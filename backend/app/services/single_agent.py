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
            # Check if Azure AI agent v2 is available
            from app.workflow.azure_agent_manager_v2 import get_azure_agent_id_v2, get_azure_agent_functions_v2
            
            agent_id = get_azure_agent_id_v2(agent_name)
            if agent_id:
                logger.debug(f"✨ Using Azure AI Agent Service (v2) for {agent_name}")
                span.set_attribute("gen_ai.system", "azure_ai_agents_v2")
                result = _run_azure_agent_v2(agent_name, claim_data)
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


def _run_azure_agent_v2(agent_name: str, claim_data: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Run an Azure AI Agent Service v2 agent.
    
    Args:
        agent_name: Name of the agent
        claim_data: Claim dict already merged/cleaned by the endpoint
        
    Returns:
        Tuple of (messages, usage_info) where messages is LangGraph-compatible format
        and usage_info contains {prompt_tokens, completion_tokens, total_tokens}
    """
    from app.workflow.azure_agent_manager_v2 import get_azure_agent_id_v2, get_azure_agent_functions_v2
    from app.workflow.azure_agent_client_v2 import run_agent_v2
    
    logger.info(f"[AGENT] Running Azure AI agent: {agent_name}")
    
    agent_id = get_azure_agent_id_v2(agent_name)
    logger.info(f"[AGENT] Agent ID for {agent_name}: {agent_id}")
    
    # Create user message
    user_message = f"Please process this insurance claim:\n\n{json.dumps(claim_data, indent=2)}"
    
    # Get functions for agent if it needs tools (v2 uses function dicts, not toolsets)
    functions = get_azure_agent_functions_v2(agent_name)
    
    # Special handling for Claims Data Analyst - force Fabric tool
    tool_choice = None
    if agent_name == "claims_data_analyst":
        tool_choice = "fabric_dataagent"
        logger.info(f"[CLAIMS_DATA_ANALYST] Forcing tool_choice={tool_choice} for Fabric queries")
        logger.info(f"[CLAIMS_DATA_ANALYST] Claimant ID: {claim_data.get('claimant_id', 'N/A')}")
        user_message = f"""Please analyze enterprise data for this claim using the Fabric data tool:

{json.dumps(claim_data, indent=2)}

IMPORTANT: You MUST use the Microsoft Fabric tool to query the lakehouse data.

Query the Fabric data lakehouse to provide:
1. Historical claims data for this claimant (if any) - look up by claimant_id
2. Similar claims from other claimants for benchmarking - search by claim_type
3. Regional statistics for the claim location - search by state
4. Any matching fraud patterns - check fraud_indicators table
5. Statistical context (averages, frequencies, outliers)

Provide specific numbers and statistics from your Fabric data queries."""
    
    # Run Azure agent v2 and get messages with usage info
    logger.info(f"[AGENT] Calling run_agent_v2 for {agent_name} (tool_choice={tool_choice})")
    azure_messages, usage_info, _ = run_agent_v2(agent_id, user_message, functions=functions, tool_choice=tool_choice)
    logger.info(f"[AGENT] Agent {agent_name} returned {len(azure_messages)} messages")
    
    # Log token usage and attach to current span for telemetry tracking
    if usage_info and (usage_info.get('total_tokens', 0) > 0):
        logger.info(f"[AGENT] Token usage for {agent_name}: {usage_info.get('prompt_tokens', 0)} prompt + {usage_info.get('completion_tokens', 0)} completion = {usage_info.get('total_tokens', 0)} total")
        
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
    
    logger.debug("✅ Azure AI agent v2 run finished: %s messages", len(messages))
    return messages, usage_info


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
