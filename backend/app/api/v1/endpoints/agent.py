"""Per-agent execution endpoints (API v1).

Each specialist agent can be invoked directly via:
POST /api/v1/agent/{agent_name}/run

The request body mirrors the existing ``ClaimIn`` schema.  The endpoint
returns the serialized message list from that single agent.
"""
from __future__ import annotations

import re
import uuid
import logging
from typing import Any, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header

from app.models.claim import ClaimIn
from app.models.agent import AgentRunOut, AgentContinueIn
from app.models.agent_models import AgentExecution, AgentStepExecution, ExecutionStatus
from app.services.single_agent import run as run_single_agent, UnknownAgentError
from app.services.cosmos_service import get_cosmos_service
from app.api.v1.endpoints.workflow import (
    get_sample_claim_by_id,
    _serialize_msg,  # reuse existing serializer
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])

# Re-use decision pattern from workflow endpoint if needed externally
DECISION_PATTERN = re.compile(
    r"\b(APPROVED|DENIED|REQUIRES_INVESTIGATION)\b", re.IGNORECASE
)


@router.post("/agent/{agent_name}/run", response_model=AgentRunOut)
async def agent_run(agent_name: str, claim: ClaimIn):  # noqa: D401
    """Run a single specialist agent and return its conversation trace.
    
    For the Claims Data Analyst agent with Fabric integration, pass a user_token
    obtained from Azure AD sign-in on the frontend. This is required for Fabric
    Data Agent's identity passthrough (On-Behalf-Of) authentication.
    """

    # Generate unique execution ID
    execution_id = str(uuid.uuid4())
    started_at = datetime.utcnow()
    
    # Extract user_token for Fabric Data Agent authentication
    user_token = claim.user_token

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
        raw_msgs, usage_info, thread_id = await run_single_agent(agent_name, claim_data, user_token=user_token)

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
                    "message_count": len(chronological),
                    "thread_id": thread_id
                }
            )
            await cosmos_service.save_execution(execution)

        return AgentRunOut(
            success=True,
            agent_name=agent_name,
            claim_body=claim_data,
            conversation_chronological=chronological,
            execution_id=execution_id,
            thread_id=thread_id,
        )

    except UnknownAgentError as err:
        # Return 503 if agent is still deploying, 404 if truly unknown
        status = 503 if "not ready yet" in str(err) else 404
        raise HTTPException(status_code=status, detail=str(err))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/agent/{agent_name}/continue", response_model=AgentRunOut)
async def agent_continue(
    agent_name: str, 
    body: AgentContinueIn,
    x_user_token: str = Header(None)
):  # noqa: D401
    """Continue a conversation with an agent on an existing thread.
    
    This allows multi-turn conversations with agents like the Claims Data Analyst
    that may ask for confirmation before executing queries.
    """
    logger.info(f"[AGENT_CONTINUE] Continuing conversation on thread {body.thread_id} for {agent_name}")
    
    started_at = datetime.utcnow()
    
    # Use token from header or body
    user_token = x_user_token or body.user_token

    try:
        from app.workflow.azure_agent_manager_v2 import get_azure_agent_id_v2
        from app.workflow.azure_agent_client_v2 import run_agent_v2
        
        agent_id = get_azure_agent_id_v2(agent_name)
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        # For follow-up messages, don't force tool_choice - let the model decide naturally
        # The model already knows about the Fabric tool and will call it when appropriate
        # Forcing tool_choice on follow-ups can cause server errors
        tool_choice = None
        
        logger.info(f"[AGENT_CONTINUE] Sending follow-up message: '{body.message[:100]}...'")
        
        # Continue the conversation on the existing thread
        azure_messages, usage_info, _, thread_id = run_agent_v2(
            agent_id, 
            body.message, 
            tool_choice=tool_choice,
            user_token=user_token,
            thread_id=body.thread_id
        )
        
        # Convert Azure messages to response format
        chronological = []
        for msg in azure_messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if item.get("type") == "text" and isinstance(item.get("text"), dict):
                        text_parts.append(item["text"].get("value", ""))
                content = "\n".join(text_parts)
            
            chronological.append({
                "role": "ai" if msg.get("role") == "assistant" else "human",
                "content": content
            })
        
        completed_at = datetime.utcnow()
        duration_ms = (completed_at - started_at).total_seconds() * 1000
        
        logger.info(f"[AGENT_CONTINUE] Completed in {duration_ms:.0f}ms with {len(chronological)} messages")
        
        return AgentRunOut(
            success=True,
            agent_name=agent_name,
            claim_body={},  # No claim body for continue operations
            conversation_chronological=chronological,
            thread_id=thread_id,
        )

    except Exception as exc:
        logger.error(f"[AGENT_CONTINUE] Error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agent/{agent_name}/info")
async def agent_info(agent_name: str):
    """Get diagnostic information about an agent including its tools."""
    try:
        from app.workflow.azure_agent_manager_v2 import get_azure_agent_id_v2
        from app.workflow.azure_agent_client_v2 import get_project_client_v2
        
        agent_id = get_azure_agent_id_v2(agent_name)
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        project_client = get_project_client_v2()
        agent = project_client.agents.get_agent(agent_id=agent_id)
        
        # Extract tool information
        tools_info = []
        if hasattr(agent, 'tools') and agent.tools:
            for tool in agent.tools:
                tool_dict = {
                    "type": getattr(tool, 'type', 'unknown'),
                }
                # Add all non-private attributes
                for attr in dir(tool):
                    if not attr.startswith('_') and not callable(getattr(tool, attr)):
                        try:
                            val = getattr(tool, attr)
                            if val is not None and attr not in ['type']:
                                tool_dict[attr] = str(val)[:200]  # Limit length
                        except:
                            pass
                tools_info.append(tool_dict)
        
        return {
            "agent_name": agent_name,
            "agent_id": agent_id,
            "model": getattr(agent, 'model', 'unknown'),
            "tools_count": len(agent.tools) if hasattr(agent, 'tools') and agent.tools else 0,
            "tools": tools_info,
            "instructions_length": len(agent.instructions) if hasattr(agent, 'instructions') else 0,
            "instructions_preview": agent.instructions[:500] if hasattr(agent, 'instructions') else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AGENT_INFO] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
