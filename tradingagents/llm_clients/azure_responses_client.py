"""Azure OpenAI client pinned to the Responses API.

This provider is intentionally separate from the legacy ``azure`` provider so
existing Azure Chat Completions deployments keep their current behaviour.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_openai import AzureChatOpenAI

from .base_client import BaseLLMClient, normalize_content

_PASSTHROUGH_KWARGS = (
    "timeout",
    "max_retries",
    "api_key",
    "reasoning_effort",
    "temperature",
    "callbacks",
    "http_client",
    "http_async_client",
)


class NormalizedAzureResponsesOpenAI(AzureChatOpenAI):
    """Azure Responses client with plain-text output for downstream agents."""

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


class AzureResponsesOpenAIClient(BaseLLMClient):
    """Azure OpenAI adapter that always uses the Responses API.

    Required environment variables:
        AZURE_OPENAI_API_KEY: Azure resource API key.
        AZURE_OPENAI_ENDPOINT: Resource root, for example
            ``https://<resource>.openai.azure.com/``.
        AZURE_OPENAI_DEPLOYMENT_NAME: Azure deployment name. Falls back to the
            configured model name.
        AZURE_OPENAI_API_VERSION: Azure API version. ``OPENAI_API_VERSION`` is
            accepted as a backward-compatible fallback.

    Response storage is disabled because TradingAgents persists the reports it
    needs locally and should not opt into server-side response retention.
    """

    def __init__(self, model: str, base_url: str | None = None, **kwargs):
        super().__init__(model, base_url, **kwargs)
        self.provider = "azure_responses"

    def get_llm(self) -> Any:
        self.warn_if_unknown_model()

        llm_kwargs: dict[str, Any] = {
            "model": self.model,
            "azure_deployment": os.environ.get(
                "AZURE_OPENAI_DEPLOYMENT_NAME", self.model
            ),
            "use_responses_api": True,
            "store": False,
        }

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        if endpoint:
            llm_kwargs["azure_endpoint"] = endpoint

        api_version = os.environ.get("AZURE_OPENAI_API_VERSION") or os.environ.get(
            "OPENAI_API_VERSION"
        )
        if api_version:
            llm_kwargs["api_version"] = api_version

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return NormalizedAzureResponsesOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Azure accepts any model name associated with a deployment."""
        return True
