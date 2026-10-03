"""Shared, bounded Alpaca Market Data REST client."""
from __future__ import annotations

import os
import random
import time
from datetime import datetime

import certifi
import requests

from tradingagents.dataflows.errors import (
    VendorError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)


class AlpacaMarketDataClient:
    def __init__(self, *, session=None, timeout=30, sleeper=time.sleep):
        key = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")
        secret = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")
        if not key or not secret:
            raise VendorNotConfiguredError("Alpaca Market Data credentials are missing")
        self.session = session or requests.Session()
        self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.timeout, self.sleep = timeout, sleeper
        self.base = "https://data.alpaca.markets"

    def get(self, path, params=None):
        for attempt in range(3):
            try:
                response = self.session.get(self.base + path, headers=self.headers, params=params,
                                            timeout=self.timeout, verify=certifi.where())
            except requests.RequestException:
                if attempt == 2:
                    raise VendorRateLimitError("Alpaca Market Data request failed") from None
                self.sleep(.5 * 2**attempt)
                continue
            if response.status_code in {401, 403}:
                raise VendorNotConfiguredError(f"Alpaca Market Data access denied (HTTP {response.status_code})")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 2:
                    raise VendorRateLimitError(f"Alpaca Market Data unavailable (HTTP {response.status_code})")
                retry = response.headers.get("Retry-After")
                try:
                    delay = min(float(retry), 30) if retry else .5 * 2**attempt + random.random() / 4
                except ValueError:
                    delay = .5 * 2**attempt
                self.sleep(delay)
                continue
            if response.status_code >= 400:
                raise VendorError(f"Alpaca Market Data rejected request (HTTP {response.status_code})")
            try:
                data = response.json()
            except (ValueError, requests.JSONDecodeError):
                raise VendorRateLimitError("Alpaca Market Data returned invalid JSON") from None
            if not isinstance(data, dict):
                raise VendorRateLimitError("Alpaca Market Data returned an invalid object")
            return data
        raise VendorRateLimitError("Alpaca Market Data request failed")

    @staticmethod
    def top(value, maximum):
        value = int(value)
        if not 1 <= value <= maximum:
            raise ValueError(f"top must be between 1 and {maximum}")
        return value

    def movers(self, top=20):
        return self.get("/v1beta1/screener/stocks/movers", {"top": self.top(top, 50)})

    def most_actives(self, by="volume", top=50):
        if by not in {"volume", "trades"}:
            raise ValueError("by must be volume or trades")
        return self.get("/v1beta1/screener/stocks/most-actives",
                        {"by": by, "top": self.top(top, 100)})

    def snapshots(self, symbols, feed=None, batch_size=50):
        symbols = list(dict.fromkeys(symbols))
        if not symbols or len(symbols) > 500:
            raise ValueError("snapshots require 1-500 bounded symbols")
        output = {}
        for offset in range(0, len(symbols), batch_size):
            params = {"symbols": ",".join(symbols[offset:offset + batch_size])}
            if feed:
                params["feed"] = feed
            payload = self.get("/v2/stocks/snapshots", params)
            snapshots = payload.get("snapshots") if "snapshots" in payload else payload
            if not isinstance(snapshots, dict):
                raise VendorRateLimitError("Alpaca snapshots response is invalid")
            output.update(snapshots)
        return output

    def bars(self, symbols, *, start, end, timeframe="1Day", feed=None, adjustment="all"):
        symbols = list(dict.fromkeys(symbols))
        if not symbols or len(symbols) > 200:
            raise ValueError("bars require 1-200 bounded symbols")
        params = {"symbols": ",".join(symbols), "start": start, "end": end,
                  "timeframe": timeframe, "adjustment": adjustment, "limit": 10000,
                  "sort": "asc"}
        if feed:
            params["feed"] = feed
        output, token = {}, None
        for _ in range(20):
            if token:
                params["page_token"] = token
            payload = self.get("/v2/stocks/bars", params)
            for ticker, rows in payload.get("bars", {}).items():
                output.setdefault(ticker, []).extend(rows)
            token = payload.get("next_page_token")
            if not token:
                return output
        raise VendorRateLimitError("Alpaca bars pagination exceeded the safety limit")

    def news(self, *, symbols=None, start=None, end=None, limit=50):
        if not 1 <= int(limit) <= 50:
            raise ValueError("news limit must be between 1 and 50")
        params = {"limit": int(limit), "sort": "desc", "include_content": "false"}
        if symbols:
            params["symbols"] = ",".join(symbols)
        if start:
            params["start"] = start.isoformat() if isinstance(start, datetime) else start
        if end:
            params["end"] = end.isoformat() if isinstance(end, datetime) else end
        return self.get("/v1beta1/news", params).get("news", [])
