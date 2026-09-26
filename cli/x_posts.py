"""Command-line access to the TradingAgents X recent-Post client."""

from __future__ import annotations

import argparse
import json

from tradingagents.dataflows.vendors.x_posts import XAPIError, search_symbol_posts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search recent X Posts for a market symbol")
    parser.add_argument("symbol", help="Ticker or crypto symbol, e.g. NVDA or BTC-USD")
    parser.add_argument("--company", help="Optional company/instrument name")
    parser.add_argument("--limit", type=int, help="Maximum Posts returned (10-100; default 20)")
    parser.add_argument("--start-time", help="Optional ISO-8601 UTC start time")
    parser.add_argument("--end-time", help="Optional ISO-8601 UTC end time")
    parser.add_argument("--no-cache", action="store_true", help="Bypass the local result cache")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = search_symbol_posts(
            args.symbol,
            args.company,
            limit=args.limit,
            start_time=args.start_time,
            end_time=args.end_time,
            use_cache=not args.no_cache,
        )
    except (XAPIError, ValueError) as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "error": str(exc)}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
