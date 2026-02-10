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
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Get settings instance
settings = get_settings()


class UnknownAgentError(ValueError):
    """Raised when a requested agent name does not exist in the registry."""


def _generate_fabric_query(claim_data: Dict[str, Any]) -> str:
    """Generate a claim-specific Fabric query based on claim type and context.
    
    Creates simple, natural language queries optimized for Fabric Data Agent.
    The Fabric Data Agent works best with focused, single-purpose queries.
    Complex queries with multiple conditions often fail.
    
    Args:
        claim_data: The claim data dictionary
        
    Returns:
        A focused natural language query string
    """
    claimant_id = claim_data.get('claimant_id', 'unknown')
    claimant_name = claim_data.get('claimant_name', 'unknown')
    
    # Simple, reliable query - just get the claimant's history
    # Complex queries with "and fraud rate for X claims over $Y in Z" frequently fail
    return f"Show all claims for claimant {claimant_id} ({claimant_name})"


def _format_lakehouse_response(
    claimant_history: list, 
    fraud_stats: dict, 
    claimant_id: str, 
    claimant_name: str, 
    state: str, 
    claim_type: str
) -> str:
    """Format Lakehouse query results into a readable response.
    
    Args:
        claimant_history: List of claim records from Lakehouse
        fraud_stats: Fraud statistics from Lakehouse
        claimant_id: Claimant ID
        claimant_name: Claimant name
        state: State abbreviation
        claim_type: Type of claim
        
    Returns:
        Formatted markdown string
    """
    # Calculate history stats
    total_claims = len(claimant_history)
    approved_claims = sum(1 for c in claimant_history if c.get('status', '').upper() == 'APPROVED')
    denied_claims = sum(1 for c in claimant_history if c.get('status', '').upper() == 'DENIED')
    total_amount = sum(c.get('claim_amount', 0) for c in claimant_history)
    avg_amount = total_amount / total_claims if total_claims > 0 else 0
    fraud_flags = sum(1 for c in claimant_history if c.get('fraud_flag'))
    
    # Extract fraud stats
    fraud_rate = fraud_stats.get('fraud_rate', 0)
    regional_avg = fraud_stats.get('avg_claim_amount', 0)
    regional_total = fraud_stats.get('total_claims', 0)
    
    response = f"""## Claims Data Analysis for {claimant_name} ({claimant_id})

### 📊 Live Data from Fabric Lakehouse

---

### Claimant History Summary

| Metric | Value |
|--------|-------|
| Total Claims Filed | {total_claims} |
| Approved Claims | {approved_claims} |
| Denied Claims | {denied_claims} |
| Total Amount Claimed | ${total_amount:,.2f} |
| Average Claim Amount | ${avg_amount:,.2f} |
| Fraud Flags | {fraud_flags} |

### Regional Statistics ({state})

| Metric | Value |
|--------|-------|
| {claim_type} Fraud Rate | {fraud_rate:.1f}% |
| Average Claim Amount | ${regional_avg:,.2f} |
| Total Claims in Region | {regional_total:,} |

### Recent Claim History

"""
    
    # Add recent claims table
    if claimant_history:
        response += "| Date | Type | Amount | Status |\n|------|------|--------|--------|\n"
        for claim in claimant_history[:5]:  # Show last 5 claims
            date = claim.get('claim_date', 'N/A')
            ctype = claim.get('claim_type', 'N/A')
            amount = claim.get('claim_amount', 0)
            status = claim.get('status', 'N/A')
            response += f"| {date} | {ctype} | ${amount:,.2f} | {status} |\n"
    else:
        response += "*No prior claims found for this claimant.*\n"
    
    # Add risk assessment
    response += "\n### Risk Assessment\n\n"
    
    if total_claims > 3:
        response += "- ⚠️ **High claim frequency** - Multiple prior claims detected\n"
    else:
        response += "- ✅ **Normal claim frequency** - Limited claim history\n"
    
    if fraud_flags > 0:
        response += f"- ⚠️ **Prior fraud flags** - {fraud_flags} previous claims flagged\n"
    else:
        response += "- ✅ **No prior fraud flags**\n"
    
    if fraud_rate > 5:
        response += f"- ⚠️ **Elevated regional fraud rate** - {fraud_rate:.1f}% for this claim type\n"
    else:
        response += f"- ✅ **Normal regional fraud rate** - {fraud_rate:.1f}%\n"
    
    return response


async def run(agent_name: str, claim_data: Dict[str, Any], user_token: str = None) -> tuple[List[Dict[str, Any]], Dict[str, int], str]:  # noqa: D401
    """Run *one* agent on the claim data and return its message list with token usage.

    Args:
        agent_name: Key in ``app.workflow.registry.AGENTS``.
        claim_data: Claim dict already merged/cleaned by the endpoint.
        user_token: Optional Azure AD user token for Fabric Data Agent authentication.

    Returns:
        Tuple of (messages, usage_info, thread_id) where usage_info contains token counts
        and thread_id is for continuing the conversation
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
                result = _run_azure_agent_v2(agent_name, claim_data, user_token=user_token)
            elif agent_name in AGENTS:
                logger.debug(f"📊 Using LangGraph agent for {agent_name}")
                span.set_attribute("gen_ai.system", "langgraph")
                messages, usage = _run_langgraph_agent(agent_name, claim_data)
                result = (messages, usage, None)  # No thread_id for LangGraph
            else:
                # Agent not yet deployed (background thread still running) and no LangGraph fallback
                raise UnknownAgentError(
                    f"Agent '{agent_name}' is not ready yet. "
                    f"It may still be deploying — please wait a few seconds and try again."
                )
            
            span.set_status(Status(StatusCode.OK))
            return result
            
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def _run_azure_agent_v2(agent_name: str, claim_data: Dict[str, Any], user_token: str = None, thread_id: str = None) -> tuple[List[Dict[str, Any]], Dict[str, int], str]:
    """Run an Azure AI Agent Service v2 agent.
    
    Args:
        agent_name: Name of the agent
        claim_data: Claim dict already merged/cleaned by the endpoint
        user_token: Optional Azure AD user token for Fabric Data Agent authentication
        thread_id: Optional existing thread ID to continue a conversation
        user_token: Optional Azure AD user token for Fabric Data Agent authentication
        
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
    fabric_query = None  # Track the query for UI display
    
    if agent_name == "claims_data_analyst":
        tool_choice = "fabric_dataagent"
        
        # Extract key identifiers for simple query
        claimant_id = claim_data.get('claimant_id', 'unknown')
        claim_type = claim_data.get('claim_type', 'unknown')
        state = claim_data.get('state', 'unknown')
        claimant_name = claim_data.get('claimant_name', 'unknown')
        
        # Generate claim-specific query based on claim type
        fabric_query = _generate_fabric_query(claim_data)
        
        logger.info(f"[CLAIMS_DATA_ANALYST] === Starting Claims Data Analyst Run ===")
        logger.info(f"[CLAIMS_DATA_ANALYST] Forcing tool_choice={tool_choice} for Fabric queries")
        logger.info(f"[CLAIMS_DATA_ANALYST] Claimant: {claimant_name} ({claimant_id})")
        logger.info(f"[CLAIMS_DATA_ANALYST] Claim Type: {claim_type}")
        logger.info(f"[CLAIMS_DATA_ANALYST] State: {state}")
        logger.info(f"[CLAIMS_DATA_ANALYST] Fabric Query: {fabric_query}")
        
        # Keep the user message simple and direct
        user_message = fabric_query
    
    # Run Azure agent v2 and get messages with usage info
    logger.info(f"[AGENT] Calling run_agent_v2 for {agent_name} (tool_choice={tool_choice}, has_user_token={user_token is not None})")
    azure_messages, usage_info, _, thread_id = run_agent_v2(agent_id, user_message, functions=functions, tool_choice=tool_choice, user_token=user_token)
    logger.info(f"[AGENT] Agent {agent_name} returned {len(azure_messages)} messages, thread_id={thread_id}")
    
    # Log response content for Claims Data Analyst debugging
    if agent_name == "claims_data_analyst" and azure_messages:
        last_msg = azure_messages[-1] if azure_messages else {}
        content = last_msg.get("content", "")
        if isinstance(content, list):
            content = " ".join([c.get("text", {}).get("value", "") if isinstance(c, dict) else str(c) for c in content])
        preview = content[:500] if len(content) > 500 else content
        logger.info(f"[CLAIMS_DATA_ANALYST] Response preview: {preview}")
        
        # DEBUG: Log the FULL response before fallback check
        logger.warning(f"[CLAIMS_DATA_ANALYST] ===== FULL AGENT RESPONSE =====")
        logger.warning(f"[CLAIMS_DATA_ANALYST] {content}")
        logger.warning(f"[CLAIMS_DATA_ANALYST] ===== END RESPONSE =====")
        
        # Check for connectivity issues - match the same phrases used in azure_agent_client_v2.py
        connectivity_phrases = [
            "technical difficulties", "technical issue", "connectivity issue", "unable to retrieve", 
            "data service issue", "encountered an issue", "failure connecting",
            "issue retrieving", "cannot query", "unable to query", "error accessing",
            "will retry", "please advise", "alternate access", "made an error",
            "apologize", "i apologize", "issue accessing", "having trouble",
            "trouble accessing", "cannot access", "unable to access", "failed to access",
            "could not access", "could not retrieve", "failed to retrieve",
            "unable to connect", "failed to connect", "no data available",
            "encountered a technical", "unable to directly", "was unable to",
            "let me retry", "ensure connection", "once accessible"
        ]
        fabric_failed = any(phrase in content.lower() for phrase in connectivity_phrases)
        
        # DEBUG: Log which phrase triggered fallback
        if fabric_failed:
            for phrase in connectivity_phrases:
                if phrase in content.lower():
                    logger.warning(f"[CLAIMS_DATA_ANALYST] FALLBACK TRIGGERED by phrase: '{phrase}'")
                    break
        
        if fabric_failed:
            logger.warning(f"[CLAIMS_DATA_ANALYST] Fabric connectivity issue detected in response!")
            logger.info(f"[CLAIMS_DATA_ANALYST] Attempting Lakehouse fallback...")
            
            # Try Lakehouse direct query fallback
            from app.services.lakehouse_service import get_lakehouse_service, get_demo_claims_data
            
            lakehouse = get_lakehouse_service()
            if lakehouse:
                try:
                    claimant_history = lakehouse.get_claimant_history(claimant_id)
                    fraud_stats = lakehouse.get_fraud_rate_by_region(state, claim_type)
                    
                    # Format Lakehouse data into response
                    fallback_content = _format_lakehouse_response(
                        claimant_history, fraud_stats, claimant_id, claimant_name, state, claim_type
                    )
                    logger.info(f"[CLAIMS_DATA_ANALYST] Lakehouse fallback successful")
                except Exception as e:
                    logger.error(f"[CLAIMS_DATA_ANALYST] Lakehouse query failed: {e}")
                    fallback_content = get_demo_claims_data(claimant_id, claim_type, state, claimant_name)
                    logger.info(f"[CLAIMS_DATA_ANALYST] Using demo data fallback")
            else:
                # No Lakehouse configured, use demo data
                fallback_content = get_demo_claims_data(claimant_id, claim_type, state, claimant_name)
                logger.info(f"[CLAIMS_DATA_ANALYST] Using demo data fallback (Lakehouse not configured)")
            
            # Replace the error message with fallback content
            azure_messages = [{
                "role": "assistant", 
                "content": f"**📊 Fabric Query:** `{fabric_query}`\n\n---\n\n{fallback_content}"
            }]
        else:
            logger.info(f"[CLAIMS_DATA_ANALYST] Fabric data retrieved successfully")
            # Add query header to the response for UI display
            if fabric_query and azure_messages:
                # Find the last assistant message and prepend the query info
                for msg in reversed(azure_messages):
                    if msg.get("role") == "assistant":
                        original_content = msg.get("content", "")
                        if isinstance(original_content, list):
                            # Handle Azure AI message format
                            for item in original_content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text_obj = item.get("text", {})
                                    if isinstance(text_obj, dict):
                                        original_text = text_obj.get("value", "")
                                        text_obj["value"] = f"**📊 Fabric Query:** `{fabric_query}`\n\n---\n\n{original_text}"
                                        break
                        else:
                            msg["content"] = f"**📊 Fabric Query:** `{fabric_query}`\n\n---\n\n{original_content}"
                        break
    
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
            current_span.set_attribute("gen_ai.request.model", settings.azure_openai_deployment_name or "gpt-4o")
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
    
    logger.debug("✅ Azure AI agent v2 run finished: %s messages, thread_id=%s", len(messages), thread_id)
    return messages, usage_info, thread_id


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
