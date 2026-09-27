"""Every direct project-owned HTTPS client uses Certifi explicitly."""

from unittest import mock

import certifi

from tradingagents.agents import post_screen
from tradingagents.dataflows import net
from tradingagents.dataflows.vendors import polymarket, sec_edgar


def _response(payload=None, status_code=200):
    response = mock.Mock(status_code=status_code)
    response.json.return_value = payload or {}
    return response


def test_shared_get_and_reachability_use_certifi():
    response = _response()
    with mock.patch.object(net.requests, "get", return_value=response) as get:
        net.get_scrubbed("https://example.test", params={}, timeout=1, secret="")
    assert get.call_args.kwargs["verify"] == certifi.where()

    with mock.patch.object(net.requests, "head", return_value=response) as head:
        assert net.vendor_reachable("https://example.test") is True
    assert head.call_args.kwargs["verify"] == certifi.where()


def test_polymarket_uses_certifi():
    with mock.patch.object(polymarket.requests, "get", return_value=_response()) as get:
        polymarket._request("public-search", {"q": "rates"})
    assert get.call_args.kwargs["verify"] == certifi.where()


def test_sec_edgar_uses_certifi():
    with mock.patch.object(sec_edgar.requests, "get", return_value=_response()) as get:
        sec_edgar._fetch_json("https://data.sec.gov/example.json")
    assert get.call_args.kwargs["verify"] == certifi.where()


def test_jev_uses_certifi(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    response = _response(
        {
            "answers": {
                "relevant": {"type": "boolean", "value": True},
            }
        }
    )
    questions = {"relevant": {"type": "boolean", "question": "Relevant?"}}
    with mock.patch.object(post_screen.requests, "post", return_value=response) as post:
        post_screen.system_one({"text": "AAPL"}, questions)
    assert post.call_args.kwargs["verify"] == certifi.where()
