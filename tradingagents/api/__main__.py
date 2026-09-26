"""Command-line entry point for the TradingAgents API."""

from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    host = os.getenv("TRADINGAGENTS_API_HOST", "127.0.0.1")
    port = int(os.getenv("TRADINGAGENTS_API_PORT", "8000"))
    if host not in {"127.0.0.1", "localhost", "::1"} and not os.getenv("TRADINGAGENTS_API_KEY"):
        raise SystemExit("TRADINGAGENTS_API_KEY is required for a non-loopback API host")
    uvicorn.run("tradingagents.api.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
