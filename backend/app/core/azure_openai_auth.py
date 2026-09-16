"""Shared Azure OpenAI authentication helpers.

Uses an API key when one is configured, and falls back to Microsoft Entra ID
(managed identity in Azure, developer credentials locally) when key-based
authentication is unavailable or disabled on the Azure OpenAI resource.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


def get_azure_openai_token_provider() -> Optional[Callable[[], str]]:
    """Return a bearer token provider for Azure OpenAI, or None if unavailable."""
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        return get_bearer_token_provider(
            DefaultAzureCredential(), COGNITIVE_SERVICES_SCOPE
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "Unable to create Entra ID token provider for Azure OpenAI: %s", exc)
        return None


def get_azure_openai_auth_kwargs(api_key: str | None) -> Dict[str, Any]:
    """Build auth keyword arguments for Azure OpenAI / LangChain clients."""
    if api_key:
        return {"api_key": api_key}

    token_provider = get_azure_openai_token_provider()
    if token_provider is None:
        return {}

    logger.info("Using Microsoft Entra ID authentication for Azure OpenAI")
    return {"azure_ad_token_provider": token_provider}
