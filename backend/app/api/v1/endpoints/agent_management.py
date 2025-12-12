"""API endpoints for agent management, execution history, and token analytics."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.agent_models import (
    AgentDefinition,
    AgentExecution,
    AgentType,
    ExecutionStatus,
    TokenUsageRecord,
)
from app.services.cosmos_service import get_cosmos_service
from app.services.token_tracker import get_token_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


# ==================== REQUEST/RESPONSE MODELS ====================

class AgentDefinitionListResponse(BaseModel):
    """Response for listing agent definitions."""
    agents: List[AgentDefinition]
    total: int


class AgentExecutionListResponse(BaseModel):
    """Response for listing agent executions."""
    executions: List[AgentExecution]
    total: int


class TokenAnalyticsResponse(BaseModel):
    """Response for token usage analytics."""
    total_tokens: int
    total_cost: float
    by_agent: dict
    period_days: int
    total_requests: int


class ClaimTokenSummaryResponse(BaseModel):
    """Response for claim-specific token summary."""
    claim_id: str
    total_tokens: int
    total_cost: float
    by_agent: dict
    by_operation: dict
    total_calls: int


# ==================== AGENT DEFINITIONS ====================

@router.get("/definitions", response_model=AgentDefinitionListResponse)
async def list_agent_definitions(
    agent_type: Optional[AgentType] = Query(None, description="Filter by agent type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status")
):
    """List all agent definitions with optional filters.
    
    Returns:
        List of agent definitions
    """
    try:
        cosmos_service = await get_cosmos_service()
        
        agents = await cosmos_service.list_agent_definitions(
            agent_type=agent_type,
            is_active=is_active
        )
        
        return AgentDefinitionListResponse(
            agents=agents,
            total=len(agents)
        )
        
    except Exception as e:
        logger.error(f"Failed to list agent definitions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agent definitions")


@router.get("/definitions/{agent_id}", response_model=AgentDefinition)
async def get_agent_definition(agent_id: str):
    """Get a specific agent definition by ID.
    
    Args:
        agent_id: Unique agent identifier
        
    Returns:
        Agent definition
    """
    try:
        cosmos_service = await get_cosmos_service()
        
        agent_def = await cosmos_service.get_agent_definition(agent_id)
        
        if not agent_def:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        return agent_def
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent definition {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agent definition")


@router.post("/definitions", response_model=AgentDefinition)
async def save_agent_definition(agent_def: AgentDefinition):
    """Create or update an agent definition.
    
    Args:
        agent_def: Agent definition to save
        
    Returns:
        Saved agent definition
    """
    try:
        cosmos_service = await get_cosmos_service()
        
        saved_agent = await cosmos_service.save_agent_definition(agent_def)
        
        logger.info(f"✅ Saved agent definition: {saved_agent.id}")
        
        return saved_agent
        
    except Exception as e:
        logger.error(f"Failed to save agent definition: {e}")
        raise HTTPException(status_code=500, detail="Failed to save agent definition")


# ==================== AGENT EXECUTIONS ====================

@router.get("/executions", response_model=AgentExecutionListResponse)
async def list_executions(
    claim_id: Optional[str] = Query(None, description="Filter by claim ID"),
    status: Optional[ExecutionStatus] = Query(None, description="Filter by execution status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results")
):
    """List agent execution records with optional filters.
    
    Returns:
        List of agent executions
    """
    try:
        cosmos_service = await get_cosmos_service()
        
        executions = await cosmos_service.list_executions(
            claim_id=claim_id,
            status=status,
            limit=limit
        )
        
        return AgentExecutionListResponse(
            executions=executions,
            total=len(executions)
        )
        
    except Exception as e:
        logger.error(f"Failed to list executions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve executions")


@router.get("/executions/{execution_id}", response_model=AgentExecution)
async def get_execution(execution_id: str):
    """Get a specific execution record by ID.
    
    Args:
        execution_id: Unique execution identifier
        
    Returns:
        Execution record
    """
    try:
        cosmos_service = await get_cosmos_service()
        
        execution = await cosmos_service.get_execution(execution_id)
        
        if not execution:
            raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
        
        return execution
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve execution")


@router.get("/executions/claim/{claim_id}", response_model=AgentExecutionListResponse)
async def get_claim_execution_history(claim_id: str):
    """Get all execution records for a specific claim.
    
    Args:
        claim_id: Claim identifier
        
    Returns:
        List of executions for the claim
    """
    try:
        cosmos_service = await get_cosmos_service()
        
        executions = await cosmos_service.get_claim_execution_history(claim_id)
        
        return AgentExecutionListResponse(
            executions=executions,
            total=len(executions)
        )
        
    except Exception as e:
        logger.error(f"Failed to get execution history for claim {claim_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve execution history")


# ==================== TOKEN USAGE & ANALYTICS ====================

@router.get("/analytics/tokens", response_model=TokenAnalyticsResponse)
async def get_token_analytics(
    agent_type: Optional[AgentType] = Query(None, description="Filter by agent type"),
    days_back: int = Query(7, ge=1, le=90, description="Number of days to analyze")
):
    """Get aggregated token usage analytics.
    
    Returns:
        Token usage analytics
    """
    try:
        cosmos_service = await get_cosmos_service()
        
        analytics = await cosmos_service.get_token_usage_analytics(
            agent_type=agent_type,
            days_back=days_back
        )
        
        return TokenAnalyticsResponse(**analytics)
        
    except Exception as e:
        logger.error(f"Failed to get token analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve token analytics")


@router.get("/analytics/tokens/claim/{claim_id}", response_model=ClaimTokenSummaryResponse)
async def get_claim_token_summary(claim_id: str):
    """Get token usage summary for a specific claim.
    
    Args:
        claim_id: Claim identifier
        
    Returns:
        Token usage summary for the claim
    """
    try:
        tracker = get_token_tracker()
        
        summary = await tracker.get_claim_token_summary(claim_id)
        
        return ClaimTokenSummaryResponse(**summary)
        
    except Exception as e:
        logger.error(f"Failed to get token summary for claim {claim_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve token summary")


@router.get("/health")
async def health_check():
    """Check if agent management service is operational.
    
    Returns:
        Service health status
    """
    try:
        cosmos_service = await get_cosmos_service()
        
        return {
            "status": "healthy",
            "cosmos_initialized": cosmos_service._initialized
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
