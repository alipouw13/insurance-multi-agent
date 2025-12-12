"""Azure AI Agent wrapper with Cosmos DB persistence and token tracking.

This module provides wrappers around Azure AI Agent Service agents to automatically
track agent definitions, executions, and token usage in Cosmos DB.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from azure.ai.projects import AIProjectClient

from app.core.tracing import trace_agent_operation, trace_llm_call, record_token_usage
from app.models.agent_models import (
    AgentDefinition,
    AgentExecution,
    AgentStepExecution,
    AgentToolDefinition,
    AgentType,
    ExecutionStatus,
    OperationType,
    ServiceType,
)
from app.services.cosmos_service import get_cosmos_service
from app.services.token_tracker import get_token_tracker

logger = logging.getLogger(__name__)


class TrackedAzureAgent:
    """Wrapper for Azure AI Agent with automatic tracking."""
    
    def __init__(
        self,
        agent,
        agent_type: AgentType,
        agent_definition: Optional[AgentDefinition] = None,
        project_client: Optional[AIProjectClient] = None
    ):
        """Initialize tracked agent wrapper.
        
        Args:
            agent: Azure AI Agent instance
            agent_type: Type of agent
            agent_definition: Agent definition (will load from Cosmos if not provided)
            project_client: Azure AI Project client
        """
        self.agent = agent
        self.agent_id = agent.id
        self.agent_type = agent_type
        self.agent_definition = agent_definition
        self.project_client = project_client
    
    async def ensure_definition_saved(self):
        """Ensure agent definition is saved to Cosmos DB."""
        if self.agent_definition:
            return
        
        try:
            cosmos_service = await get_cosmos_service()
            
            # Try to load existing definition
            agent_def = await cosmos_service.get_agent_definition(self.agent_id)
            
            if agent_def:
                self.agent_definition = agent_def
                logger.debug(f"Loaded agent definition from Cosmos: {self.agent_id}")
            else:
                # Create new definition
                agent_def = AgentDefinition(
                    id=self.agent_id,
                    agent_type=self.agent_type,
                    name=self.agent_type.value.replace("_", " ").title(),
                    description=f"Azure AI Agent: {self.agent_type.value}",
                    instructions=getattr(self.agent, "instructions", ""),
                    model_deployment=getattr(self.agent, "model", "gpt-4o"),
                    version="1.0.0",
                    is_active=True
                )
                
                self.agent_definition = await cosmos_service.save_agent_definition(agent_def)
                logger.info(f"✅ Saved new agent definition: {self.agent_id}")
                
        except Exception as e:
            logger.error(f"❌ Failed to save agent definition: {e}")
    
    async def run(
        self,
        thread: AgentThread,
        claim_id: str,
        execution_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> AgentRun:
        """Run the agent with automatic tracking.
        
        Args:
            thread: Agent thread to run
            claim_id: Claim ID being processed
            execution_id: Parent workflow execution ID
            session_id: User session ID
            user_id: User ID
            **kwargs: Additional arguments for agent run
            
        Returns:
            Agent run result
        """
        # Ensure definition is saved
        await self.ensure_definition_saved()
        
        # Create step execution record
        step = AgentStepExecution(
            agent_type=self.agent_type,
            agent_version=self.agent_definition.version if self.agent_definition else "1.0.0",
            started_at=datetime.now(timezone.utc),
            status=ExecutionStatus.STARTED
        )
        
        # Determine operation type
        operation_type = self._get_operation_type()
        
        # Start token tracking
        tracker = get_token_tracker()
        tracking_id = tracker.start_tracking(
            session_id=session_id or str(uuid.uuid4()),
            service_type=ServiceType.AGENT_SERVICE,
            operation_type=operation_type,
            agent_type=self.agent_type,
            claim_id=claim_id,
            user_id=user_id,
            execution_id=execution_id
        )
        
        # Update model info
        model_name = self.agent_definition.model_deployment if self.agent_definition else "gpt-4o"
        tracker.update_model_info(
            tracking_id=tracking_id,
            model_name=model_name,
            temperature=self.agent_definition.temperature if self.agent_definition else 0.1
        )
        
        start_time = time.time()
        
        try:
            # Trace the agent operation
            with trace_agent_operation(
                operation_name=f"agent.{self.agent_type.value}",
                agent_type=self.agent_type.value,
                agent_version=step.agent_version,
                claim_id=claim_id
            ) as span:
                # Run the agent
                agent_run = self.project_client.agents.create_and_process_run(
                    thread_id=thread.id,
                    assistant_id=self.agent_id,
                    **kwargs
                )
                
                # Extract token usage from run
                if hasattr(agent_run, 'usage') and agent_run.usage:
                    usage = agent_run.usage
                    prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                    completion_tokens = getattr(usage, 'completion_tokens', 0)
                    total_tokens = getattr(usage, 'total_tokens', 0)
                    
                    step.token_usage = {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    }
                    
                    # Update tracker
                    await tracker.update_usage(
                        tracking_id=tracking_id,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens
                    )
                    
                    # Record in span
                    if span:
                        record_token_usage(span, prompt_tokens, completion_tokens, total_tokens)
                
                # Extract output
                messages = self.project_client.agents.list_messages(thread_id=thread.id)
                if messages and len(messages.data) > 0:
                    last_message = messages.data[0]
                    if hasattr(last_message, 'content') and last_message.content:
                        output_text = str(last_message.content[0].text.value)
                        step.output_data = {"response": output_text}
                        
                        await tracker.update_usage(
                            tracking_id=tracking_id,
                            response_text=output_text
                        )
                
                # Mark as completed
                step.status = ExecutionStatus.COMPLETED
                step.completed_at = datetime.now(timezone.utc())
                step.duration_ms = (time.time() - start_time) * 1000
                
                # Finalize tracking
                await tracker.finalize_tracking(
                    tracking_id=tracking_id,
                    success=True,
                    agent_type=self.agent_type.value,
                    agent_version=step.agent_version
                )
                
                logger.info(
                    f"✅ Agent {self.agent_type.value} completed: "
                    f"{step.token_usage.get('total_tokens', 0)} tokens, "
                    f"{step.duration_ms:.0f}ms"
                )
                
                return agent_run
                
        except Exception as e:
            # Mark as failed
            step.status = ExecutionStatus.FAILED
            step.error_message = str(e)
            step.completed_at = datetime.now(timezone.utc)
            step.duration_ms = (time.time() - start_time) * 1000
            
            # Finalize tracking with error
            await tracker.finalize_tracking(
                tracking_id=tracking_id,
                success=False,
                error_message=str(e),
                http_status_code=500
            )
            
            logger.error(f"❌ Agent {self.agent_type.value} failed: {e}")
            raise
    
    def _get_operation_type(self) -> OperationType:
        """Get operation type based on agent type."""
        operation_map = {
            AgentType.CLAIM_ASSESSOR: OperationType.CLAIM_ASSESSMENT,
            AgentType.POLICY_CHECKER: OperationType.POLICY_CHECK,
            AgentType.RISK_ANALYST: OperationType.RISK_ANALYSIS,
            AgentType.COMMUNICATION_AGENT: OperationType.COMMUNICATION,
        }
        return operation_map.get(self.agent_type, OperationType.CLAIM_ASSESSMENT)


async def register_agent_definition(
    agent_type: AgentType,
    name: str,
    description: str,
    instructions: str,
    model_deployment: str = "gpt-4o",
    temperature: float = 0.1,
    tools: Optional[List[Dict[str, Any]]] = None,
    version: str = "1.0.0"
) -> AgentDefinition:
    """Register or update an agent definition in Cosmos DB.
    
    Args:
        agent_type: Type of agent
        name: Human-readable agent name
        description: Agent purpose and capabilities
        instructions: System prompt/instructions
        model_deployment: Azure OpenAI deployment name
        temperature: Model temperature
        tools: List of tool definitions
        version: Semantic version
        
    Returns:
        Saved agent definition
    """
    # Convert tools to proper format
    tool_defs = []
    if tools:
        for tool in tools:
            tool_defs.append(AgentToolDefinition(
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                parameters=tool.get("parameters", {})
            ))
    
    # Create agent definition
    agent_def = AgentDefinition(
        id=f"{agent_type.value}_v{version.replace('.', '_')}",
        agent_type=agent_type,
        name=name,
        description=description,
        instructions=instructions,
        model_deployment=model_deployment,
        temperature=temperature,
        tools=tool_defs,
        version=version,
        is_active=True
    )
    
    # Save to Cosmos DB
    cosmos_service = await get_cosmos_service()
    return await cosmos_service.save_agent_definition(agent_def)


async def get_agent_execution_history(claim_id: str) -> List[AgentExecution]:
    """Get execution history for a claim.
    
    Args:
        claim_id: Claim identifier
        
    Returns:
        List of agent executions
    """
    cosmos_service = await get_cosmos_service()
    return await cosmos_service.get_claim_execution_history(claim_id)
