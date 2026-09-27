"""Live market context and reference helpers from Finnhub."""

from __future__ import annotations

from datetime import date, datetime

from tradingagents.dataflows.date_window import get_current_date
from tradingagents.dataflows.errors import NoMarketDataError, VendorError
from tradingagents.dataflows.vendors.finnhub.client import get_json, require_api_key

_EXCHANGE_BY_SUFFIX = {
    ".AX": "AU",
    ".BO": "IN",
    ".HK": "HK",
    ".L": "L",
    ".NS": "IN",
    ".TO": "TO",
}


def _today_utc():
    return date.fromisoformat(get_current_date())


def _exchange(symbol: str) -> str:
    upper = symbol.upper()
    return next((code for suffix, code in _EXCHANGE_BY_SUFFIX.items() if upper.endswith(suffix)), "US")


def search_symbols(query: str, exchange: str | None = None):
    """Search Finnhub's symbol directory for application-side symbol resolution."""
    return get_json("search", {"q": query, "exchange": exchange}, cache_ttl_seconds=86_400)


def get_live_market_context(ticker: str, curr_date: str) -> str:
    """Return live quote/session context; never use it in historical analysis."""
    require_api_key()
    try:
        current = datetime.strptime(curr_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Finnhub live-market date must use YYYY-MM-DD format") from exc
    if current != _today_utc():
        raise NoMarketDataError(
            ticker,
            ticker,
            "Finnhub live quote and session state are withheld for historical analysis",
        )

    symbol = ticker.strip().upper()
    exchange = _exchange(symbol)
    errors: list[VendorError] = []
    try:
        status = get_json(
            "stock/market-status", {"exchange": exchange}, cache_ttl_seconds=60
        )
    except VendorError as exc:
        errors.append(exc)
        status = {}

    quote = {}
    # Finnhub documents free real-time quotes for US equities; do not imply the
    # same entitlement for international symbols.
    if exchange == "US":
        try:
            quote = get_json("quote", {"symbol": symbol}, cache_ttl_seconds=30)
        except VendorError as exc:
            errors.append(exc)

    if not status and not quote:
        if errors:
            raise errors[0]
        raise NoMarketDataError(ticker, symbol, "Finnhub returned no live market context")

    lines = [
        f"## {ticker} Finnhub Live Market Context",
        "",
        "Live context only; the verified historical snapshot remains the source of truth.",
    ]
    if isinstance(status, dict) and status:
        lines.extend(
            (
                "",
                "### Exchange session",
                f"- Exchange: {status.get('exchange', exchange)}",
                f"- Open: {status.get('isOpen')}",
                f"- Session: {status.get('session')}",
                f"- Holiday: {status.get('holiday')}",
                f"- Timezone: {status.get('timezone')}",
            )
        )
    if isinstance(quote, dict) and quote.get("c"):
        lines.extend(
            (
                "",
                "### Current US quote",
                f"- Current: {quote.get('c')}",
                f"- Change: {quote.get('d')} ({quote.get('dp')}%)",
                f"- Open/high/low: {quote.get('o')} / {quote.get('h')} / {quote.get('l')}",
                f"- Previous close: {quote.get('pc')}",
                f"- Vendor timestamp: {quote.get('t')}",
            )
        )
    return "\n".join(lines)
