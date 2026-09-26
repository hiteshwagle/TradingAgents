"""Versioned HTTP API for TradingAgents analysis.

Import concrete modules such as :mod:`tradingagents.api.app` explicitly. Keeping
this package initializer lightweight means schema/runner imports do not create a
background executor or require the optional web dependencies.
"""
