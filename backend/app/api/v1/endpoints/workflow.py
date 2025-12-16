"""Workflow endpoint definitions (API v1)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
import re
from typing import Any
from datetime import datetime
import uuid
import logging

from app.models.claim import ClaimIn, ClaimOut
from app.services.claim_processing import run as run_workflow
from app.sample_data import ALL_SAMPLE_CLAIMS
from app.services.cosmos_service import get_cosmos_service
from app.services.token_tracker import TokenUsageTracker, get_token_tracker
from app.models.agent_models import AgentExecution, AgentStepExecution, ExecutionStatus
from app.services.token_estimation import estimate_agent_step_tokens
from app.services.evaluation_service import get_evaluation_service
from app.models.evaluation import EvaluationRequest

router = APIRouter(tags=["workflow"])

# Initialize logger
logger = logging.getLogger(__name__)

# Regex compiled once
DECISION_PATTERN = re.compile(
    r"\b(APPROVED|DENIED|REQUIRES_INVESTIGATION)\b", re.IGNORECASE)


def get_sample_claim_by_id(claim_id: str) -> dict:
    """Retrieve sample claim data by claim_id."""
    for claim in ALL_SAMPLE_CLAIMS:
        if claim.get("claim_id") == claim_id:
            return claim

    # If not found, list available claim IDs
    available_ids = [claim.get("claim_id") for claim in ALL_SAMPLE_CLAIMS]
    raise HTTPException(
        status_code=404,
        detail=f"Claim ID '{claim_id}' not found. Available sample claim IDs: {available_ids}"
    )


@router.get("/workflow/sample-claims")
async def list_sample_claims():
    """List all available sample claims for testing."""
    claims_summary = []
    for claim in ALL_SAMPLE_CLAIMS:
        claims_summary.append({
            "claim_id": claim.get("claim_id"),
            "claimant_name": claim.get("claimant_name"),
            "claim_type": claim.get("claim_type"),
            "estimated_damage": claim.get("estimated_damage"),
            "description": claim.get("description", "")
        })

    return {
        "available_claims": claims_summary,
        "usage": "Use POST /api/v1/workflow/run with {'claim_id': 'CLM-2024-001'} to process a sample claim"
    }


@router.post("/workflow/run", response_model=ClaimOut)
async def workflow_run(claim: ClaimIn):  # noqa: D401
    """Run the claim through the multi-agent workflow and return full trace.

    Accepts either:
    - A claim_id to load sample data: {"claim_id": "CLM-2024-001"}
    - Full claim data: {"claim_id": "...", "policy_number": "...", ...}
    """
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    
    # Get tracer for creating spans
    tracer = trace.get_tracer(__name__)

    # Initialize tracking
    cosmos_service = await get_cosmos_service()
    token_tracker = get_token_tracker(cosmos_service)
    execution_id = str(uuid.uuid4())
    
    # Create top-level span for entire workflow
    with tracer.start_as_current_span(
        "workflow.insurance_claim_processing",
        attributes={
            "gen_ai.operation.name": "workflow.execute",
            "workflow.type": "insurance_claim_processing",
            "workflow.execution_id": execution_id,
        }
    ) as workflow_span:
        try:
            # ------------------------------------------------------------------
            # 1. Decide whether to load sample claim or use provided data
            # ------------------------------------------------------------------
            # Load sample data if claim_id provided and matches sample claim
            if claim.claim_id:
                claim_data = get_sample_claim_by_id(claim.claim_id)

                # Merge/override with any additional fields supplied in request (e.g., supporting_documents)
                override_data = {
                    k: v for k, v in claim.model_dump(by_alias=True, exclude_none=True).items()
                    if k != "claim_id"
                }

                # Apply overrides (including supporting_images) on top of sample claim
                claim_data.update(override_data)
            else:
                # Full claim provided without loading sample
                claim_data = claim.to_dict()
            
            # Add claim_id to workflow span
            workflow_span.set_attribute("insurance.claim_id", claim_data.get("claim_id", "unknown"))
            workflow_span.set_attribute("insurance.claim_type", claim_data.get("claim_type", "unknown"))
            
            # Start tracking
            await token_tracker.start_tracking(
                claim_id=claim_data.get("claim_id", "unknown"),
                workflow_id=execution_id
            )
            
            # Setup and enable token capture from OpenTelemetry spans for Cosmos DB
            try:
                from app.services.token_span_processor import setup_token_span_processor, get_token_span_processor
                
                # Setup span processor if not already configured
                span_processor = get_token_span_processor()
                if not span_processor:
                    span_processor = setup_token_span_processor(token_tracker)
                
                if span_processor:
                    span_processor.enable()
                    logger.debug("✅ Token span processor enabled - will save token usage to Cosmos DB")
            except Exception as e:
                logger.warning(f"⚠️ Could not enable token span processor: {e}")

            # ------------------------------------------------------------------
            # 2. Stream LangGraph execution; capture both grouped & chronological
            # ------------------------------------------------------------------
            chronological: list[dict[str, str]] = []
            seen_lengths: dict[str, int] = {}
            agent_steps: list[AgentStepExecution] = []
            started_at = datetime.utcnow()

            chunks = []
            for chunk in run_workflow(claim_data):
                chunks.append(chunk)
                
                # Process each node in the chunk (now we get individual agent updates)
                for node_name, node_data in chunk.items():
                    if node_name == "__end__":
                        continue

                    # Handle different data structures
                    if isinstance(node_data, list):
                        msgs = node_data
                    elif isinstance(node_data, dict) and "messages" in node_data:
                        msgs = node_data["messages"]
                    elif isinstance(node_data, dict) and set(node_data.keys()) == {"messages"}:
                        # Handle supervisor-style single messages key
                        msgs = node_data["messages"]
                    else:
                        continue

                    prev_len = seen_lengths.get(node_name, 0)
                    new_msgs = msgs[prev_len:]

                    for msg in new_msgs:
                        serialized = _serialize_msg(node_name, msg)
                        chronological.append(serialized)
                        
                        # Track agent steps (only for recognized agents, skip supervisor)
                        if node_name in ["claim_assessor", "policy_checker", "risk_analyst", "communication_agent"]:
                            step_started = datetime.utcnow()
                            
                            # Prepare input/output data
                            input_data = {"content": serialized.get("content", "")}
                            output_data = {"role": serialized.get("role", ""), "content": serialized.get("content", "")}
                            
                            # Estimate token usage for this step
                            estimated_tokens = estimate_agent_step_tokens(input_data, output_data)
                            
                            agent_steps.append(AgentStepExecution(
                                agent_type=node_name,  # AgentType enum value
                                agent_version="1.0.0",
                                started_at=step_started,
                                completed_at=step_started,  # Immediate for message processing
                                duration_ms=0.0,
                                input_data=input_data,
                                output_data=output_data,
                                token_usage=estimated_tokens,
                                status=ExecutionStatus.COMPLETED
                            ))

                    seen_lengths[node_name] = len(msgs)

            # ------------------------------------------------------------------
            # 3. Extract final decision from chronological messages
            # ------------------------------------------------------------------
            final_decision: str | None = None

            # Extract final decision scanning chronological reverse order
            for entry in reversed(chronological):
                match = DECISION_PATTERN.search(entry["content"])
                if match:
                    final_decision = match.group(1).upper()
                    break

            # Finalize tracking
            completed_at = datetime.utcnow()
            duration_ms = (completed_at - started_at).total_seconds() * 1000
            
            # Save execution to Cosmos DB
            if cosmos_service._initialized:
                # Calculate total tokens and cost from agent steps (already estimated)
                total_tokens_all = sum(step.token_usage.get('total_tokens', 0) for step in agent_steps)
                total_cost_all = 0.0
                
                # Estimate cost using GPT-4.1-mini pricing ($0.00015 per 1K prompt, $0.0006 per 1K completion)
                for step in agent_steps:
                    prompt_tokens = step.token_usage.get('prompt_tokens', 0)
                    completion_tokens = step.token_usage.get('completion_tokens', 0)
                    total_cost_all += (prompt_tokens * 0.00015 + completion_tokens * 0.0006) / 1000
                
                # Save token usage records to Cosmos DB for each agent step
                for step in agent_steps:
                    total_tokens = step.token_usage.get('total_tokens', 0) if isinstance(step.token_usage, dict) else 0
                    if total_tokens > 0:
                        await token_tracker.record_token_usage(
                            model_name="gpt-4.1-mini",
                            deployment_name="gpt-4.1-mini",
                            prompt_tokens=step.token_usage.get('prompt_tokens', 0),
                            completion_tokens=step.token_usage.get('completion_tokens', 0),
                            agent_type=step.agent_type,
                            operation_type="chat_completion"
                        )
                
                execution = AgentExecution(
                    id=execution_id,
                    workflow_id=execution_id,
                    workflow_type="insurance_claim_processing",
                    claim_id=claim_data.get("claim_id", "unknown"),
                    agent_steps=agent_steps,
                    final_result={"decision": final_decision, "success": True},
                    status=ExecutionStatus.COMPLETED,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    total_tokens=total_tokens_all,
                    total_cost=total_cost_all,
                    agents_invoked=list(set(step.agent_type for step in agent_steps)),
                    metadata={
                        "total_steps": len(agent_steps),
                        "execution_id": execution_id
                    }
                )
                await cosmos_service.save_execution(execution)
            
            # Force flush of tracer provider to ensure all spans are processed
            try:
                from opentelemetry import trace
                tracer_provider = trace.get_tracer_provider()
                if hasattr(tracer_provider, 'force_flush'):
                    tracer_provider.force_flush()
                    logger.debug("✅ Flushed tracer provider - all spans processed")
            except Exception as e:
                logger.warning(f"Could not flush tracer provider: {e}")
            
            # Wait briefly for span processor to complete async operations
            import asyncio
            await asyncio.sleep(0.5)
            
            # Finalize token tracking and disable span processor
            await token_tracker.finalize_tracking()
            
            try:
                from app.services.token_span_processor import get_token_span_processor
                span_processor = get_token_span_processor()
                if span_processor:
                    span_processor.disable()
                    logger.debug("Token span processor disabled after workflow completion")
            except Exception as e:
                logger.warning(f"Could not disable token span processor: {e}")

            # ------------------------------------------------------------------
            # 4. Run evaluation on workflow execution
            # ------------------------------------------------------------------
            evaluation_results = None
            try:
                evaluation_service = get_evaluation_service()
                if evaluation_service.is_available():
                    logger.info(f"Running evaluation for execution: {execution_id}")
                    
                    # Extract question and answer from conversation
                    first_user_message = next((msg for msg in chronological if msg.get('role') == 'human'), None)
                    last_assistant_message = next(
                        (msg for msg in reversed(chronological) 
                         if msg.get('role') == 'ai' and not msg.get('content', '').startswith('TOOL_CALL:')),
                        None
                    )
                    
                    question = first_user_message.get('content', f"Process claim {claim_data.get('claim_id')}") if first_user_message else f"Process claim {claim_data.get('claim_id')}"
                    answer = last_assistant_message.get('content', 'No response available') if last_assistant_message else 'No response available'
                    
                    # Extract context from claim data
                    context = [
                        f"Claim ID: {claim_data.get('claim_id', 'N/A')}",
                        f"Claimant: {claim_data.get('claimant_name', 'N/A')}",
                        f"Claim Type: {claim_data.get('claim_type', 'N/A')}",
                        f"Description: {claim_data.get('description', 'N/A')}",
                        f"Estimated Damage: ${claim_data.get('estimated_damage', 'N/A')}",
                    ]
                    
                    # Run evaluation
                    eval_request = EvaluationRequest(
                        execution_id=execution_id,
                        claim_id=str(claim_data.get('claim_id', 'unknown')),
                        agent_type='workflow',
                        question=question,
                        answer=answer,
                        context=context,
                        metrics=['groundedness', 'relevance', 'coherence', 'fluency']
                    )
                    
                    eval_result = await evaluation_service.evaluate_execution(eval_request)
                    
                    if eval_result:
                        evaluation_results = {
                            'evaluation_id': eval_result.evaluation_id,
                            'overall_score': eval_result.overall_score,
                            'groundedness_score': eval_result.groundedness_score,
                            'relevance_score': eval_result.relevance_score,
                            'coherence_score': eval_result.coherence_score,
                            'fluency_score': eval_result.fluency_score,
                            'reasoning': eval_result.reasoning
                        }
                        logger.info(f"✅ Evaluation completed with score: {eval_result.overall_score:.2f}")
                else:
                    logger.info("Evaluation service not available, skipping evaluation")
            except Exception as eval_err:
                logger.warning(f"Evaluation failed, continuing without it: {eval_err}")
            
            # ------------------------------------------------------------------
            # 5. Return response with chronological stream and evaluation
            # ------------------------------------------------------------------
            workflow_span.set_attribute("workflow.status", "completed")
            workflow_span.set_attribute("workflow.agent_count", len(agent_steps))
            workflow_span.set_status(Status(StatusCode.OK))
            
            return ClaimOut(
                success=True,
                final_decision=final_decision,
                conversation_chronological=chronological,
                execution_id=execution_id,
                evaluation_results=evaluation_results,
            )

        except Exception as exc:
            # Mark workflow span as failed
            workflow_span.set_status(Status(StatusCode.ERROR, str(exc)))
            workflow_span.record_exception(exc)
            
            # Save failed execution
            if cosmos_service._initialized:
                try:
                    now = datetime.utcnow()
                    start = started_at if 'started_at' in locals() else now
                    execution = AgentExecution(
                        id=execution_id,
                        workflow_id=execution_id,
                        workflow_type="insurance_claim_processing",
                        claim_id=claim_data.get("claim_id", "unknown") if 'claim_data' in locals() else "unknown",
                        agent_steps=[],
                        final_result={"error": str(exc)},
                        status=ExecutionStatus.FAILED,
                        started_at=start,
                        completed_at=now,
                        duration_ms=(now - start).total_seconds() * 1000,
                        error_message=str(exc)
                    )
                    await cosmos_service.save_execution(execution)
                except:
                    pass  # Don't fail on tracking errors
            
            raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# Helper serialization
# ------------------------------------------------------------------


def _serialize_msg(node: str, msg: Any, *, include_node: bool = True) -> dict:  # noqa: D401
    """Return a serializable dict for a LangChain message including tool calls."""
    role = getattr(msg, "role", getattr(msg, "type", "assistant"))

    # Handle tool call messages (AIMessage with tool_calls attr)
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        content_repr = f"TOOL_CALL: {msg.tool_calls}"
    else:
        content_repr = getattr(msg, "content", str(msg)) or ""

    data = {
        "role": role,
        "content": content_repr.strip(),
    }
    if include_node:
        data["node"] = node
    return data
