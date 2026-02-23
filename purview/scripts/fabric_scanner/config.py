#!/usr/bin/env python3
"""Shared configuration, authentication, and retry helpers.

Reads from the existing purview/scripts/.env and provides:
- AAD token acquisition for Fabric, Purview, and Graph APIs
- PurviewClient construction (pyapacheatlas)
- Exponential-backoff retry decorator
- Logging setup

References:
- pyapacheatlas auth:  https://github.com/wjohnson/pyapacheatlas#quickstart
- Fabric REST auth:    https://learn.microsoft.com/en-us/rest/api/fabric/articles/get-started/fabric-api-quickstart
- Graph MIP labels:    https://learn.microsoft.com/en-us/graph/api/informationprotectionpolicy-list-labels
"""
from __future__ import annotations

import functools
import logging
import os
import sys
import time
from pathlib import Path
from typing import Callable, TypeVar

from azure.identity import (
    ClientSecretCredential,
    DefaultAzureCredential,
    AzureCliCredential,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("fabric_scanner")


# ---------------------------------------------------------------------------
# .env loader (re-uses the existing .env in purview/scripts/)
# ---------------------------------------------------------------------------

def load_env(env_path: str | Path | None = None) -> None:
    """Load key=value pairs from *env_path* into ``os.environ`` (no override)."""
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    env_path = Path(env_path)
    if not env_path.exists():
        logger.warning("No .env found at %s – relying on environment variables", env_path)
        return
    with open(env_path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
    logger.info("Loaded environment from %s", env_path)


# ---------------------------------------------------------------------------
# Configuration constants (populated after load_env)
# ---------------------------------------------------------------------------

def _env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


class Config:
    """Namespace for all configuration values. Call ``Config.reload()`` after
    ``load_env()`` to pick up the latest values."""

    # Purview / Atlas
    purview_account: str = ""
    purview_collection: str = ""

    # Purview Scanning Data Plane (for classification rules / scan rule sets)
    data_source_name: str = ""   # Registered Fabric data source in Purview
    scan_name: str = ""          # Existing scan name (e.g. Scan-Fabric-Claims-Demo)

    # Fabric
    fabric_workspace_id: str = ""

    # AAD / Service Principal
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""

    # Behaviour
    dry_run: bool = False
    batch_size: int = 25  # entities per Atlas bulk upload

    @classmethod
    def reload(cls) -> None:
        cls.purview_account = _env("PURVIEW_ACCOUNT", "")
        cls.purview_collection = _env("PURVIEW_COLLECTION", "")
        cls.data_source_name = _env("PURVIEW_DATA_SOURCE_NAME", "")
        cls.scan_name = _env("PURVIEW_SCAN_NAME", "")
        cls.fabric_workspace_id = _env("FABRIC_WORKSPACE_ID", "")
        cls.tenant_id = _env("AZURE_TENANT_ID", "")
        cls.client_id = _env("AZURE_CLIENT_ID", "")
        cls.client_secret = _env("AZURE_CLIENT_SECRET", "")
        cls.dry_run = _env("DRY_RUN", "false").lower() in ("1", "true", "yes")
        cls.batch_size = int(_env("ATLAS_BATCH_SIZE", "25"))

    @classmethod
    def validate(cls) -> None:
        missing = []
        if not cls.purview_account:
            missing.append("PURVIEW_ACCOUNT")
        if not cls.fabric_workspace_id:
            missing.append("FABRIC_WORKSPACE_ID")
        if not cls.tenant_id:
            missing.append("AZURE_TENANT_ID")
        if not cls.client_id:
            missing.append("AZURE_CLIENT_ID")
        if not cls.client_secret:
            missing.append("AZURE_CLIENT_SECRET")
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Set them in purview/scripts/.env"
            )


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

def get_spn_credential() -> ClientSecretCredential:
    """Service Principal credential for Fabric & Purview APIs."""
    return ClientSecretCredential(
        tenant_id=Config.tenant_id,
        client_id=Config.client_id,
        client_secret=Config.client_secret,
    )


def get_token(scope: str) -> str:
    """Acquire a bearer token for the given scope using the Service Principal."""
    cred = get_spn_credential()
    token = cred.get_token(scope)
    return token.token


def get_fabric_token() -> str:
    """Bearer token for the Fabric REST API."""
    return get_token("https://api.fabric.microsoft.com/.default")


def get_purview_token() -> str:
    """Bearer token for the Purview Data Map / Catalog API."""
    return get_token("https://purview.azure.net/.default")


def get_graph_token() -> str:
    """Bearer token for Microsoft Graph (used for MIP labels)."""
    return get_token("https://graph.microsoft.com/.default")


# ---------------------------------------------------------------------------
# pyapacheatlas PurviewClient factory
# ---------------------------------------------------------------------------

def get_purview_client():
    """Create a ``pyapacheatlas.core.PurviewClient`` using SPN auth.

    Reference: https://github.com/wjohnson/pyapacheatlas#quickstart
    """
    from pyapacheatlas.auth import ServicePrincipalAuthentication
    from pyapacheatlas.core import PurviewClient

    auth = ServicePrincipalAuthentication(
        tenant_id=Config.tenant_id,
        client_id=Config.client_id,
        client_secret=Config.client_secret,
    )
    return PurviewClient(
        account_name=Config.purview_account,
        authentication=auth,
    )


# ---------------------------------------------------------------------------
# Retry decorator with exponential back-off
# ---------------------------------------------------------------------------

T = TypeVar("T")


def retry(
    max_attempts: int = 4,
    backoff_base: float = 2.0,
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> Callable:
    """Decorator: retries a function that returns a ``requests.Response`` or
    raises on transient HTTP errors.

    Works for both ``requests`` calls and raw functions that may raise.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    # If result is a requests.Response, check status
                    if hasattr(result, "status_code"):
                        if result.status_code in retryable_status_codes:
                            wait = backoff_base ** attempt
                            logger.warning(
                                "Attempt %d/%d for %s returned %s – retrying in %.1fs",
                                attempt, max_attempts, func.__name__,
                                result.status_code, wait,
                            )
                            time.sleep(wait)
                            continue
                    return result
                except Exception as exc:
                    last_exc = exc
                    # Don't retry on non-transient HTTP errors (400, 401, 403, 404)
                    if hasattr(exc, "response") and exc.response is not None:
                        if exc.response.status_code not in retryable_status_codes:
                            raise
                    wait = backoff_base ** attempt
                    logger.warning(
                        "Attempt %d/%d for %s raised %s – retrying in %.1fs",
                        attempt, max_attempts, func.__name__, exc, wait,
                    )
                    time.sleep(wait)
            # Exhausted retries
            if last_exc:
                raise last_exc
            return result  # noqa: may be unbound but kept for mypy

        return wrapper

    return decorator
