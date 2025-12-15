"""Evaluation API endpoints."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from app.models.evaluation import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationSummary,
    AgentEvaluationContext
)
from app.services.evaluation_service import get_evaluation_service
from app.services.cosmos_service import get_cosmos_service

router = APIRouter(tags=["evaluation"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def get_evaluation_status():
    """Check if evaluation service is available."""
    evaluation_service = get_evaluation_service()
    is_available = evaluation_service.is_available()
    
    return {
        "available": is_available,
        "evaluator_type": "foundry" if is_available else None,
        "metrics": ["groundedness", "relevance", "coherence", "fluency"] if is_available else []
    }


@router.post("/evaluate", response_model=EvaluationResult)
async def evaluate_execution(request: EvaluationRequest):
    """Evaluate an agent execution using Azure AI Foundry.
    
    This endpoint evaluates an agent's performance using metrics like:
    - Groundedness: Is the response supported by the context?
    - Relevance: Does the response address the question?
    - Coherence: Is the response logically consistent?
    - Fluency: Is the response well-written?
    """
    try:
        evaluation_service = get_evaluation_service()
        
        if not evaluation_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="Evaluation service not available. Install azure-ai-evaluation package."
            )
        
        logger.info(f"Evaluating execution: {request.execution_id} for agent: {request.agent_type}")
        
        result = await evaluation_service.evaluate_execution(request)
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.get("/execution/{execution_id}", response_model=List[EvaluationResult])
async def get_evaluations_for_execution(execution_id: str):
    """Get all evaluations for a specific execution."""
    try:
        evaluation_service = get_evaluation_service()
        results = await evaluation_service.get_evaluations_for_execution(execution_id)
        return results
    except Exception as e:
        logger.error(f"Failed to get evaluations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/claim/{claim_id}", response_model=List[EvaluationResult])
async def get_evaluations_for_claim(claim_id: str):
    """Get all evaluations for a specific claim."""
    try:
        evaluation_service = get_evaluation_service()
        results = await evaluation_service.get_evaluations_for_claim(claim_id)
        return results
    except Exception as e:
        logger.error(f"Failed to get evaluations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=EvaluationSummary)
async def get_evaluation_summary(
    execution_id: Optional[str] = Query(None),
    claim_id: Optional[str] = Query(None)
):
    """Get evaluation summary for an execution or claim."""
    try:
        if not execution_id and not claim_id:
            raise HTTPException(status_code=400, detail="Must provide execution_id or claim_id")
        
        evaluation_service = get_evaluation_service()
        summary = await evaluation_service.get_evaluation_summary(
            execution_id=execution_id,
            claim_id=claim_id
        )
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{evaluation_id}", response_model=EvaluationResult)
async def get_evaluation_by_id(evaluation_id: str):
    """Get a specific evaluation result by ID."""
    try:
        evaluation_service = get_evaluation_service()
        result = await evaluation_service.get_evaluation_result(evaluation_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
