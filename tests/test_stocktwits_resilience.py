"""Tests for the authorized StockTwits aggregate-sentiment client."""

from __future__ import annotations

from unittest.mock import Mock

import certifi
import pytest
import requests
from requests.auth import HTTPBasicAuth

from tradingagents.dataflows.vendors import stocktwits


def _payload():
    return {
        "data": {
            "messageVolume": {
                "now": {"labelNormalized": "LOW", "valueNormalized": 25.8},
                "24h": {"labelNormalized": "HIGH", "valueNormalized": 75.2},
            },
            "sentiment": {
                "now": {"labelNormalized": "BEARISH", "valueNormalized": 35.7},
                "24h": {"labelNormalized": "NEUTRAL", "valueNormalized": 50},
            },
            "timeframes": {
                "1D": {
                    "buzz": {"labelNormalized": "NORMAL", "valueNormalized": 52.1},
                    "participationScore": {
                        "labelNormalized": "NORMAL",
                        "valueNormalized": 55.2,
                    },
                    "sentiment": {
                        "labelNormalized": "BULLISH",
                        "valueNormalized": 68.9,
                    },
                }
            },
        }
    }


@pytest.mark.unit
def test_missing_credentials_does_not_call_network(monkeypatch):
    monkeypatch.delenv("STOCKTWITS_USERNAME", raising=False)
    monkeypatch.delenv("STOCKTWITS_PASSWORD", raising=False)
    get = Mock()
    monkeypatch.setattr(stocktwits.requests, "get", get)

    out = stocktwits.fetch_stocktwits_messages("AMD")

    assert "configure STOCKTWITS_USERNAME" in out
    get.assert_not_called()


@pytest.mark.unit
def test_historical_request_never_calls_current_only_endpoint(monkeypatch):
    monkeypatch.setenv("STOCKTWITS_USERNAME", "user")
    monkeypatch.setenv("STOCKTWITS_PASSWORD", "secret")
    get = Mock()
    monkeypatch.setattr(stocktwits.requests, "get", get)

    out = stocktwits.fetch_stocktwits_messages(
        "AMD", start_date="2025-08-28", end_date="2025-09-04"
    )

    assert "historical window 2025-08-28..2025-09-04" in out
    assert "current-only" in out
    get.assert_not_called()


@pytest.mark.unit
def test_live_request_uses_firestream_basic_auth_and_certifi(monkeypatch):
    monkeypatch.setenv("STOCKTWITS_USERNAME", "user")
    monkeypatch.setenv("STOCKTWITS_PASSWORD", "secret")
    response = Mock()
    response.json.return_value = _payload()
    get = Mock(return_value=response)
    monkeypatch.setattr(stocktwits.requests, "get", get)

    out = stocktwits.fetch_stocktwits_messages("AMD", timeout=40)

    url = get.call_args.args[0]
    kwargs = get.call_args.kwargs
    assert url.endswith("/external/sentiment/v2/AMD/detail")
    assert kwargs["auth"] == HTTPBasicAuth("user", "secret")
    assert kwargs["headers"]["Accept-Encoding"] == "gzip"
    assert kwargs["timeout"] == (5.0, 40)
    assert kwargs["verify"] == certifi.where()
    assert "Current sentiment: BEARISH (35.7/100)" in out
    assert "24-hour message volume: HIGH (75.2/100)" in out
    assert "1-day participation: NORMAL (55.2/100)" in out
    assert "individual posts" in out


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc",
    [
        requests.exceptions.ChunkedEncodingError("incomplete"),
        requests.exceptions.Timeout("slow"),
    ],
)
def test_transport_errors_return_placeholder(monkeypatch, exc):
    monkeypatch.setenv("STOCKTWITS_USERNAME", "user")
    monkeypatch.setenv("STOCKTWITS_PASSWORD", "secret")
    monkeypatch.setattr(stocktwits.requests, "get", Mock(side_effect=exc))

    out = stocktwits.fetch_stocktwits_messages("AMD")

    assert out.startswith("<StockTwits unavailable")


@pytest.mark.unit
def test_http_error_reports_status_without_credentials(monkeypatch, caplog):
    monkeypatch.setenv("STOCKTWITS_USERNAME", "user")
    monkeypatch.setenv("STOCKTWITS_PASSWORD", "do-not-log-this")
    response = requests.Response()
    response.status_code = 403
    response.url = "https://example.invalid/AMD/detail"
    monkeypatch.setattr(stocktwits.requests, "get", Mock(return_value=response))

    out = stocktwits.fetch_stocktwits_messages("AMD")

    assert out == "<StockTwits unavailable: HTTP 403>"
    assert "HTTP 403" in caplog.text
    assert "do-not-log-this" not in caplog.text


@pytest.mark.unit
def test_unexpected_payload_degrades_gracefully(monkeypatch):
    monkeypatch.setenv("STOCKTWITS_USERNAME", "user")
    monkeypatch.setenv("STOCKTWITS_PASSWORD", "secret")
    response = Mock()
    response.json.return_value = {"not_data": {}}
    monkeypatch.setattr(stocktwits.requests, "get", Mock(return_value=response))

    out = stocktwits.fetch_stocktwits_messages("AMD")

    assert out == "<StockTwits unavailable: unexpected response shape>"


@pytest.mark.unit
class TestStockTwitsCryptoSymbols:
    @pytest.mark.parametrize(
        ("ticker", "expected"),
        [
            ("BTC-USD", "BTC.X"),
            ("eth-usd", "ETH.X"),
            ("SOL-USD", "SOL.X"),
            ("BTCUSD", "BTC.X"),
            ("BTC-USDT", "BTC.X"),
            ("AMD", "AMD"),
            ("BRK-B", "BRK-B"),
            ("GOLD", "GOLD"),
            ("XYZ-USD", "XYZ-USD"),
        ],
    )
    def test_symbol_mapping(self, ticker, expected):
        assert stocktwits._stocktwits_symbol(ticker) == expected
