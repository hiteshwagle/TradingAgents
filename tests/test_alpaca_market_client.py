from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from tradingagents.dataflows.errors import VendorNotConfiguredError, VendorRateLimitError
from tradingagents.dataflows.vendors.alpaca.client import AlpacaMarketDataClient


class Response:
    def __init__(self, status, payload, headers=None):
        self.status_code, self.payload, self.headers = status, payload, headers or {}

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def client(responses, delays=None):
    delays = delays if delays is not None else []
    with patch.dict("os.environ", {"APCA_API_KEY_ID": "key", "APCA_API_SECRET_KEY": "secret"}):
        return AlpacaMarketDataClient(session=Session(responses), sleeper=delays.append)


def test_missing_credentials_and_access_denial_are_distinct():
    with patch.dict("os.environ", {}, clear=True), pytest.raises(VendorNotConfiguredError):
        AlpacaMarketDataClient(session=Session([]))
    api = client([Response(403, {})])
    with pytest.raises(VendorNotConfiguredError, match="403"):
        api.movers()


def test_rate_limit_honors_retry_after_and_is_bounded():
    delays = []
    api = client([Response(429, {}, {"Retry-After": "2"}), Response(200, {"gainers": []})], delays)
    assert api.movers() == {"gainers": []}
    assert delays == [2]
    failing = client([requests.ConnectionError(), requests.ConnectionError(), requests.ConnectionError()])
    with pytest.raises(VendorRateLimitError):
        failing.movers()
    assert len(failing.session.calls) == 3


def test_parameter_validation_happens_before_request():
    api = client([])
    for value in (0, 51):
        with pytest.raises(ValueError):
            api.movers(value)
    with pytest.raises(ValueError):
        api.most_actives("invalid")
    assert api.session.calls == []


def test_snapshots_support_actual_top_level_contract_and_batching():
    api = client([Response(200, {"AAA": {"latestTrade": {"p": 1}}}),
                  Response(200, {"BBB": {"latestTrade": {"p": 2}}})])
    result = api.snapshots(["AAA", "BBB"], "iex", batch_size=1)
    assert list(result) == ["AAA", "BBB"]
    assert api.session.calls[0][1]["params"]["feed"] == "iex"


def test_bars_pagination_preserves_rows_and_exact_window():
    api = client([Response(200, {"bars": {"AAA": [{"v": 1}]}, "next_page_token": "next"}),
                  Response(200, {"bars": {"AAA": [{"v": 2}]}})])
    result = api.bars(["AAA"], start="2026-09-01T00:00:00Z", end="2026-10-01T00:00:00Z")
    assert result["AAA"] == [{"v": 1}, {"v": 2}]
    assert api.session.calls[1][1]["params"]["page_token"] == "next"
