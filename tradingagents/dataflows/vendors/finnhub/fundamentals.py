"""Finnhub company-intelligence enrichment for the Fundamentals Analyst."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from tradingagents.dataflows.date_window import get_current_date
from tradingagents.dataflows.errors import NoMarketDataError, VendorError
from tradingagents.dataflows.vendors.finnhub.client import get_json, require_api_key
from tradingagents.dataflows.vendors.finnhub.models import clean_text

_METRICS = {
    "marketCapitalization": "Market capitalization",
    "peBasicExclExtraTTM": "P/E (TTM)",
    "pbAnnual": "Price/book",
    "psTTM": "Price/sales (TTM)",
    "grossMarginTTM": "Gross margin (TTM)",
    "operatingMarginTTM": "Operating margin (TTM)",
    "netProfitMarginTTM": "Net margin (TTM)",
    "currentRatioQuarterly": "Current ratio",
    "totalDebt/totalEquityQuarterly": "Debt/equity",
    "52WeekHigh": "52-week high",
    "52WeekLow": "52-week low",
    "beta": "Beta",
}


def _today_utc():
    return date.fromisoformat(get_current_date())


def _as_date(value: object):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _fetch(endpoint: str, params: dict, errors: list[VendorError]):
    try:
        return get_json(endpoint, params)
    except VendorError as exc:
        errors.append(exc)
        return None


def get_fundamentals(ticker: str, curr_date: str) -> str:
    """Return a bounded Finnhub company-intelligence report as of ``curr_date``."""
    require_api_key()
    try:
        cutoff = datetime.strptime(curr_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Finnhub fundamentals date must use YYYY-MM-DD format") from exc
    symbol = ticker.strip().upper()
    live = cutoff == _today_utc()
    errors: list[VendorError] = []
    sections: list[str] = [f"## {ticker} Finnhub Company Intelligence as of {curr_date}"]

    # These endpoints expose current state without a historical-vintage field,
    # so they are deliberately withheld from backtests.
    if live:
        profile = _fetch("stock/profile2", {"symbol": symbol}, errors)
        if isinstance(profile, dict) and profile:
            fields = {
                "Name": profile.get("name"),
                "Exchange": profile.get("exchange"),
                "Industry": profile.get("finnhubIndustry"),
                "Country": profile.get("country"),
                "Currency": profile.get("currency"),
                "IPO date": profile.get("ipo"),
                "Market capitalization": profile.get("marketCapitalization"),
                "Shares outstanding": profile.get("shareOutstanding"),
                "Website": profile.get("weburl"),
            }
            sections.extend(("", "### Current company profile"))
            sections.extend(
                f"- {label}: {clean_text(value, 500)}"
                for label, value in fields.items()
                if value not in (None, "", 0)
            )

        peers = _fetch("stock/peers", {"symbol": symbol}, errors)
        if isinstance(peers, list) and peers:
            sections.extend(("", f"### Peers\n{', '.join(map(str, peers[:12]))}"))

        metric_payload = _fetch("stock/metric", {"symbol": symbol, "metric": "all"}, errors)
        metrics = metric_payload.get("metric", {}) if isinstance(metric_payload, dict) else {}
        metric_lines = [
            f"- {_METRICS[key]}: {metrics[key]}"
            for key in _METRICS
            if metrics.get(key) is not None
        ]
        if metric_lines:
            sections.extend(("", "### Current valuation and operating metrics", *metric_lines))
    else:
        sections.extend(
            (
                "",
                "Current profile, peer and metric snapshots are withheld because this is a "
                "historical analysis and Finnhub does not provide their as-of vintage.",
            )
        )

    earnings = _fetch("stock/earnings", {"symbol": symbol, "limit": 4}, errors)
    earnings_rows = [
        row
        for row in earnings or []
        if isinstance(row, dict) and (_as_date(row.get("period")) or cutoff) <= cutoff
    ] if isinstance(earnings, list) else []
    if earnings_rows:
        sections.extend(("", "### Earnings surprises available by the cutoff"))
        for row in earnings_rows[:4]:
            sections.append(
                f"- {row.get('period', 'Unknown period')}: actual EPS {row.get('actual')}, "
                f"estimate {row.get('estimate')}, surprise {row.get('surprisePercent')}%"
            )

    recommendations = _fetch("stock/recommendation", {"symbol": symbol}, errors)
    recommendation_rows = [
        row
        for row in recommendations or []
        if isinstance(row, dict) and (_as_date(row.get("period")) or cutoff) <= cutoff
    ] if isinstance(recommendations, list) else []
    if recommendation_rows:
        sections.extend(("", "### Analyst recommendation trends available by the cutoff"))
        for row in recommendation_rows[:6]:
            sections.append(
                f"- {row.get('period', 'Unknown period')}: strong buy {row.get('strongBuy')}, "
                f"buy {row.get('buy')}, hold {row.get('hold')}, sell {row.get('sell')}, "
                f"strong sell {row.get('strongSell')}"
            )

    filings = _fetch(
        "stock/filings",
        {"symbol": symbol, "from": (cutoff - timedelta(days=365)).isoformat(),
         "to": cutoff.isoformat()},
        errors,
    )
    filing_rows = [
        row
        for row in filings or []
        if isinstance(row, dict) and (_as_date(row.get("acceptedDate")) or cutoff) <= cutoff
    ] if isinstance(filings, list) else []
    if filing_rows:
        filing_rows.sort(key=lambda row: str(row.get("acceptedDate", "")), reverse=True)
        sections.extend(("", "### Recent SEC filing metadata available by the cutoff"))
        for row in filing_rows[:8]:
            sections.append(
                f"- {row.get('acceptedDate') or row.get('filedDate')}: "
                f"{row.get('form', 'Unknown form')} · {row.get('reportUrl') or row.get('filingUrl')}"
            )

    if len(sections) == 1 or (len(sections) == 3 and not live):
        if errors:
            raise errors[0]
        raise NoMarketDataError(ticker, symbol, "Finnhub returned no usable company intelligence")
    return "\n".join(sections)
