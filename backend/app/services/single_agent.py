"""Service helper to run a single compiled LangGraph agent or Azure AI agent.

This mirrors the existing ``services.claim_processing`` layer but targets
one specialist agent instead of the supervisor.  It first checks if an
Azure AI Agent Service agent is available, otherwise falls back to the
compiled LangGraph agent from ``app.workflow.registry``.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.workflow.registry import AGENTS

logger = logging.getLogger(__name__)


class UnknownAgentError(ValueError):
    """Raised when a requested agent name does not exist in the registry."""


def run(agent_name: str, claim_data: Dict[str, Any]) -> List[Dict[str, Any]]:  # noqa: D401
    """Run *one* agent on the claim data and return its message list.

    Args:
        agent_name: Key in ``app.workflow.registry.AGENTS``.
        claim_data: Claim dict already merged/cleaned by the endpoint.

    Returns:
        The message list returned by ``agent.invoke``.
    """
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    
    logger.info("🚀 Starting single-agent run: %s", agent_name)
    
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
                logger.info(f"✨ Using Azure AI Agent Service for {agent_name}")
                span.set_attribute("gen_ai.system", "azure_ai_agents")
                result = _run_azure_agent(agent_name, claim_data)
            else:
                logger.info(f"📊 Using LangGraph agent for {agent_name}")
                span.set_attribute("gen_ai.system", "langgraph")
                result = _run_langgraph_agent(agent_name, claim_data)
            
            span.set_status(Status(StatusCode.OK))
            return result
            
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def _run_azure_agent(agent_name: str, claim_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run an Azure AI Agent Service agent.
    
    Args:
        agent_name: Name of the agent
        claim_data: Claim dict already merged/cleaned by the endpoint
        
    Returns:
        Message list in LangGraph-compatible format
    """
    from app.workflow.azure_agent_manager import get_azure_agent_id
    from app.workflow.azure_agent_client import run_agent
    
    agent_id = get_azure_agent_id(agent_name)
    
    # Create user message
    user_message = f"Please process this insurance claim:\n\n{json.dumps(claim_data, indent=2)}"
    
    # Get toolset for agent if it needs tools
    toolset = _get_toolset_for_agent(agent_name)
    
    # Run Azure agent and get messages
    azure_messages = run_agent(agent_id, user_message, toolset=toolset)
    
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
    
    logger.info("✅ Azure AI agent run finished: %s messages", len(messages))
    return messages


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
        from app.workflow.agents.azure_policy_checker import search_policies
        user_functions = {search_policies}
        functions = FunctionTool(functions=user_functions)
        toolset = ToolSet()
        toolset.add(functions)
        return toolset
    
    elif agent_name == "risk_analyst":
        # Import tools for risk analyst
        from app.workflow.agents.azure_risk_analyst import get_fraud_indicators, get_historical_claims
        user_functions = {get_fraud_indicators, get_historical_claims}
        functions = FunctionTool(functions=user_functions)
        toolset = ToolSet()
        toolset.add(functions)
        return toolset
    
    # No tools needed for communication_agent
    return None


def _run_langgraph_agent(agent_name: str, claim_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run a LangGraph agent.
    
    Args:
        agent_name: Name of the agent
        claim_data: Claim dict already merged/cleaned by the endpoint
        
    Returns:
        Message list from LangGraph agent
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

    logger.info("✅ LangGraph agent run finished: %s messages", len(msgs))
    return msgs
