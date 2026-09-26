"""FastAPI application exposing TradingAgents analysis as JSON."""

from __future__ import annotations

import hmac
import os
from importlib.metadata import PackageNotFoundError, version

from fastapi import Depends, FastAPI, Header, HTTPException, status

from tradingagents.agents.rating import RATINGS_5_TIER

from .jobs import AnalysisJobManager, JobCapacityError
from .models import (
    AnalysisJobResponse,
    AnalysisRequest,
    CapabilitiesResponse,
    HealthResponse,
    JobEventsResponse,
)


def _package_version() -> str:
    try:
        return version("tradingagents")
    except PackageNotFoundError:
        return "0.5.1"


def create_app(
    job_manager: AnalysisJobManager | None = None,
    api_key: str | None = None,
) -> FastAPI:
    manager = job_manager or AnalysisJobManager()
    configured_key = api_key if api_key is not None else os.getenv("TRADINGAGENTS_API_KEY", "")
    application = FastAPI(
        title="TradingAgents API",
        version=_package_version(),
        description="Asynchronous research and decision API. It never executes broker trades.",
    )
    application.state.job_manager = manager

    def authorize(
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> None:
        if not configured_key:
            return
        bearer = None
        if authorization and authorization.lower().startswith("bearer "):
            bearer = authorization[7:].strip()
        supplied = x_api_key or bearer or ""
        if not hmac.compare_digest(supplied, configured_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @application.get("/v1/health", response_model=HealthResponse, tags=["service"])
    def health() -> HealthResponse:
        return HealthResponse(version=_package_version(), jobs=manager.counts())

    @application.get(
        "/v1/capabilities",
        response_model=CapabilitiesResponse,
        dependencies=[Depends(authorize)],
        tags=["service"],
    )
    def capabilities() -> CapabilitiesResponse:
        return CapabilitiesResponse(
            analysts=["market", "social", "news", "fundamentals"],
            asset_types=["stock", "crypto"],
            ratings=list(RATINGS_5_TIER),
        )

    @application.post(
        "/v1/analyses",
        response_model=AnalysisJobResponse,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(authorize)],
        tags=["analysis"],
    )
    def create_analysis(request: AnalysisRequest) -> AnalysisJobResponse:
        try:
            return manager.submit(request)
        except JobCapacityError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    @application.get(
        "/v1/analyses/{analysis_id}",
        response_model=AnalysisJobResponse,
        dependencies=[Depends(authorize)],
        tags=["analysis"],
    )
    def get_analysis(analysis_id: str) -> AnalysisJobResponse:
        response = manager.get(analysis_id)
        if response is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
        return response

    @application.get(
        "/v1/analyses/{analysis_id}/events",
        response_model=JobEventsResponse,
        dependencies=[Depends(authorize)],
        tags=["analysis"],
    )
    def get_analysis_events(analysis_id: str) -> JobEventsResponse:
        response = manager.events(analysis_id)
        if response is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
        return response

    @application.post(
        "/v1/analyses/{analysis_id}/cancel",
        response_model=AnalysisJobResponse,
        dependencies=[Depends(authorize)],
        tags=["analysis"],
    )
    def cancel_analysis(analysis_id: str) -> AnalysisJobResponse:
        response = manager.cancel(analysis_id)
        if response is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
        return response

    return application


app = create_app()
