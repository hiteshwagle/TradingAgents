"""Authorized StockTwits aggregate-sentiment client.

StockTwits' supported Firestream endpoint requires HTTP Basic authentication
and returns current aggregate sentiment, message-volume, and participation
metrics. It does not return archived posts, so historical runs skip the source
instead of leaking today's sentiment into a past analysis.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import certifi
import requests
from requests.auth import HTTPBasicAuth

from tradingagents.dataflows.symbols import crypto_base

logger = logging.getLogger(__name__)

_API = (
    "https://api-gw-prd.stocktwits.com/api-middleware/external/"
    "sentiment/v2/{ticker}/detail"
)
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"


def _stocktwits_symbol(ticker: str) -> str:
    """Map crypto pairs to StockTwits' ``<BASE>.X`` convention."""
    base = crypto_base(ticker)
    return f"{base}.X" if base else ticker.strip().upper()


def _is_historical(end_date: str | None) -> bool:
    """Return true when the requested cutoff predates today in UTC."""
    if not end_date:
        return False
    try:
        return datetime.strptime(end_date, "%Y-%m-%d").date() < datetime.now(
            timezone.utc
        ).date()
    except ValueError:
        # Let the graph's normal date validation own malformed dates. Treating
        # one as historical here is the safer behavior for current-only data.
        return True


def _metric(section: dict, key: str) -> str | None:
    value = section.get(key)
    if not isinstance(value, dict):
        return None
    label = str(value.get("labelNormalized") or "NA").replace("_", " ")
    score = value.get("valueNormalized")
    if isinstance(score, (int, float)):
        return f"{label} ({score:.1f}/100)"
    return label


def _format_response(ticker: str, payload: object) -> str:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        return "<StockTwits unavailable: unexpected response shape>"

    data = payload["data"]
    sentiment = data.get("sentiment") if isinstance(data.get("sentiment"), dict) else {}
    volume = (
        data.get("messageVolume")
        if isinstance(data.get("messageVolume"), dict)
        else {}
    )
    timeframes = data.get("timeframes") if isinstance(data.get("timeframes"), dict) else {}

    lines = [
        f"StockTwits authorized aggregate sentiment for ${ticker.upper()} (current data)",
        "This source contains aggregate metrics, not individual posts.",
    ]
    for label, section, key in (
        ("Current sentiment", sentiment, "now"),
        ("15-minute sentiment", sentiment, "15m"),
        ("24-hour sentiment", sentiment, "24h"),
        ("Current message volume", volume, "now"),
        ("15-minute message volume", volume, "15m"),
        ("24-hour message volume", volume, "24h"),
    ):
        formatted = _metric(section, key)
        if formatted:
            lines.append(f"{label}: {formatted}")

    one_day = timeframes.get("1D")
    if isinstance(one_day, dict):
        for label, key in (
            ("1-day sentiment", "sentiment"),
            ("1-day buzz", "buzz"),
            ("1-day participation", "participationScore"),
        ):
            formatted = _metric(one_day, key)
            if formatted:
                lines.append(f"{label}: {formatted}")

    if len(lines) == 2:
        return "<StockTwits unavailable: response contained no sentiment metrics>"
    return "\n".join(lines)


def fetch_stocktwits_messages(
    ticker: str,
    limit: int = 30,
    timeout: float = 35.0,
    start_date: str | None = None,
    end_date: str | None = None,
    screen=None,
) -> str:
    """Return current authorized StockTwits aggregate sentiment for ``ticker``.

    ``limit`` and ``screen`` remain in the signature for compatibility with the
    former post-stream client. Firestream returns aggregates rather than posts,
    so neither option applies.
    """
    del limit, screen

    if _is_historical(end_date):
        window = f"{start_date or '?'}..{end_date}"
        return (
            f"<StockTwits unavailable for historical window {window}: "
            "authorized Firestream sentiment is current-only>"
        )

    username = os.getenv("STOCKTWITS_USERNAME", "").strip()
    password = os.getenv("STOCKTWITS_PASSWORD", "")
    if not username or not password:
        return (
            "<StockTwits unavailable: configure STOCKTWITS_USERNAME and "
            "STOCKTWITS_PASSWORD for authorized Firestream access>"
        )

    url = _API.format(ticker=_stocktwits_symbol(ticker))
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(username, password),
            headers={
                "User-Agent": _UA,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
            timeout=(5.0, timeout),
            verify=certifi.where(),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.RequestException as exc:
        status = exc.response.status_code if exc.response is not None else None
        detail = f"HTTP {status}" if status else type(exc).__name__
        logger.warning("StockTwits fetch failed for %s: %s", ticker, detail)
        return f"<StockTwits unavailable: {detail}>"
    except ValueError:
        logger.warning("StockTwits fetch failed for %s: invalid JSON response", ticker)
        return "<StockTwits unavailable: invalid JSON response>"

    return _format_response(ticker, payload)
