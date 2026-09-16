"""Service layer to invoke the insurance workflow supervisor."""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def run(claim: Dict[str, Any]):  # noqa: D401
    """Run claim through supervisor and return raw chunks.

    Backend selection:
    - USE_FOUNDRY_AGENTS: new Foundry prompt agents (Responses API)
    - USE_AZURE_AGENTS: classic Azure AI Agent Service supervisor (v2)
    - otherwise: LangGraph supervisor (v1)
    """
    settings = get_settings()

    if settings.use_foundry_agents:
        try:
            logger.info("Using Microsoft Foundry agents (new Foundry)")
            from app.workflow.foundry_agents import run_claim_workflow
            return run_claim_workflow(claim)
        except Exception as exc:
            # Never fail a claim because the agent backend is unavailable.
            logger.error(
                "Foundry agent workflow failed (%s); falling back to LangGraph", exc)
            from app.workflow import process_claim_with_supervisor
            return process_claim_with_supervisor(claim)

    if settings.use_azure_agents:
        logger.info("Using Azure AI Agent Service (v2) agents")
        from app.workflow.supervisor_v2 import process_claim_with_supervisor_v2
        return process_claim_with_supervisor_v2(claim)

    logger.info("Using LangGraph (v1) agents")
    from app.workflow import process_claim_with_supervisor
    return process_claim_with_supervisor(claim)
