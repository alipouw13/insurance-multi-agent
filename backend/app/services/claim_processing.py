"""Service layer to invoke the insurance workflow supervisor."""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def run(claim: Dict[str, Any]):  # noqa: D401
    """Run claim through supervisor and return raw chunks.
    
    Uses USE_AZURE_AGENTS setting to determine which supervisor to use:
    - False (default): LangGraph supervisor (v1)
    - True: Azure AI Agent Service supervisor (v2)
    """
    settings = get_settings()
    
    if settings.use_azure_agents:
        logger.info("Using Azure AI Agent Service (v2) agents")
        from app.workflow.supervisor_v2 import process_claim_with_supervisor_v2
        return process_claim_with_supervisor_v2(claim)
    else:
        logger.info("Using LangGraph (v1) agents")
        from app.workflow import process_claim_with_supervisor
        return process_claim_with_supervisor(claim)
