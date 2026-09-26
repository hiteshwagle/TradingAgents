from __future__ import annotations

import time
from datetime import date

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app
from tradingagents.api.jobs import AnalysisJobManager
from tradingagents.api.models import AnalysisRequest, AnalysisResult, TradeRecommendation
from tradingagents.api.runner import build_result


class FakeRunner:
    def run(self, request):
        return AnalysisResult(
            symbol=request.symbol,
            trade_date=request.trade_date,
            asset_type=request.asset_type,
            analysts=request.analysts,
            recommendation=TradeRecommendation(rating="Buy", action="Buy"),
            final_decision="**Rating**: Buy",
        )


def _client(api_key="secret"):
    manager = AnalysisJobManager(runner=FakeRunner(), max_workers=1, max_jobs=10)
    return TestClient(create_app(manager, api_key=api_key)), manager


def test_api_requires_configured_key():
    client, manager = _client()
    try:
        assert client.get("/v1/capabilities").status_code == 401
        assert client.get("/v1/capabilities", headers={"X-API-Key": "secret"}).status_code == 200
        assert client.get("/v1/health").status_code == 200
    finally:
        manager.shutdown()


def test_analysis_job_returns_structured_json():
    client, manager = _client()
    headers = {"Authorization": "Bearer secret"}
    try:
        created = client.post(
            "/v1/analyses",
            headers=headers,
            json={"symbol": "aapl", "trade_date": "2026-09-01", "analysts": ["market"]},
        )
        assert created.status_code == 202
        analysis_id = created.json()["analysis_id"]

        payload = None
        for _ in range(100):
            payload = client.get(f"/v1/analyses/{analysis_id}", headers=headers).json()
            if payload["status"] == "completed":
                break
            time.sleep(0.01)

        assert payload["result"]["symbol"] == "AAPL"
        assert payload["result"]["recommendation"]["rating"] == "Buy"
        events = client.get(f"/v1/analyses/{analysis_id}/events", headers=headers).json()
        assert events["events"][-1]["status"] == "completed"
    finally:
        manager.shutdown()


def test_build_result_extracts_execution_fields_and_sources():
    request = AnalysisRequest(symbol="AAPL", trade_date=date(2026, 9, 1), analysts=["market"])
    state = {
        "market_report": "Evidence: https://example.com/aapl",
        "trader_investment_plan": """**Action**: Buy
**Entry Price**: 220.50
**Stop Loss**: 210
**Position Sizing**: 5% of portfolio""",
        "final_trade_decision": """**Rating**: Buy
**Price Target**: 250
**Time Horizon**: 3-6 months""",
    }
    result = build_result(request, state, "Buy")
    assert result.recommendation.action == "Buy"
    assert result.recommendation.entry_price == 220.5
    assert result.recommendation.stop_loss == 210
    assert result.recommendation.price_target == 250
    assert result.source_urls == ["https://example.com/aapl"]
