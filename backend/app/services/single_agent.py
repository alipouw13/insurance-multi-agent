"""Service helper to run a single compiled LangGraph agent or Azure AI agent.

This mirrors the existing ``services.claim_processing`` layer but targets
one specialist agent instead of the supervisor.  It first checks if an
Azure AI Agent Service agent is available, otherwise falls back to the
compiled LangGraph agent from ``app.workflow.registry``.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List

from app.workflow.registry import AGENTS

logger = logging.getLogger(__name__)


class UnknownAgentError(ValueError):
    """Raised when a requested agent name does not exist in the registry."""


async def run(agent_name: str, claim_data: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, int]]:  # noqa: D401
    """Run *one* agent on the claim data and return its message list with token usage.

    Args:
        agent_name: Key in ``app.workflow.registry.AGENTS``.
        claim_data: Claim dict already merged/cleaned by the endpoint.

    Returns:
        Tuple of (messages, usage_info) where usage_info contains token counts
    """
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    
    logger.debug("🚀 Starting single-agent run: %s", agent_name)
    
    # Get tracer for creating spans
    tracer = trace.get_tracer(__name__)
    
    # Create a span for the agent execution
    with tracer.start_as_current_span(
        f"invoke_agent.{agent_name}",
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": agent_name,
            "gen_ai.agent.type": agent_name,
            "insurance.claim_id": claim_data.get("claim_id", "unknown"),
        }
    ) as span:
        try:
            # Check if Azure AI agent is available
            from app.workflow.azure_agent_manager import is_azure_agent_available, get_azure_agent_id
            
            if is_azure_agent_available(agent_name):
                logger.debug(f"✨ Using Azure AI Agent Service for {agent_name}")
                span.set_attribute("gen_ai.system", "azure_ai_agents")
                result = _run_azure_agent(agent_name, claim_data)
            else:
                logger.debug(f"📊 Using LangGraph agent for {agent_name}")
                span.set_attribute("gen_ai.system", "langgraph")
                result = _run_langgraph_agent(agent_name, claim_data)
            
            span.set_status(Status(StatusCode.OK))
            return result
            
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def _run_azure_agent(agent_name: str, claim_data: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Run an Azure AI Agent Service agent.
    
    Args:
        agent_name: Name of the agent
        claim_data: Claim dict already merged/cleaned by the endpoint
        
    Returns:
        Tuple of (messages, usage_info) where messages is LangGraph-compatible format
        and usage_info contains {prompt_tokens, completion_tokens, total_tokens}
    """
    from app.workflow.azure_agent_manager import get_azure_agent_id
    from app.workflow.azure_agent_client import run_agent
    
    agent_id = get_azure_agent_id(agent_name)
    
    # Create user message
    user_message = f"Please process this insurance claim:\n\n{json.dumps(claim_data, indent=2)}"
    
    # Get toolset for agent if it needs tools
    toolset = _get_toolset_for_agent(agent_name)
    
    # Run Azure agent and get messages with usage info
    azure_messages, usage_info = run_agent(agent_id, user_message, toolset=toolset)
    
    # Log token usage and attach to current span for telemetry tracking
    if usage_info and (usage_info.get('total_tokens', 0) > 0):
        logger.debug(f"💰 Azure AI agent token usage for {agent_name}: {usage_info['prompt_tokens']} prompt + {usage_info['completion_tokens']} completion = {usage_info['total_tokens']} total tokens")
        
        # Attach usage info to current OpenTelemetry span so it can be captured by span processor
        from opentelemetry import trace
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute("gen_ai.usage.prompt_tokens", usage_info['prompt_tokens'])
            current_span.set_attribute("gen_ai.usage.completion_tokens", usage_info['completion_tokens'])
            current_span.set_attribute("gen_ai.usage.total_tokens", usage_info['total_tokens'])
            current_span.set_attribute("gen_ai.system", "azure_ai_agents")
            current_span.set_attribute("gen_ai.request.model", "gpt-4o")
            current_span.set_attribute("agent.type", agent_name)
            logger.debug(f"✅ Attached token usage to span for {agent_name}")
    
    # Convert Azure AI message format to LangGraph-compatible format
    messages = []
    for msg in azure_messages:
        if msg["role"] == "user":
            messages.append({
                "role": "user",
                "content": msg["content"]
            })
        elif msg["role"] == "assistant":
            # Extract text content from Azure AI message format
            content = msg["content"]
            if isinstance(content, list):
                # Azure AI format: [{'type': 'text', 'text': {'value': '...', 'annotations': []}}]
                text_parts = []
                for item in content:
                    if item.get("type") == "text" and isinstance(item.get("text"), dict):
                        text_parts.append(item["text"].get("value", ""))
                content = "\n".join(text_parts)
            
            messages.append({
                "role": "assistant",
                "content": content
            })
    
    logger.debug("✅ Azure AI agent run finished: %s messages", len(messages))
    return messages, usage_info


def _get_toolset_for_agent(agent_name: str):
    """Get the toolset for a specific agent.
    
    Args:
        agent_name: Name of the agent
        
    Returns:
        ToolSet with functions for the agent, or None if no tools needed
    """
    from azure.ai.agents.models import FunctionTool, ToolSet
    
    if agent_name == "claim_assessor":
        # Import tools for claim assessor
        from app.workflow.agents.azure_claim_assessor import get_vehicle_details, analyze_image
        user_functions = {get_vehicle_details, analyze_image}
        functions = FunctionTool(functions=user_functions)
        toolset = ToolSet()
        toolset.add(functions)
        return toolset
    
    elif agent_name == "policy_checker":
        # Import tools for policy checker
        from app.workflow.agents.azure_policy_checker import get_policy_details, search_policy_documents
        user_functions = {get_policy_details, search_policy_documents}
        functions = FunctionTool(functions=user_functions)
        toolset = ToolSet()
        toolset.add(functions)
        return toolset
    
    elif agent_name == "risk_analyst":
        # Import tools for risk analyst
        from app.workflow.agents.azure_risk_analyst import get_claimant_history
        user_functions = {get_claimant_history}
        functions = FunctionTool(functions=user_functions)
        toolset = ToolSet()
        toolset.add(functions)
        return toolset
    
    # No tools needed for communication_agent
    return None


def _run_langgraph_agent(agent_name: str, claim_data: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Run a LangGraph agent.
    
    Args:
        agent_name: Name of the agent
        claim_data: Claim dict already merged/cleaned by the endpoint
        
    Returns:
        Tuple of (messages, usage_info) where messages is from LangGraph agent
        and usage_info is empty dict (LangGraph token tracking not yet implemented)
    """
    if agent_name not in AGENTS:
        raise UnknownAgentError(f"Unknown agent '{agent_name}'. Available: {list(AGENTS)}")

    agent = AGENTS[agent_name]

    # Wrap claim data in a user message (same pattern supervisor uses)
    messages = [
        {
            "role": "user",
            "content": (
                "Please process this insurance claim:\n\n" + json.dumps(claim_data, indent=2)
            ),
        }
    ]

    result = agent.invoke({"messages": messages})
    # LangGraph convention: result is {"messages": [...]}
    msgs = result.get("messages", []) if isinstance(result, dict) else result

    logger.debug("✅ LangGraph agent run finished: %s messages", len(msgs))
    # Return empty usage_info for LangGraph (token tracking not yet implemented)
    return msgs, {}
