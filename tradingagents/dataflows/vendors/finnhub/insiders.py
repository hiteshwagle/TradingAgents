"""Dated insider transactions and sentiment from Finnhub."""

from __future__ import annotations

from datetime import datetime, timedelta

from tradingagents.dataflows.errors import NoMarketDataError, VendorError
from tradingagents.dataflows.vendors.finnhub.client import get_json, require_api_key


def _date(value: object):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def get_insider_transactions(ticker: str, curr_date: str | None = None) -> str:
    """Return transactions and aggregate insider sentiment available by a cutoff."""
    require_api_key()
    cutoff = _date(curr_date or datetime.now().date().isoformat())
    if cutoff is None:
        raise ValueError("Finnhub insider date must use YYYY-MM-DD format")
    start = cutoff - timedelta(days=365)
    symbol = ticker.strip().upper()
    errors: list[VendorError] = []

    try:
        transactions_payload = get_json(
            "stock/insider-transactions",
            {"symbol": symbol, "from": start.isoformat(), "to": cutoff.isoformat()},
        )
    except VendorError as exc:
        errors.append(exc)
        transactions_payload = {}
    try:
        sentiment_payload = get_json(
            "stock/insider-sentiment",
            {"symbol": symbol, "from": start.isoformat(), "to": cutoff.isoformat()},
        )
    except VendorError as exc:
        errors.append(exc)
        sentiment_payload = {}

    transactions = transactions_payload.get("data", []) if isinstance(transactions_payload, dict) else []
    transactions = [
        row
        for row in transactions
        if isinstance(row, dict)
        and (_date(row.get("filingDate")) or cutoff) <= cutoff
        and (_date(row.get("transactionDate")) or cutoff) <= cutoff
    ]
    transactions.sort(key=lambda row: str(row.get("filingDate", "")), reverse=True)

    sentiment = sentiment_payload.get("data", []) if isinstance(sentiment_payload, dict) else []
    sentiment = [
        row
        for row in sentiment
        if isinstance(row, dict)
        and (int(row.get("year", 0)), int(row.get("month", 0))) <= (cutoff.year, cutoff.month)
    ]
    sentiment.sort(
        key=lambda row: (int(row.get("year", 0)), int(row.get("month", 0))), reverse=True
    )

    if not transactions and not sentiment:
        if errors:
            raise errors[0]
        raise NoMarketDataError(ticker, symbol, "Finnhub returned no dated insider activity")

    lines = [f"## {ticker} Finnhub Insider Activity through {cutoff.isoformat()}"]
    if transactions:
        lines.extend(("", "### Recent filed transactions"))
        for row in transactions[:30]:
            lines.append(
                f"- Filed {row.get('filingDate')} · transaction {row.get('transactionDate')} · "
                f"{row.get('name', 'Unknown insider')} · code {row.get('transactionCode', '?')} · "
                f"change {row.get('change')} shares at {row.get('transactionPrice')} · "
                f"post-transaction shares {row.get('share')}"
            )
    if sentiment:
        lines.extend(("", "### Monthly insider sentiment (MSPR: -100 to +100)"))
        for row in sentiment[:12]:
            lines.append(
                f"- {int(row.get('year', 0)):04d}-{int(row.get('month', 0)):02d}: "
                f"MSPR {row.get('mspr')}; net share change {row.get('change')}"
            )
    return "\n".join(lines)
