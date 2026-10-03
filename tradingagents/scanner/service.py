"""Deterministic live US-equity discovery with transparent scoring."""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from tradingagents.dataflows.vendors.alpaca.client import AlpacaMarketDataClient


class HistoricalScannerUnsupportedError(ValueError):
    pass


@dataclass
class ScannerConfig:
    feed: str | None = None
    movers_top: int = 20
    most_active_top: int = 50
    news_lookback_hours: int = 6
    news_limit: int = 50
    rvol_lookback_sessions: int = 20
    max_candidates_for_bars: int = 50
    top_n: int = 20
    min_price: float = 2.0
    min_dollar_volume: float = 5_000_000
    max_spread_pct: float = 1.0

    def __post_init__(self):
        if self.feed not in {None, "iex", "sip", "delayed_sip"}:
            raise ValueError("Unsupported Alpaca feed")
        if not 1 <= self.top_n <= 50 or not 1 <= self.max_candidates_for_bars <= 100:
            raise ValueError("Invalid scanner result limits")


@dataclass
class Candidate:
    symbol: str
    discovery_sources: list[str] = field(default_factory=list)
    direction: str = "unknown"
    price_change_pct: float | None = None
    price: float | None = None
    volume: float | None = None
    dollar_volume: float | None = None
    relative_volume: float | None = None
    spread_pct: float | None = None
    news_count: int = 0
    score: float | None = None
    score_components: dict[str, float] = field(default_factory=dict)
    data_completeness: float = 0
    data_feed: str | None = None
    as_of: str | None = None
    warnings: list[str] = field(default_factory=list)
    disqualified_reasons: list[str] = field(default_factory=list)


def finite(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def ticker(value):
    value = str(value or "").strip().upper()
    return value if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", value) else None


class MarketScanner:
    def __init__(self, client=None, config=None, now=None):
        self.client = client or AlpacaMarketDataClient()
        self.config = config or ScannerConfig()
        self.now = now or (lambda: datetime.now(timezone.utc))

    def scan(self, scan_date=None):
        now = self.now()
        if now.tzinfo is None:
            raise ValueError("Scanner clock must be timezone-aware")
        if scan_date is not None and date.fromisoformat(str(scan_date)) != now.astimezone(ZoneInfo("America/New_York")).date():
            raise HistoricalScannerUnsupportedError("Live scanner cannot reconstruct a historical ranking")
        candidates, failed, warnings = {}, {}, []

        def candidate(raw, source):
            sym = ticker(raw.get("symbol"))
            if not sym:
                return None
            item = candidates.setdefault(sym, Candidate(sym))
            if source not in item.discovery_sources:
                item.discovery_sources.append(source)
            return item

        try:
            movers = self.client.movers(self.config.movers_top)
            for label in ("gainers", "losers"):
                for raw in movers.get(label, []):
                    item = candidate(raw, "mover")
                    if item:
                        item.direction = "gainer" if label == "gainers" else "loser"
                        item.price_change_pct = finite(raw.get("percent_change"))
                        item.price = finite(raw.get("price"))
        except Exception as exc:
            failed["movers"] = type(exc).__name__
        for by in ("volume", "trades"):
            try:
                payload = self.client.most_actives(by, self.config.most_active_top)
                for rank, raw in enumerate(payload.get("most_actives", []), 1):
                    item = candidate(raw, "most_active_" + by)
                    if item:
                        value = finite(raw.get("volume"))
                        if value is not None and value >= 0:
                            item.volume = max(item.volume or 0, value)
                        item.score_components["activity"] = max(
                            item.score_components.get("activity", 0),
                            1 - (rank - 1) / max(self.config.most_active_top, 1))
            except Exception as exc:
                failed["most_active_" + by] = type(exc).__name__
        try:
            stories = self.client.news(start=now - timedelta(hours=self.config.news_lookback_hours),
                                       end=now, limit=self.config.news_limit)
            seen = set()
            for story in stories:
                identity = story.get("id") or story.get("url") or story.get("headline")
                if identity in seen:
                    continue
                seen.add(identity)
                story_symbols = [ticker(value) for value in story.get("symbols") or []]
                story_symbols = [value for value in story_symbols if value]
                for sym in story_symbols:
                    item = candidate({"symbol": sym}, "news")
                    if item:
                        item.news_count += 1
                        if len(story_symbols) > 1:
                            item.warnings.append(
                                "multi-symbol news tag is discovery metadata, not equal materiality"
                            )
        except Exception as exc:
            failed["news"] = type(exc).__name__
        if not candidates:
            raise ValueError(f"No scanner candidates; failed sources: {failed}")
        snapshots = self.client.snapshots(list(candidates), self.config.feed)
        for sym, item in candidates.items():
            raw = snapshots.get(sym)
            if not raw:
                item.disqualified_reasons.append("missing snapshot")
                continue
            trade, quote = raw.get("latestTrade") or {}, raw.get("latestQuote") or {}
            daily, previous = raw.get("dailyBar") or {}, raw.get("prevDailyBar") or {}
            item.price = finite(trade.get("p")) or finite(daily.get("c"))
            item.volume = finite(daily.get("v"))
            previous_close = finite(previous.get("c"))
            if item.price_change_pct is None and item.price and previous_close:
                item.price_change_pct = (item.price / previous_close - 1) * 100
            bid, ask = finite(quote.get("bp")), finite(quote.get("ap"))
            if bid and ask and ask >= bid:
                item.spread_pct = (ask - bid) / ((ask + bid) / 2) * 100
            item.dollar_volume = item.price * item.volume if item.price and item.volume is not None else None
            item.as_of = trade.get("t") or daily.get("t")
            item.data_feed = self.config.feed or "entitled_default"
            if item.price is None or item.price < self.config.min_price:
                item.disqualified_reasons.append("price missing or below minimum")
            if item.dollar_volume is None or item.dollar_volume < self.config.min_dollar_volume:
                item.disqualified_reasons.append("observed dollar volume below minimum")
            if item.spread_pct is not None and item.spread_pct > self.config.max_spread_pct:
                item.disqualified_reasons.append("spread above maximum")
            if item.data_feed != "sip" and any(s.startswith("most_active") or s == "mover" for s in item.discovery_sources):
                item.warnings.append("SIP screener activity and non-SIP snapshot/bar volume are not comparable")
        shortlist = [c for c in candidates.values() if not c.disqualified_reasons]
        shortlist.sort(key=lambda c: (c.dollar_volume or 0), reverse=True)
        shortlist = shortlist[:self.config.max_candidates_for_bars]
        if shortlist:
            bars = self.client.bars([c.symbol for c in shortlist],
                                    start=(now - timedelta(days=self.config.rvol_lookback_sessions * 2)).isoformat(),
                                    end=now.isoformat(), feed=self.config.feed)
            for item in shortlist:
                complete = [finite(row.get("v")) for row in bars.get(item.symbol, [])[:-1]]
                complete = [v for v in complete if v is not None and v >= 0][-self.config.rvol_lookback_sessions:]
                if complete and sum(complete) > 0 and item.volume is not None:
                    item.relative_volume = item.volume / (sum(complete) / len(complete))
                else:
                    item.warnings.append("relative volume unavailable")
        weights = {"movement": .30, "rvol": .35, "activity": .20, "news": .15}
        for item in shortlist:
            components = dict(item.score_components)
            if item.price_change_pct is not None:
                components["movement"] = min(abs(item.price_change_pct) / 10, 1)
            if item.relative_volume is not None:
                components["rvol"] = min(item.relative_volume / 5, 1)
            if item.news_count:
                components["news"] = min(item.news_count / 5, 1)
            present = sum(weights[k] for k in components if k in weights)
            item.score = round(100 * sum(components[k] * weights[k] for k in components if k in weights) / present, 2) if present else None
            item.score_components = {k: round(v, 4) for k, v in components.items()}
            item.data_completeness = round(present, 2)
        shortlist.sort(key=lambda c: (c.score is not None, c.score or 0, c.data_completeness), reverse=True)
        ny = now.astimezone(ZoneInfo("America/New_York"))
        session = "regular" if ny.weekday() < 5 and (9, 30) <= (ny.hour, ny.minute) < (16, 0) else "outside_regular_hours"
        if session != "regular":
            warnings.append("mover and activity rankings may describe the prior market session")
            for item in shortlist:
                if any(source == "mover" or source.startswith("most_active") for source in item.discovery_sources):
                    item.warnings.append("ranking observed outside regular market hours")
        return {"schema_version": "1.0", "as_of": now.astimezone(timezone.utc).isoformat(),
                "market": "US", "session": session, "feed": self.config.feed or "entitled_default",
                "candidates": [asdict(c) for c in shortlist[:self.config.top_n]],
                "excluded": [asdict(c) for c in candidates.values() if c.disqualified_reasons],
                "metadata": {"discovered": len(candidates), "eligible": len(shortlist),
                             "failed_sources": failed, "warnings": warnings}}
