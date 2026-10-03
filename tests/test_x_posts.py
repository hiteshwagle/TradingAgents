from __future__ import annotations

import json
import sys
from datetime import date, timedelta

import pytest

from tradingagents.dataflows.vendors import x_posts


@pytest.mark.unit
def test_symbol_query_targets_market_events():
    assert x_posts.build_symbol_query("NVDA", "NVIDIA") == (
        '($NVDA OR "NVIDIA") '
        "(earnings OR revenue OR guidance OR acquisition OR partnership OR SEC OR "
        "downgrade OR upgrade) lang:en -is:retweet"
    )


@pytest.mark.unit
def test_search_scores_posts_and_reuses_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("X_API_CACHE_DIR", str(tmp_path))
    response = {
        "data": [
            {
                "id": "1",
                "text": "earnings",
                "public_metrics": {
                    "like_count": 10,
                    "repost_count": 4,
                    "reply_count": 3,
                },
            }
        ],
        "meta": {"result_count": 1},
    }
    calls = []
    monkeypatch.setattr(
        x_posts,
        "_request_json",
        lambda params, token: calls.append((params, token)) or response,
    )

    first = x_posts.search_symbol_posts("NVDA", "NVIDIA", bearer_token="test", limit=10)
    second = x_posts.search_symbol_posts("NVDA", "NVIDIA", bearer_token="test", limit=10)

    assert first["posts"][0]["score"] == 21
    assert second["posts"][0]["score"] == 21
    assert second["cached"] is True
    assert len(calls) == 1
    assert calls[0][0]["post.fields"] == x_posts.POST_FIELDS
    assert "tweet.fields" not in calls[0][0]
    assert calls[0][0]["expansions"] == "author_id"


@pytest.mark.unit
def test_scoring_accepts_legacy_retweet_count():
    post = {
        "public_metrics": {
            "like_count": 10,
            "retweet_count": 4,
            "reply_count": 3,
        }
    }

    assert x_posts._with_engagement_score(post)["score"] == 21


@pytest.mark.unit
def test_request_uses_requests_with_certifi(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        headers = {}
        content = b'{"data": []}'

        @staticmethod
        def json():
            return {"data": []}

    monkeypatch.setattr(x_posts.certifi, "where", lambda: "/test/cacert.pem")
    monkeypatch.setattr(
        x_posts.requests,
        "get",
        lambda url, **kwargs: calls.append((url, kwargs)) or Response(),
    )

    assert x_posts._request_json({"query": "$AAPL"}, "test-token") == {"data": []}
    assert calls == [
        (
            x_posts.X_RECENT_SEARCH_URL,
            {
                "params": {"query": "$AAPL"},
                "headers": {
                    "Authorization": "Bearer test-token",
                    "Accept": "application/json",
                    "User-Agent": "TradingAgents-X-Sentiment/1.0",
                },
                "timeout": 20,
                "verify": "/test/cacert.pem",
            },
        )
    ]


@pytest.mark.unit
def test_formatted_posts_are_screened_and_ordered_by_score(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "test")
    captured = {}
    posts = [
        {
            "id": "low",
            "text": "off topic",
            "created_at": "2026-09-25T01:00:00Z",
            "author_id": "1",
            "score": 2,
            "public_metrics": {"like_count": 2, "repost_count": 0, "reply_count": 0},
        },
        {
            "id": "high",
            "text": "NVDA guidance upgraded",
            "created_at": "2026-09-25T02:00:00Z",
            "author_id": "2",
            "score": 15,
            "public_metrics": {"like_count": 5, "repost_count": 4, "reply_count": 2},
        },
    ]

    def search(symbol, company_name, **kwargs):
        captured.update(symbol=symbol, company_name=company_name, **kwargs)
        return {"posts": posts}

    def screen(texts):
        assert texts == ["NVDA guidance upgraded", "off topic"]
        return [True, False], "Screened by Jev: 1 of 2 Posts retained."

    monkeypatch.setattr(x_posts, "search_symbol_posts", search)
    end_day = date.today() - timedelta(days=1)
    start_day = end_day - timedelta(days=6)
    output = x_posts.fetch_x_posts(
        "NVDA",
        "NVIDIA",
        start_date=start_day.isoformat(),
        end_date=end_day.isoformat(),
        screen=screen,
    )

    assert captured["symbol"] == "NVDA"
    assert captured["company_name"] == "NVIDIA"
    assert "Screened by Jev" in output
    assert "score 15" in output
    assert "reposts 4" in output
    assert "NVDA guidance upgraded" in output
    assert "off topic" not in output


@pytest.mark.unit
def test_formatted_fetch_is_optional_without_token(monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    assert x_posts.fetch_x_posts("NVDA") == "<X unavailable: X_BEARER_TOKEN is not set>"


@pytest.mark.unit
def test_historical_validation_can_disable_x_without_a_call(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "secret-token")
    monkeypatch.setattr(
        x_posts, "search_symbol_posts",
        lambda *args, **kwargs: pytest.fail("disabled X mode must not make a request"),
    )
    assert x_posts.fetch_x_posts("AAPL", mode="disabled") == (
        "<X disabled for this historical validation>"
    )


@pytest.mark.unit
def test_old_recent_window_is_skipped_without_a_call(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "secret-token")
    monkeypatch.setattr(
        x_posts, "search_symbol_posts",
        lambda *args, **kwargs: pytest.fail("old recent-search window must be skipped"),
    )
    assert "outside recent-search retention" in x_posts.fetch_x_posts(
        "AAPL", start_date="2025-09-01", end_date="2025-09-07", mode="recent"
    )


@pytest.mark.unit
def test_formatted_fetch_preserves_sanitized_api_error(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "secret-token")

    def fail(*args, **kwargs):
        raise x_posts.XAPIError("X API HTTP 403: forbidden secret-token")

    monkeypatch.setattr(x_posts, "search_symbol_posts", fail)

    assert x_posts.fetch_x_posts("AAPL") == (
        "<X unavailable: XAPIError: X API HTTP 403: forbidden [REDACTED]>"
    )


@pytest.mark.unit
def test_date_bounds_reject_future_or_reversed_windows():
    today = date.today()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    with pytest.raises(ValueError, match="future"):
        x_posts._date_bounds(yesterday.isoformat(), tomorrow.isoformat())
    with pytest.raises(ValueError, match="after"):
        x_posts._date_bounds(today.isoformat(), yesterday.isoformat())


@pytest.mark.unit
def test_package_cli_returns_json_error_without_token(monkeypatch, capsys):
    from cli import x_posts as x_cli

    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["tradingagents-x", "NVDA"])

    assert x_cli.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error_type"] == "XAPIError"
