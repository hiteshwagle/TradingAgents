"""Adapter from the API schema to the existing TradingAgents graph."""

from __future__ import annotations

import re
from copy import deepcopy

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

from .models import AnalysisRequest, AnalysisResult, TradeRecommendation

_URL_RE = re.compile(r"https?://[^\s\])}>\"]+")


def _field(markdown: str, label: str) -> str | None:
    match = re.search(
        rf"(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*:\s*(.+)$",
        markdown or "",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return None
    value = match.group(1).strip().strip("*")
    return None if value.lower() in {"", "none", "not provided", "n/a"} else value


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.fullmatch(r"[$£€¥]?\s*([+-]?[0-9][0-9,]*(?:\.[0-9]+)?)", value)
    return float(match.group(1).replace(",", "")) if match else None


def _source_urls(values: list[str]) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for value in values:
        for match in _URL_RE.findall(value or ""):
            url = match.rstrip(".,;:")
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def build_result(request: AnalysisRequest, state: dict, signal: str, report_path=None) -> AnalysisResult:
    trader_plan = str(state.get("trader_investment_plan") or "")
    final_decision = str(state.get("final_trade_decision") or "")
    action = _field(trader_plan, "Action")
    if action:
        action = action.capitalize()
    if action not in {"Buy", "Hold", "Sell"}:
        action = None

    reports = {
        "market": str(state.get("market_report") or ""),
        "sentiment": str(state.get("sentiment_report") or ""),
        "news": str(state.get("news_report") or ""),
        "fundamentals": str(state.get("fundamentals_report") or ""),
        "macro": str(state.get("macro_report") or ""),
    }
    investment_debate = state.get("investment_debate_state") or {}
    risk_debate = state.get("risk_debate_state") or {}
    debates = {
        "investment": str(investment_debate.get("history") or ""),
        "investment_bull": str(investment_debate.get("bull_history") or ""),
        "investment_bear": str(investment_debate.get("bear_history") or ""),
        "investment_judgement": str(investment_debate.get("judge_decision") or ""),
        "risk": str(risk_debate.get("history") or ""),
        "risk_aggressive": str(risk_debate.get("aggressive_history") or ""),
        "risk_conservative": str(risk_debate.get("conservative_history") or ""),
        "risk_neutral": str(risk_debate.get("neutral_history") or ""),
        "risk_judgement": str(risk_debate.get("judge_decision") or ""),
    }

    recommendation = TradeRecommendation(
        rating=signal,
        action=action,
        entry_price=_number(_field(trader_plan, "Entry Price")),
        stop_loss=_number(_field(trader_plan, "Stop Loss")),
        position_sizing=_field(trader_plan, "Position Sizing"),
        price_target=_number(_field(final_decision, "Price Target")),
        time_horizon=_field(final_decision, "Time Horizon"),
    )
    text_values = [*reports.values(), *debates.values(), trader_plan, final_decision]
    return AnalysisResult(
        symbol=request.symbol,
        trade_date=request.trade_date,
        asset_type=request.asset_type,
        analysts=request.analysts,
        recommendation=recommendation,
        final_decision=final_decision,
        investment_plan=str(state.get("investment_plan") or ""),
        trader_plan=trader_plan,
        reports=reports,
        debates=debates,
        source_urls=_source_urls(text_values),
        report_path=str(report_path) if report_path else None,
    )


class AnalysisRunner:
    """Run one API request using the package's normal graph entry point."""

    def run(self, request: AnalysisRequest) -> AnalysisResult:
        config = deepcopy(DEFAULT_CONFIG)
        options = request.options
        if options.max_debate_rounds is not None:
            config["max_debate_rounds"] = options.max_debate_rounds
        if options.max_risk_rounds is not None:
            config["max_risk_discuss_rounds"] = options.max_risk_rounds
        if options.output_language is not None:
            config["output_language"] = options.output_language
        if options.checkpoint_enabled is not None:
            config["checkpoint_enabled"] = options.checkpoint_enabled
        if options.x_posts_mode is not None:
            config["x_posts_mode"] = options.x_posts_mode

        graph = TradingAgentsGraph(
            selected_analysts=request.analysts,
            config=config,
        )
        state, signal = graph.propagate(
            request.symbol,
            request.trade_date.isoformat(),
            asset_type=request.asset_type,
            portfolio=request.portfolio,
        )
        report_path = None
        if options.save_reports:
            report_path = graph.save_reports(state, request.symbol)
        return build_result(request, state, signal, report_path)
