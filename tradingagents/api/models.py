"""Request and response schemas for the TradingAgents HTTP API."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from tradingagents.dataflows.date_window import get_current_date
from tradingagents.dataflows.symbols import normalize_symbol, safe_ticker_component
from tradingagents.portfolio import PortfolioContext

AnalystName = Literal["market", "social", "news", "fundamentals"]
AssetType = Literal["stock", "crypto"]


class AnalysisOptions(BaseModel):
    """Safe per-run options; secrets and backend URLs remain server-owned."""

    max_debate_rounds: int | None = Field(default=None, ge=1, le=10)
    max_risk_rounds: int | None = Field(default=None, ge=1, le=10)
    output_language: str | None = Field(default=None, min_length=2, max_length=50)
    checkpoint_enabled: bool | None = None
    save_reports: bool = True


class AnalysisRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    trade_date: date = Field(default_factory=lambda: date.fromisoformat(get_current_date()))
    asset_type: AssetType = "stock"
    analysts: list[AnalystName] = Field(
        default_factory=lambda: ["market", "social", "news", "fundamentals"],
        min_length=1,
    )
    portfolio: PortfolioContext | None = None
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)

    @field_validator("symbol")
    @classmethod
    def canonical_symbol(cls, value: str) -> str:
        symbol = normalize_symbol(value)
        return safe_ticker_component(symbol)

    @field_validator("trade_date")
    @classmethod
    def no_future_date(cls, value: date) -> date:
        if value > date.fromisoformat(get_current_date()):
            raise ValueError("trade_date cannot be in the future")
        return value

    @field_validator("analysts")
    @classmethod
    def unique_analysts(cls, value: list[AnalystName]) -> list[AnalystName]:
        if len(value) != len(set(value)):
            raise ValueError("analysts must not contain duplicates")
        return value


class TradeRecommendation(BaseModel):
    rating: str
    action: Literal["Buy", "Hold", "Sell"] | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    position_sizing: str | None = None
    price_target: float | None = None
    time_horizon: str | None = None


class AnalysisResult(BaseModel):
    schema_version: str = "1.0"
    symbol: str
    trade_date: date
    asset_type: AssetType
    analysts: list[AnalystName]
    recommendation: TradeRecommendation
    final_decision: str
    investment_plan: str = ""
    trader_plan: str = ""
    reports: dict[str, str] = Field(default_factory=dict)
    debates: dict[str, str] = Field(default_factory=dict)
    source_urls: list[str] = Field(default_factory=list)
    report_path: str | None = None


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobEvent(BaseModel):
    sequence: int
    timestamp: datetime
    status: JobStatus
    message: str


class JobError(BaseModel):
    code: str
    message: str


class AnalysisJobResponse(BaseModel):
    analysis_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    cancel_requested: bool = False
    result: AnalysisResult | None = None
    error: JobError | None = None


class JobEventsResponse(BaseModel):
    analysis_id: str
    events: list[JobEvent]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "tradingagents-api"
    version: str
    jobs: dict[str, int]


class CapabilitiesResponse(BaseModel):
    schema_version: str = "1.0"
    analysts: list[str]
    asset_types: list[str]
    ratings: list[str]
    supports_portfolio_context: bool = True
    supports_checkpointing: bool = True
    executes_trades: bool = False
