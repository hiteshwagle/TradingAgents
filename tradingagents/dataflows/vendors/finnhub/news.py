"""Point-in-time company and current market news from Finnhub."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.date_window import get_current_date
from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.vendors.finnhub.client import get_json
from tradingagents.dataflows.vendors.finnhub.models import (
    NewsItem,
    clean_text,
    format_news,
    safe_url,
    unix_datetime,
)

MARKET_NEWS_CATEGORIES = ("general", "forex", "crypto", "merger")


def _date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Finnhub dates must use YYYY-MM-DD format") from exc


def _today_utc() -> date:
    return date.fromisoformat(get_current_date())


def _normalize(raw: dict) -> NewsItem | None:
    published = unix_datetime(raw.get("datetime"))
    headline = clean_text(raw.get("headline"), 500)
    if published is None or not headline:
        return None
    return NewsItem(
        vendor_id=str(raw.get("id", "")),
        headline=headline,
        summary=clean_text(raw.get("summary")),
        source=clean_text(raw.get("source"), 100) or "Unknown",
        url=safe_url(raw.get("url")),
        published_at=published,
        category=clean_text(raw.get("category"), 100),
        related=clean_text(raw.get("related"), 300),
    )


def _dedupe(items: list[NewsItem], limit: int) -> list[NewsItem]:
    selected: list[NewsItem] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(items, key=lambda entry: entry.published_at, reverse=True):
        if item.dedupe_key in seen:
            continue
        seen.add(item.dedupe_key)
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """Return North-American company news inside an inclusive UTC date window."""
    start_day = _date(start_date)
    end_day = _date(end_date)
    if start_day > end_day:
        raise ValueError("Finnhub news start_date must be on or before end_date")
    config = get_config()
    ttl = (
        config["finnhub_cache_ttl_seconds"]
        if end_day >= _today_utc()
        else config["finnhub_historical_cache_ttl_seconds"]
    )
    payload = get_json(
        "company-news",
        {"symbol": ticker.strip().upper(), "from": start_date, "to": end_date},
        cache_ttl_seconds=ttl,
    )
    if not isinstance(payload, list):
        raise NoMarketDataError(ticker, ticker, "Finnhub returned an unexpected news response")

    items = []
    for raw in payload:
        item = _normalize(raw) if isinstance(raw, dict) else None
        if item and start_day <= item.published_at.date() <= end_day:
            items.append(item)
    items = _dedupe(items, int(config["news_article_limit"]))
    if not items:
        raise NoMarketDataError(
            ticker,
            ticker,
            f"Finnhub returned no company news from {start_date} to {end_date}",
        )
    return format_news(f"{ticker} News from Finnhub, {start_date} to {end_date}", items)


def get_global_news(
    curr_date: str,
    look_back_days: int | None = None,
    limit: int | None = None,
) -> str:
    """Return current Finnhub market news; historical runs are withheld."""
    current_day = _date(curr_date)
    if current_day != _today_utc():
        raise NoMarketDataError(
            "global news",
            "global news",
            "Finnhub market-news is latest-only and is withheld for historical analysis",
        )
    config = get_config()
    lookback = int(look_back_days or config["global_news_lookback_days"])
    resolved_limit = int(limit or config["global_news_article_limit"])
    earliest = current_day - timedelta(days=max(1, lookback))
    items: list[NewsItem] = []
    for category in MARKET_NEWS_CATEGORIES:
        payload = get_json("news", {"category": category, "minId": 0})
        if not isinstance(payload, list):
            continue
        for raw in payload:
            item = _normalize(raw) if isinstance(raw, dict) else None
            if item and earliest <= item.published_at.date() <= current_day:
                items.append(item)

    items = _dedupe(items, resolved_limit)
    if not items:
        raise NoMarketDataError(
            "global news",
            "global news",
            f"Finnhub returned no current market news through {curr_date}",
        )
    return format_news(
        f"Finnhub Market News, {earliest.isoformat()} to {curr_date}",
        items,
    )
