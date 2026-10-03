from datetime import datetime, timezone

import pytest

from tradingagents.scanner import HistoricalScannerUnsupportedError, MarketScanner, ScannerConfig


class FakeClient:
    def movers(self, top):
        return {"gainers": [{"symbol": "AAA", "percent_change": 8, "price": 10}],
                "losers": [{"symbol": "BBB", "percent_change": -7, "price": 20}]}

    def most_actives(self, by, top):
        return {"most_actives": [{"symbol": "AAA", "volume": 1_000_000},
                                  {"symbol": "BRK.B", "volume": 600_000}]}

    def news(self, **kwargs):
        return [{"id": 1, "symbols": ["AAA", "BRK.B"]},
                {"id": 1, "symbols": ["AAA"]}]

    def snapshots(self, symbols, feed):
        return {s: {"latestTrade": {"p": 10, "t": "2026-10-01T15:00:00Z"},
                    "latestQuote": {"bp": 9.99, "ap": 10.01},
                    "dailyBar": {"c": 10, "v": 1_000_000, "t": "2026-10-01T14:59:00Z"},
                    "prevDailyBar": {"c": 9.5}} for s in symbols}

    def bars(self, symbols, **kwargs):
        return {s: [{"v": 200_000}] * 20 + [{"v": 1_000_000}] for s in symbols}


NOW = datetime(2026, 10, 1, 15, tzinfo=timezone.utc)


def test_scanner_merges_sources_scores_and_preserves_losers_and_punctuation():
    result = MarketScanner(FakeClient(), ScannerConfig(feed="iex", top_n=10), lambda: NOW).scan()
    rows = {row["symbol"]: row for row in result["candidates"]}
    assert {"AAA", "BBB", "BRK.B"} <= rows.keys()
    assert rows["BBB"]["direction"] == "loser"
    assert rows["AAA"]["relative_volume"] == 5
    assert rows["AAA"]["news_count"] == 1
    assert rows["AAA"]["score"] is not None
    assert rows["AAA"]["data_completeness"] == 1
    assert any("not comparable" in warning for warning in rows["AAA"]["warnings"])
    assert any("equal materiality" in warning for warning in rows["AAA"]["warnings"])


def test_outside_market_hours_labels_rankings_as_prior_session_data():
    after_hours = datetime(2026, 10, 1, 22, tzinfo=timezone.utc)
    result = MarketScanner(FakeClient(), ScannerConfig(top_n=10), lambda: after_hours).scan()
    assert result["session"] == "outside_regular_hours"
    assert any("prior market session" in warning for warning in result["metadata"]["warnings"])
    assert any("outside regular" in warning for warning in result["candidates"][0]["warnings"])


def test_scanner_rejects_historical_date_and_naive_clock():
    scanner = MarketScanner(FakeClient(), now=lambda: NOW)
    with pytest.raises(HistoricalScannerUnsupportedError):
        scanner.scan("2026-09-30")
    with pytest.raises(ValueError, match="timezone"):
        MarketScanner(FakeClient(), now=lambda: datetime(2026, 10, 1)).scan()


def test_missing_core_snapshots_excludes_candidates():
    client = FakeClient()
    client.snapshots = lambda symbols, feed: {}
    result = MarketScanner(client, ScannerConfig(top_n=10), lambda: NOW).scan()
    assert result["candidates"] == []
    assert len(result["excluded"]) == 3


def test_optional_sources_degrade_visibly():
    client = FakeClient()
    client.news = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("secret response"))
    result = MarketScanner(client, ScannerConfig(top_n=10), lambda: NOW).scan()
    assert result["metadata"]["failed_sources"]["news"] == "RuntimeError"
    assert "secret response" not in str(result)
