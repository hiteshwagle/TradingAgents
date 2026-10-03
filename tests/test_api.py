from __future__ import annotations

import tempfile
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
        capabilities = client.get(
            "/v1/capabilities", headers={"X-API-Key": "secret"}
        )
        assert capabilities.status_code == 200
        assert "macro" in capabilities.json()["analysts"]
        assert client.get("/v1/health").status_code == 200
    finally:
        manager.shutdown()


def test_blank_job_limit_environment_values_use_defaults(monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_API_WORKERS", "")
    monkeypatch.setenv("TRADINGAGENTS_API_MAX_JOBS", "")
    manager = AnalysisJobManager(runner=FakeRunner())
    try:
        assert manager.max_jobs == 500
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


def test_completed_job_survives_restart():
    with tempfile.TemporaryDirectory() as directory:
        path = f"{directory}/jobs.sqlite3"
        manager = AnalysisJobManager(
            runner=FakeRunner(), max_workers=1, max_jobs=10, persistence_path=path
        )
        job = manager.submit(AnalysisRequest(symbol="AAPL", trade_date=date(2026, 9, 1)))
        for _ in range(100):
            response = manager.get(job.analysis_id)
            if response.status.value == "completed":
                break
            time.sleep(0.01)
        manager.shutdown()

        restarted = AnalysisJobManager(
            runner=FakeRunner(), max_workers=1, max_jobs=10, persistence_path=path
        )
        try:
            restored = restarted.get(job.analysis_id)
            assert restored.status.value == "completed"
            assert restored.result.symbol == "AAPL"
        finally:
            restarted.shutdown()


def test_scanner_endpoint_requires_auth_and_validates_bounds(monkeypatch):
    client, manager = _client()
    monkeypatch.setattr(
        "tradingagents.scanner.MarketScanner.scan",
        lambda self: {"schema_version": "1.0", "candidates": []},
    )
    try:
        assert client.post("/v1/scanner/scan", json={"top_n": 5}).status_code == 401
        response = client.post(
            "/v1/scanner/scan", headers={"X-API-Key": "secret"}, json={"top_n": 5}
        )
        assert response.status_code == 200
        assert response.json()["schema_version"] == "1.0"
        invalid = client.post(
            "/v1/scanner/scan", headers={"X-API-Key": "secret"}, json={"top_n": 500}
        )
        assert invalid.status_code == 422
    finally:
        manager.shutdown()


def test_api_accepts_macro_as_a_dedicated_analyst():
    request = AnalysisRequest(
        symbol="AAPL",
        trade_date=date(2026, 9, 1),
        analysts=["macro"],
    )
    assert request.analysts == ["macro"]


def test_api_accepts_bounded_x_mode_for_historical_validation():
    request = AnalysisRequest(
        symbol="AAPL", trade_date=date(2026, 9, 1), analysts=["social"],
        options={"x_posts_mode": "disabled"},
    )
    assert request.options.x_posts_mode == "disabled"


def test_build_result_extracts_execution_fields_and_sources():
    request = AnalysisRequest(symbol="AAPL", trade_date=date(2026, 9, 1), analysts=["market"])
    state = {
        "market_report": "Evidence: https://example.com/aapl",
        "macro_report": "Macro evidence: https://example.com/macro",
        "investment_debate_state": {
            "history": "combined investment debate",
            "bull_history": "bull case",
            "bear_history": "bear case",
            "judge_decision": "research judgement",
        },
        "risk_debate_state": {
            "history": "combined risk debate",
            "aggressive_history": "aggressive case",
            "conservative_history": "conservative case",
            "neutral_history": "neutral case",
            "judge_decision": "risk judgement",
        },
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
    assert result.debates["investment_bull"] == "bull case"
    assert result.debates["risk_conservative"] == "conservative case"
    assert result.reports["macro"].startswith("Macro evidence")
    assert result.source_urls == ["https://example.com/aapl", "https://example.com/macro"]
