"""Azure OpenAI Responses API provider wiring."""

from __future__ import annotations

import pytest

from tradingagents.llm_clients.api_key_env import get_api_key_env
from tradingagents.llm_clients.factory import build_llm_kwargs, create_llm_client


@pytest.mark.unit
def test_factory_routes_to_dedicated_adapter():
    client = create_llm_client("azure_responses", "gpt-6.1-sol")
    assert type(client).__name__ == "AzureResponsesOpenAIClient"
    assert get_api_key_env("azure_responses") == "AZURE_OPENAI_API_KEY"


@pytest.mark.unit
def test_responses_configuration_from_azure_environment(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT", "https://example-resource.openai.azure.com/"
    )
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "sol-deployment")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")

    llm = create_llm_client(
        "azure_responses", "gpt-6.1-sol", reasoning_effort="high"
    ).get_llm()

    assert llm.use_responses_api is True
    assert llm.store is False
    assert llm.reasoning_effort == "high"
    assert llm.deployment_name == "sol-deployment"
    assert str(llm.azure_endpoint) == "https://example-resource.openai.azure.com/"
    assert llm.openai_api_version == "2025-04-01-preview"


@pytest.mark.unit
def test_api_version_supports_legacy_sdk_env_name(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT", "https://example-resource.openai.azure.com/"
    )
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    monkeypatch.setenv("OPENAI_API_VERSION", "2024-10-21")

    llm = create_llm_client("azure_responses", "deployment").get_llm()
    assert llm.openai_api_version == "2024-10-21"


@pytest.mark.unit
def test_reasoning_effort_is_forwarded_for_azure_responses():
    kwargs = build_llm_kwargs(
        {
            "llm_provider": "azure_responses",
            "openai_reasoning_effort": "high",
        }
    )
    assert kwargs["reasoning_effort"] == "high"
