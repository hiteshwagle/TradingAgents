"""Historical social sentiment must not leak current data into a backtest (#1220).

Reddit pulls only recent items, so for a historical run they must be trimmed to
the analysis window (and yield a clear placeholder when nothing qualifies)
rather than showing today's chatter as if it were from the as-of date.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tradingagents.dataflows.date_window import in_window
from tradingagents.dataflows.vendors import reddit

# --- shared window helper ---------------------------------------------------

@pytest.mark.unit
def test_in_window_bounds_and_exclusive_upper():
    start = datetime(2026, 5, 1)
    end = datetime(2026, 5, 9)
    assert in_window(datetime(2026, 5, 5, tzinfo=timezone.utc), start, end) is True
    assert in_window(datetime(2026, 5, 9, 23, 59, tzinfo=timezone.utc), start, end) is True
    # exactly midnight after end -> excluded (no leak)
    assert in_window(datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc), start, end) is False
    # offset-aware converted, not truncated: 05-10T01:00+05:00 == 05-09T20:00Z
    assert in_window(datetime.fromisoformat("2026-05-10T01:00:00+05:00"), start, end) is True


@pytest.mark.unit
def test_in_window_undated_excluded_in_backtest_kept_live():
    old = datetime(2026, 5, 9)
    assert in_window(None, datetime(2026, 5, 1), old) is False       # historical
    now = datetime.now(timezone.utc)
    assert in_window(None, now, now) is True                          # live


# --- Reddit -----------------------------------------------------------------

def _epoch(date_str):
    return int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


@pytest.mark.unit
def test_reddit_historical_window_excludes_recent(monkeypatch):
    posts = [{"title": "NOW", "created_utc": _epoch("2026-08-30"), "source": "rss"}]
    monkeypatch.setattr(reddit, "_fetch_subreddit_rss", lambda *a, **k: posts)
    out = reddit.fetch_reddit_posts(
        "AAPL", subreddits=("stocks",),
        start_date="2026-05-01", end_date="2026-05-08",
    )
    assert "NOW" not in out
    assert "unavailable" in out and "not an absence" in out


@pytest.mark.unit
def test_reddit_live_window_keeps_in_range(monkeypatch):
    posts = [{"title": "INRANGE", "created_utc": _epoch("2026-05-05"), "source": "rss"}]
    monkeypatch.setattr(reddit, "_fetch_subreddit_rss", lambda *a, **k: posts)
    out = reddit.fetch_reddit_posts(
        "AAPL", subreddits=("stocks",),
        start_date="2026-05-01", end_date="2026-05-08",
    )
    assert "INRANGE" in out


# --- coverage vs absence --------------------------------------------------------
# The public feeds only serve recent items. When everything fetched postdates the
# window the source cannot answer for that date; reporting "no posts" there is a
# claim about the market that was never observed.

@pytest.mark.unit
def test_reddit_covered_but_empty_window_is_a_real_absence(monkeypatch):
    posts = [{"title": "NOW", "created_utc": _epoch("2026-08-30"), "source": "rss"},
             {"title": "OLD", "created_utc": _epoch("2026-04-20"), "source": "rss"}]
    monkeypatch.setattr(reddit, "_fetch_subreddit_rss", lambda *a, **k: posts)
    out = reddit.fetch_reddit_posts(
        "AAPL", subreddits=("stocks",),
        start_date="2026-05-01", end_date="2026-05-08",
    )
    assert "no reddit posts" in out.lower()
    assert "unavailable" not in out


@pytest.mark.unit
def test_reddit_empty_feed_for_an_old_window_is_unavailable(monkeypatch):
    # Search is limited to the last week, so an empty response says nothing
    # about a window from months ago: there are no timestamps to go on, and the
    # lookback bound alone must decide.
    monkeypatch.setattr(reddit, "_fetch_subreddit_rss", lambda *a, **k: [])
    out = reddit.fetch_reddit_posts(
        "AAPL", subreddits=("stocks",),
        start_date="2024-05-01", end_date="2024-05-08",
    )
    assert "unavailable" in out and "not an absence" in out


@pytest.mark.unit
def test_reddit_live_empty_feed_is_a_real_absence(monkeypatch):
    monkeypatch.setattr(reddit, "_fetch_subreddit_rss", lambda *a, **k: [])
    out = reddit.fetch_reddit_posts("AAPL", subreddits=("stocks",))
    assert "no reddit posts" in out.lower() and "past 7 days" in out
    assert "unavailable" not in out


@pytest.mark.unit
def test_reddit_window_straddling_the_lookback_is_unavailable(monkeypatch):
    # Ten days ago through five days ago: the week-long search never reaches the
    # first three days, so an empty result cannot stand for the whole window.
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    monkeypatch.setattr(reddit, "_fetch_subreddit_rss", lambda *a, **k: [])
    out = reddit.fetch_reddit_posts(
        "AAPL", subreddits=("stocks",),
        start_date=str(today - timedelta(days=10)), end_date=str(today - timedelta(days=5)),
    )
    assert "unavailable" in out


@pytest.mark.unit
def test_reddit_standard_week_window_empty_is_a_real_absence(monkeypatch):
    # The graph's window is [trade_date - 7, trade_date]; the week-long search
    # covers it, so an empty result is genuine silence.
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    monkeypatch.setattr(reddit, "_fetch_subreddit_rss", lambda *a, **k: [])
    out = reddit.fetch_reddit_posts(
        "AAPL", subreddits=("stocks",),
        start_date=str(today - timedelta(days=7)), end_date=str(today),
    )
    assert "no reddit posts" in out.lower() and "unavailable" not in out


@pytest.mark.unit
def test_reddit_full_page_does_not_vouch_for_older_days(monkeypatch):
    # 100 posts from today say nothing about five days ago: the page may have
    # cut older matches off, so the window stays unavailable.
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    ts = _epoch(str(today))
    page = [{"title": f"T{i}", "created_utc": ts, "subreddit": "stocks"} for i in range(reddit._FEED_PAGE)]
    monkeypatch.setattr(reddit, "_fetch_subreddit_rss", lambda *a, **k: page)
    out = reddit.fetch_reddit_posts(
        "AAPL", subreddits=("stocks",),
        start_date=str(today - timedelta(days=6)), end_date=str(today - timedelta(days=5)),
    )
    assert "unavailable" in out and "no reddit posts" not in out.lower()
