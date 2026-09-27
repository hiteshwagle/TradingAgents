"""Finnhub shared-client, point-in-time, routing, and agent-safety tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from time import sleep
from unittest import mock

import certifi
import pytest

from tradingagents.dataflows import router
from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)
from tradingagents.dataflows.vendors.finnhub import client, events, fundamentals, market, news


def _response(payload, status_code=200, headers=None):
    response = mock.Mock(status_code=status_code, headers=headers or {})
    response.json.return_value = payload
    return response


@pytest.fixture(autouse=True)
def reset_client_state(monkeypatch, tmp_path):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    config = get_config()
    config.update(
        data_cache_dir=str(tmp_path),
        finnhub_requests_per_minute=10_000,
        finnhub_max_calls_per_run=30,
        finnhub_max_concurrency=2,
        finnhub_cache_ttl_seconds=900,
        finnhub_historical_cache_ttl_seconds=86_400,
    )
    monkeypatch.setattr(client, "get_config", lambda: config)
    client._request_times.clear()
    client._key_locks.clear()
    client._semaphores.clear()


def test_shared_client_uses_header_certifi_cache_and_single_flight():
    response = _response({"value": 1})

    def delayed(*args, **kwargs):
        sleep(0.03)
        return response

    with (
        mock.patch.object(client.requests, "get", side_effect=delayed) as get,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        results = list(pool.map(lambda _: client.get_json("quote", {"symbol": "AAPL"}), range(2)))

    assert results == [{"value": 1}, {"value": 1}]
    assert get.call_count == 1
    call = get.call_args
    assert call.kwargs["headers"]["X-Finnhub-Token"] == "test-key"
    assert "test-key" not in str(call.kwargs["params"])
    assert call.kwargs["verify"] == certifi.where()


def test_missing_key_and_rate_limit_are_typed(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY")
    with pytest.raises(VendorNotConfiguredError, match="FINNHUB_API_KEY"):
        client.get_json("quote", {"symbol": "AAPL"})

    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    with (
        mock.patch.object(
            client.requests,
            "get",
            return_value=_response({}, 429, {"Retry-After": "10"}),
        ),
        pytest.raises(VendorRateLimitError, match="retry after 10s"),
    ):
        client.get_json("quote", {"symbol": "MSFT"})


def test_run_budget_counts_only_uncached_http_calls():
    with (
        mock.patch.object(client.requests, "get", return_value=_response({"c": 1})) as get,
        client.finnhub_run_budget(1),
    ):
        assert client.get_json("quote", {"symbol": "AAPL"}) == {"c": 1}
        assert client.get_json("quote", {"symbol": "AAPL"}) == {"c": 1}
        with pytest.raises(VendorRateLimitError, match="per-run call budget"):
            client.get_json("quote", {"symbol": "MSFT"})

    assert get.call_count == 1


def test_company_news_filters_dates_sanitizes_and_limits(monkeypatch):
    monkeypatch.setattr(news, "get_config", lambda: {
        "news_article_limit": 1,
        "finnhub_historical_cache_ttl_seconds": 86_400,
    })
    inside = int(datetime(2026, 9, 10, 12, tzinfo=timezone.utc).timestamp())
    outside = int(datetime(2026, 9, 11, 0, tzinfo=timezone.utc).timestamp())
    payload = [
        {
            "id": 1,
            "datetime": inside,
            "headline": "<b>Apple results</b>",
            "summary": "Revenue rose.",
            "source": "Reuters",
            "url": "https://example.test/one",
        },
        {"id": 2, "datetime": outside, "headline": "Future article"},
    ]
    with mock.patch.object(news, "get_json", return_value=payload) as get:
        result = news.get_news("AAPL", "2026-09-10", "2026-09-10")

    assert "Apple results" in result
    assert "<b>" not in result
    assert "Future article" not in result
    assert get.call_args.args[0] == "company-news"


def test_latest_market_news_is_withheld_from_historical_runs(monkeypatch):
    monkeypatch.setattr(news, "_today_utc", lambda: date(2026, 9, 27))
    with (
        mock.patch.object(news, "get_json") as get,
        pytest.raises(NoMarketDataError, match="latest-only"),
    ):
        news.get_global_news("2026-09-26")
    get.assert_not_called()


def test_historical_fundamentals_withhold_current_snapshots(monkeypatch):
    monkeypatch.setattr(fundamentals, "require_api_key", lambda: "key")
    monkeypatch.setattr(fundamentals, "_today_utc", lambda: date(2026, 9, 27))
    seen = []

    def payload(endpoint, params):
        seen.append(endpoint)
        if endpoint == "stock/earnings":
            return [{"period": "2026-06-30", "actual": 2, "estimate": 1, "surprisePercent": 100}]
        if endpoint == "stock/recommendation":
            return [{"period": "2026-06-01", "buy": 3, "hold": 1, "sell": 0}]
        if endpoint == "stock/filings":
            return [{"acceptedDate": "2026-06-02 10:00:00", "form": "10-Q", "reportUrl": "https://example.test/10q"}]
        raise AssertionError(endpoint)

    monkeypatch.setattr(fundamentals, "get_json", payload)
    result = fundamentals.get_fundamentals("AAPL", "2026-07-01")
    assert "withheld" in result
    assert "Earnings surprises" in result
    assert "10-Q" in result
    assert "stock/profile2" not in seen
    assert "stock/metric" not in seen
    assert "stock/peers" not in seen


def test_current_only_events_and_market_context_do_not_call_historical_api(monkeypatch):
    monkeypatch.setattr(events, "require_api_key", lambda: "key")
    monkeypatch.setattr(market, "require_api_key", lambda: "key")
    monkeypatch.setattr(events, "_today_utc", lambda: date(2026, 9, 27))
    monkeypatch.setattr(market, "_today_utc", lambda: date(2026, 9, 27))
    with (
        mock.patch.object(events, "get_json") as event_get,
        pytest.raises(NoMarketDataError, match="historical"),
    ):
        events.get_company_events("AAPL", "2026-09-26")
    with (
        mock.patch.object(market, "get_json") as market_get,
        pytest.raises(NoMarketDataError, match="historical"),
    ):
        market.get_live_market_context("AAPL", "2026-09-26")
    event_get.assert_not_called()
    market_get.assert_not_called()


def test_router_and_defaults_expose_shared_finnhub_features():
    config = get_config()
    assert config["tool_vendors"]["get_news"] == "alpaca,yfinance,finnhub"
    assert config["tool_vendor_modes"]["get_news"] == "aggregate"
    assert "finnhub" in router.VENDOR_METHODS["get_news"]
    assert "finnhub" in router.VENDOR_METHODS["get_global_news"]
    assert "finnhub" in router.VENDOR_METHODS["get_fundamentals"]
    assert "finnhub" in router.VENDOR_METHODS["get_insider_transactions"]
    assert set(router.VENDOR_METHODS["get_company_events"]) == {"finnhub"}
    assert set(router.VENDOR_METHODS["get_live_market_context"]) == {"finnhub"}
