"""Centralised application settings using Pydantic [v2].

All environment variables are optional so the app can still start for local
mock/testing. Access via `get_settings()` for a cached singleton.
"""
from __future__ import annotations

import functools
from typing import Any, Dict

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, Field


class Settings(BaseSettings):  # noqa: D101
    # Azure OpenAI
    azure_openai_api_key: str | None = Field(
        default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str | None = Field(
        default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment_name: str | None = Field(
        default="gpt-4o", alias="AZURE_OPENAI_DEPLOYMENT_NAME")
    azure_openai_embedding_model: str | None = Field(
        default="text-embedding-ada-002", alias="AZURE_OPENAI_EMBEDDING_MODEL")
    azure_openai_api_version: str | None = Field(
        default="2024-08-01-preview", alias="AZURE_OPENAI_API_VERSION")
    
    # Azure AI Foundry Project (for Agent Service)
    project_endpoint: str | None = Field(
        default=None, alias="PROJECT_ENDPOINT")
    
    # Azure Service Principal Authentication
    azure_tenant_id: str | None = Field(
        default=None, alias="AZURE_TENANT_ID")
    azure_client_id: str | None = Field(
        default=None, alias="AZURE_CLIENT_ID")
    azure_client_secret: str | None = Field(
        default=None, alias="AZURE_CLIENT_SECRET")
    
    # Azure Blob Storage (for document storage)
    azure_storage_account_name: str | None = Field(
        default=None, alias="AZURE_STORAGE_ACCOUNT_NAME")
    azure_storage_container_name: str | None = Field(
        default="insurance-documents", alias="AZURE_STORAGE_CONTAINER_NAME")
    
    # Azure AI Search (for document indexing)
    azure_search_endpoint: str | None = Field(
        default=None, alias="AZURE_SEARCH_ENDPOINT")
    azure_search_index_name: str | None = Field(
        default="insurance-policies", alias="AZURE_SEARCH_INDEX_NAME")

    # FastAPI
    app_name: str = "Insurance Multi-Agent Backend"
    api_v1_prefix: str = "/api/v1"

    model_config = {
        "extra": "ignore",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    # Convenience: serialise to dict sans secrets
    def dict_safe(self) -> Dict[str, Any]:  # noqa: D401
        return self.model_dump(exclude={
            "azure_openai_api_key",
            "azure_client_secret"
        })


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:  # noqa: D401
    """Return a cached Settings instance (singleton)."""
    return Settings()
