"""Token usage tracking service with Cosmos DB persistence.

This service tracks token usage across all Azure AI operations including:
- Azure OpenAI chat completions
- Embedding generation
- Azure AI Agent Service calls
- AI Search queries

Follows patterns from: https://github.com/alipouw13/ai-sec-claims-analysis
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from app.core.config import get_settings
from app.models.agent_models import (
    AgentType,
    OperationType,
    ServiceType,
    TokenUsageRecord,
)
from app.services.cosmos_service import get_cosmos_service

logger = logging.getLogger(__name__)


class TokenUsageTracker:
    """Token usage tracking service with Cosmos DB storage."""
    
    def __init__(self, cosmos_service=None):
        """Initialize the token usage tracker."""
        self._active_sessions: Dict[str, TokenUsageRecord] = {}
        self._cosmos_service = cosmos_service
        self._current_claim_id: Optional[str] = None
        self._current_workflow_id: Optional[str] = None
        
        # Token pricing (per 1K tokens) - Azure OpenAI pricing as of Dec 2024
        self.token_pricing = {
            "gpt-4o": {"prompt": 0.005, "completion": 0.015},
            "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
            "gpt-4.1-mini": {"prompt": 0.00015, "completion": 0.0006},  # Alias
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-35-turbo": {"prompt": 0.0015, "completion": 0.002},
            "text-embedding-3-small": {"prompt": 0.00002, "completion": 0.0},
            "text-embedding-3-large": {"prompt": 0.00013, "completion": 0.0},
            "text-embedding-ada-002": {"prompt": 0.0001, "completion": 0.0}
        }
    
    async def start_tracking(
        self,
        claim_id: str,
        workflow_id: str,
        user_id: Optional[str] = None
    ):
        """Start tracking for a workflow execution.
        
        Args:
            claim_id: Claim ID being processed
            workflow_id: Workflow execution ID
            user_id: Optional user identifier
        """
        self._current_claim_id = claim_id
        self._current_workflow_id = workflow_id
        logger.info(f"🎯 Started token tracking for claim {claim_id}, workflow {workflow_id}")
    
    def start_tracking_legacy(
        self,
        session_id: str,
        service_type: ServiceType,
        operation_type: OperationType,
        agent_type: Optional[AgentType] = None,
        claim_id: Optional[str] = None,
        user_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Start tracking a new token usage session (legacy method).
        
        Args:
            session_id: User session identifier
            service_type: Type of Azure service
            operation_type: Specific operation being performed
            agent_type: Type of agent (if applicable)
            claim_id: Associated claim ID
            user_id: User identifier
            execution_id: Workflow execution ID
            **kwargs: Additional metadata
            
        Returns:
            Tracking ID for this session
        """
        record_id = str(uuid.uuid4())
        
        record = TokenUsageRecord(
            id=record_id,
            record_id=record_id,
            session_id=session_id,
            user_id=user_id,
            claim_id=claim_id,
            execution_id=execution_id,
            service_type=service_type,
            operation_type=operation_type,
            agent_type=agent_type,
            model_name="",  # Will be set when usage is recorded
            request_start_time=time.time(),
            timestamp=datetime.now(timezone.utc),
            **kwargs
        )
        
        self._active_sessions[record_id] = record
        logger.debug(f"Started tracking: {record_id} ({service_type.value}/{operation_type.value})")
        
        return record_id
    
    def update_model_info(
        self,
        tracking_id: str,
        model_name: str,
        deployment_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """Update model information for an active tracking session.
        
        Args:
            tracking_id: Tracking session ID
            model_name: Model or deployment name
            deployment_name: Azure deployment name
            temperature: Model temperature setting
            max_tokens: Maximum tokens setting
        """
        if tracking_id in self._active_sessions:
            record = self._active_sessions[tracking_id]
            record.model_name = model_name
            record.deployment_name = deployment_name or model_name
            if temperature is not None:
                record.temperature = temperature
            if max_tokens:
                record.max_tokens = max_tokens
    
    async def update_usage(
        self,
        tracking_id: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        response_text: Optional[str] = None,
        request_text: Optional[str] = None
    ):
        """Update token usage for an active tracking session.
        
        Args:
            tracking_id: Tracking session ID
            prompt_tokens: Number of prompt tokens used
            completion_tokens: Number of completion tokens used
            response_text: Response text from the model
            request_text: Request text to the model
        """
        if tracking_id not in self._active_sessions:
            logger.warning(f"Tracking session {tracking_id} not found")
            return
        
        record = self._active_sessions[tracking_id]
        
        # Accumulate token usage
        record.prompt_tokens += prompt_tokens
        record.completion_tokens += completion_tokens
        record.total_tokens = record.prompt_tokens + record.completion_tokens
        
        # Update text if provided
        if request_text:
            record.request_text = request_text
            record.request_size_chars = len(request_text)
        
        if response_text:
            if record.response_text:
                record.response_text += f"\n---\n{response_text}"
            else:
                record.response_text = response_text
            record.response_size_chars = len(record.response_text)
        
        # Calculate costs
        model_key = self._get_model_key_for_pricing(record.model_name or record.deployment_name)
        if model_key in self.token_pricing:
            pricing = self.token_pricing[model_key]
            record.prompt_cost = (record.prompt_tokens / 1000) * pricing["prompt"]
            record.completion_cost = (record.completion_tokens / 1000) * pricing["completion"]
            record.total_cost = record.prompt_cost + record.completion_cost
        
        logger.debug(
            f"Updated usage for {tracking_id}: "
            f"prompt={record.prompt_tokens}, completion={record.completion_tokens}, "
            f"total={record.total_tokens}, cost=${record.total_cost:.4f}"
        )
    
    async def finalize_tracking(self):
        """Finalize tracking for current workflow (simplified method)."""
        if self._current_claim_id:
            logger.info(f"✅ Finalized token tracking for claim {self._current_claim_id}")
            # Note: Token usage is captured automatically via OpenTelemetry instrumentation
            # This method is a placeholder for future enhancements
            self._current_claim_id = None
            self._current_workflow_id = None
    
    async def finalize_tracking_legacy(
        self,
        tracking_id: str,
        success: bool = True,
        error_message: Optional[str] = None,
        http_status_code: int = 200,
        **metadata
    ):
        """Finalize and store a tracking session (legacy method).
        
        Args:
            tracking_id: Tracking session ID
            success: Whether the operation succeeded
            error_message: Error message if failed
            http_status_code: HTTP status code
            **metadata: Additional metadata to store
        """
        if tracking_id not in self._active_sessions:
            logger.warning(f"Tracking session {tracking_id} not found")
            return
        
        record = self._active_sessions[tracking_id]
        
        # Update final status
        record.success = success
        record.error_message = error_message
        record.http_status_code = http_status_code
        
        # Update timing
        record.request_end_time = time.time()
        if record.request_start_time:
            record.duration_ms = (record.request_end_time - record.request_start_time) * 1000
        
        # Add metadata
        if metadata:
            record.metadata.update(metadata)
        
        # Store in Cosmos DB
        try:
            if self._cosmos_service and self._cosmos_service._initialized:
                await self._cosmos_service.save_token_usage(record)
                logger.info(
                    f"✅ Finalized tracking {tracking_id}: "
                    f"{record.total_tokens} tokens, ${record.total_cost:.4f}"
                )
        except Exception as e:
            logger.error(f"❌ Failed to store token usage: {e}")
        
        # Remove from active sessions
        del self._active_sessions[tracking_id]
    
    def _get_model_key_for_pricing(self, model_identifier: str) -> str:
        """Map model identifier to pricing key.
        
        Args:
            model_identifier: Model name or deployment name
            
        Returns:
            Pricing key for token cost calculation
        """
        if not model_identifier:
            return "gpt-4o-mini"  # Default fallback
        
        model_lower = model_identifier.lower()
        
        # Map deployment names and model names to pricing keys
        if "gpt-4o-mini" in model_lower or "gpt-4.1-mini" in model_lower:
            return "gpt-4o-mini"
        elif "gpt-4o" in model_lower:
            return "gpt-4o"
        elif "gpt-4" in model_lower:
            return "gpt-4"
        elif "gpt-35-turbo" in model_lower or "gpt-3.5-turbo" in model_lower:
            return "gpt-35-turbo"
        elif "text-embedding-3-small" in model_lower:
            return "text-embedding-3-small"
        elif "text-embedding-3-large" in model_lower:
            return "text-embedding-3-large"
        elif "text-embedding-ada-002" in model_lower or "ada-002" in model_lower:
            return "text-embedding-ada-002"
        else:
            logger.warning(f"Unknown model for pricing: {model_identifier}, using gpt-4o-mini")
            return "gpt-4o-mini"
    
    async def get_claim_token_summary(self, claim_id: str) -> Dict[str, any]:
        """Get token usage summary for a specific claim.
        
        Args:
            claim_id: Claim identifier
            
        Returns:
            Dictionary with aggregated token usage
        """
        try:
            cosmos_service = await get_cosmos_service()
            records = await cosmos_service.get_token_usage_by_claim(claim_id)
            
            if not records:
                return {
                    "claim_id": claim_id,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "by_agent": {},
                    "by_operation": {}
                }
            
            # Aggregate by agent and operation
            by_agent = {}
            by_operation = {}
            total_tokens = 0
            total_cost = 0.0
            
            for record in records:
                # By agent
                agent = record.agent_type.value if record.agent_type else "unknown"
                if agent not in by_agent:
                    by_agent[agent] = {"tokens": 0, "cost": 0.0, "calls": 0}
                by_agent[agent]["tokens"] += record.total_tokens
                by_agent[agent]["cost"] += record.total_cost
                by_agent[agent]["calls"] += 1
                
                # By operation
                operation = record.operation_type.value
                if operation not in by_operation:
                    by_operation[operation] = {"tokens": 0, "cost": 0.0, "calls": 0}
                by_operation[operation]["tokens"] += record.total_tokens
                by_operation[operation]["cost"] += record.total_cost
                by_operation[operation]["calls"] += 1
                
                total_tokens += record.total_tokens
                total_cost += record.total_cost
            
            return {
                "claim_id": claim_id,
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "by_agent": by_agent,
                "by_operation": by_operation,
                "total_calls": len(records)
            }
            
        except Exception as e:
            logger.error(f"Failed to get claim token summary: {e}")
            return {
                "claim_id": claim_id,
                "total_tokens": 0,
                "total_cost": 0.0,
                "error": str(e)
            }


# Global singleton instance
_token_tracker: Optional[TokenUsageTracker] = None


def get_token_tracker() -> TokenUsageTracker:
    """Get or create the global token usage tracker instance.
    
    Returns:
        Token usage tracker
    """
    global _token_tracker
    if _token_tracker is None:
        _token_tracker = TokenUsageTracker()
    return _token_tracker
