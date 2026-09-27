"""Current company catalyst calendar from Finnhub."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from tradingagents.dataflows.date_window import get_current_date
from tradingagents.dataflows.errors import NoMarketDataError, VendorError
from tradingagents.dataflows.vendors.finnhub.client import get_json, require_api_key


def _today_utc():
    return date.fromisoformat(get_current_date())


def get_company_events(
    ticker: str,
    curr_date: str,
    look_ahead_days: int | None = None,
) -> str:
    """Return upcoming earnings and IPO events; withhold non-vintage historical calendars."""
    require_api_key()
    try:
        current = datetime.strptime(curr_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Finnhub company-event date must use YYYY-MM-DD format") from exc
    if current != _today_utc():
        raise NoMarketDataError(
            ticker,
            ticker,
            "Finnhub calendars are current snapshots and are withheld for historical analysis",
        )
    days = min(90, max(1, int(look_ahead_days or 30)))
    end = current + timedelta(days=days)
    symbol = ticker.strip().upper()
    errors: list[VendorError] = []

    try:
        earnings_payload = get_json(
            "calendar/earnings",
            {"from": current.isoformat(), "to": end.isoformat(), "symbol": symbol},
            cache_ttl_seconds=3_600,
        )
    except VendorError as exc:
        errors.append(exc)
        earnings_payload = {}
    try:
        ipo_payload = get_json(
            "calendar/ipo",
            {"from": current.isoformat(), "to": end.isoformat()},
            cache_ttl_seconds=3_600,
        )
    except VendorError as exc:
        errors.append(exc)
        ipo_payload = {}

    earnings = earnings_payload.get("earningsCalendar", []) if isinstance(earnings_payload, dict) else []
    earnings = [row for row in earnings if isinstance(row, dict) and row.get("symbol") == symbol]
    ipos = ipo_payload.get("ipoCalendar", []) if isinstance(ipo_payload, dict) else []
    ipos = [row for row in ipos if isinstance(row, dict) and row.get("symbol") == symbol]

    if not earnings and not ipos:
        if errors:
            raise errors[0]
        raise NoMarketDataError(
            ticker,
            symbol,
            f"Finnhub returned no company events through {end.isoformat()}",
        )

    lines = [
        f"## {ticker} Finnhub Company Events, {current.isoformat()} to {end.isoformat()}",
        "",
        "This is scheduling context, not a directional signal.",
    ]
    if earnings:
        lines.extend(("", "### Earnings calendar"))
        for row in earnings:
            lines.append(
                f"- {row.get('date')} ({row.get('hour', 'time unknown')}): "
                f"Q{row.get('quarter')} {row.get('year')}; EPS estimate {row.get('epsEstimate')}; "
                f"revenue estimate {row.get('revenueEstimate')}"
            )
    if ipos:
        lines.extend(("", "### IPO calendar"))
        for row in ipos:
            lines.append(
                f"- {row.get('date')}: {row.get('name', symbol)} · {row.get('exchange')} · "
                f"status {row.get('status')} · price {row.get('price')}"
            )
    return "\n".join(lines)
