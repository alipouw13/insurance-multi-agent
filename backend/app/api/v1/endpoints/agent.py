"""Per-agent execution endpoints (API v1).

Each specialist agent can be invoked directly via:
POST /api/v1/agent/{agent_name}/run

The request body mirrors the existing ``ClaimIn`` schema.  The endpoint
returns the serialized message list from that single agent.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, List
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.models.claim import ClaimIn
from app.models.agent import AgentRunOut
from app.models.agent_models import AgentExecution, AgentStepExecution, ExecutionStatus
from app.services.single_agent import run as run_single_agent, UnknownAgentError
from app.services.cosmos_service import get_cosmos_service
from app.api.v1.endpoints.workflow import (
    get_sample_claim_by_id,
    _serialize_msg,  # reuse existing serializer
)

router = APIRouter(tags=["agent"])

# Re-use decision pattern from workflow endpoint if needed externally
DECISION_PATTERN = re.compile(
    r"\b(APPROVED|DENIED|REQUIRES_INVESTIGATION)\b", re.IGNORECASE
)


@router.post("/agent/{agent_name}/run", response_model=AgentRunOut)
async def agent_run(agent_name: str, claim: ClaimIn):  # noqa: D401
    """Run a single specialist agent and return its conversation trace."""

    # Generate unique execution ID
    execution_id = str(uuid.uuid4())
    started_at = datetime.utcnow()

    try:
        # ------------------------------------------------------------------
        # 1. Load sample claim or use provided data (same logic as supervisor)
        # ------------------------------------------------------------------
        if claim.claim_id:
            claim_data = get_sample_claim_by_id(claim.claim_id)

            # Merge/override with any additional fields supplied in request
            override_data = {
                k: v
                for k, v in claim.model_dump(by_alias=True, exclude_none=True).items()
                if k != "claim_id"
            }
            claim_data.update(override_data)
        else:
            claim_data = claim.to_dict()

        # ------------------------------------------------------------------
        # 2. Run the agent graph (token tracking handled internally)
        # ------------------------------------------------------------------
        raw_msgs, usage_info = await run_single_agent(agent_name, claim_data)

        # ------------------------------------------------------------------
        # 3. Serialize messages for JSON response
        # ------------------------------------------------------------------
        chronological = [_serialize_msg(agent_name, m, include_node=False) for m in raw_msgs]

        completed_at = datetime.utcnow()
        duration_ms = (completed_at - started_at).total_seconds() * 1000

        # ------------------------------------------------------------------
        # 4. Save individual agent execution to Cosmos DB
        # ------------------------------------------------------------------
        cosmos_service = await get_cosmos_service()
        if cosmos_service._initialized:
            # Create agent step execution with token usage
            agent_step = AgentStepExecution(
                agent_type=agent_name,
                agent_version="1.0.0",
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                input_data={"claim_id": claim_data.get("claim_id", "unknown"), "claim_data": claim_data},
                output_data={"messages": chronological},
                token_usage=usage_info,  # Populate with actual token usage
                status=ExecutionStatus.COMPLETED
            )

            # Calculate total tokens for the execution record
            total_tokens = usage_info.get('total_tokens', 0) if usage_info else 0
            total_cost = 0.0
            if total_tokens > 0:
                # Estimate cost using GPT-4o pricing
                total_cost = (usage_info.get('prompt_tokens', 0) * 0.005 + 
                             usage_info.get('completion_tokens', 0) * 0.015) / 1000

            # Create execution record for individual agent
            execution = AgentExecution(
                id=execution_id,
                workflow_id=execution_id,  # For individual agent, workflow_id is same as execution_id
                workflow_type="single_agent_execution",
                claim_id=claim_data.get("claim_id", "unknown"),
                agent_steps=[agent_step],
                final_result={"success": True, "messages_count": len(chronological)},
                status=ExecutionStatus.COMPLETED,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                total_tokens=total_tokens,
                total_cost=total_cost,
                agents_invoked=[agent_name],
                metadata={
                    "single_agent": True,
                    "agent_name": agent_name,
                    "message_count": len(chronological)
                }
            )
            await cosmos_service.save_execution(execution)

        return AgentRunOut(
            success=True,
            agent_name=agent_name,
            claim_body=claim_data,
            conversation_chronological=chronological,
        )

    except UnknownAgentError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc))
