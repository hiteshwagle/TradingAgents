"""Dedicated macro analyst grounded in FRED, news, and event probabilities."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.context import (
    get_instrument_context_from_state,
    get_language_instruction,
)
from tradingagents.agents.tools import (
    get_global_news,
    get_macro_indicators,
    get_macro_release_calendar,
    get_news,
    get_prediction_markets,
)

# Asset news supplies symbol-specific macro context; the remaining tools cover
# the same broad sources as AlpacaTradingAgent's former standalone Macro Agent.
TOOLS = (
    get_macro_indicators,
    get_macro_release_calendar,
    get_global_news,
    get_prediction_markets,
    get_news,
)


def create_macro_analyst(llm):
    """Create an analyst for rates, inflation, growth, liquidity, and events."""

    def macro_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        system_message = (
            "You are a macroeconomic analyst supporting a multi-agent trading team. "
            "Assess the macro environment as of the supplied analysis date and explain "
            "how it affects the specified instrument over the expected trading horizon. "
            "Ground the report in tool evidence rather than general model knowledge. "
            "Use get_macro_indicators for the most relevant FRED series, including policy "
            "rates, inflation, labor, growth, Treasury yields or the yield curve, market "
            "volatility, dollar strength, and liquidity when relevant. Call "
            "get_macro_release_calendar to identify scheduled data-release risk; use those "
            "dates for timing and risk controls, never as a directional signal. Use "
            "get_global_news for central-bank, fiscal, geopolitical, and economic developments; "
            "get_prediction_markets for forward-looking event probabilities; and get_news "
            "when symbol-specific news is needed to connect the macro regime to the asset. "
            "For crypto, explicitly assess global liquidity, real yields, dollar strength, "
            "risk appetite, regulation, and correlation with risk assets. For equities, "
            "explain sector, valuation, financing-cost, currency, and demand implications. "
            "Separate observed facts from inference, mention conflicting evidence and data "
            "limitations, and do not fabricate unavailable releases. Finish with a Markdown "
            "table covering factor, latest evidence, direction, instrument impact, and risk."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant collaborating with other analysts. "
                    "Use the available tools before concluding; another agent makes the "
                    "trade decision. You have access to: {tool_names}. Today's date is "
                    "{current_date}; treat it as now and never use information published "
                    "after it. {instrument_context}\n{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(
            tool_names=", ".join(tool.name for tool in TOOLS),
            current_date=current_date,
            instrument_context=instrument_context,
            system_message=system_message,
        )

        result = (prompt | llm.bind_tools(TOOLS)).invoke(state["messages"])
        report = result.content if not result.tool_calls else ""
        return {"messages": [result], "macro_report": report, "sender": "Macro Analyst"}

    return macro_analyst_node
