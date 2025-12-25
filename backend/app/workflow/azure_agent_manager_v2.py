"""Azure AI Agent Service deployment and management (New SDK).

This module handles deploying and retrieving Azure AI Agent Service agents
using the new SDK at application startup, with fallback to LangGraph agents
when Azure agents are unavailable.
"""
import logging
from typing import Dict, Optional, Any
from azure.ai.projects import AIProjectClient
from azure.core.exceptions import ResourceNotFoundError

from app.workflow.azure_agent_client_v2 import get_project_client_v2

logger = logging.getLogger(__name__)

# Global cache of deployed Azure agent IDs (v2)
_AZURE_AGENT_IDS_V2: Dict[str, str] = {}
# Global cache of toolsets for each agent (v2)
_AZURE_AGENT_TOOLSETS_V2: Dict[str, Any] = {}
# Global cache of Python callable functions for each agent (for manual tool execution)
_AZURE_AGENT_FUNCTIONS_V2: Dict[str, Dict[str, Any]] = {}


def get_azure_agent_id_v2(agent_name: str) -> Optional[str]:
    """Get the Azure AI agent ID for a given agent name (v2).
    
    Args:
        agent_name: Name of the agent (e.g., "claim_assessor", "policy_checker")
        
    Returns:
        Agent ID if deployed, None otherwise
    """
    return _AZURE_AGENT_IDS_V2.get(agent_name)


def get_azure_agent_toolset_v2(agent_name: str) -> Optional[Any]:
    """Get the toolset for a given agent name (v2).
    
    Args:
        agent_name: Name of the agent (e.g., "claim_assessor", "policy_checker")
        
    Returns:
        ToolSet if agent has tools, None otherwise
    """
    return _AZURE_AGENT_TOOLSETS_V2.get(agent_name)


def get_azure_agent_functions_v2(agent_name: str) -> Optional[Dict[str, Any]]:
    """Get the Python callable functions for a given agent name (v2).
    
    These functions are used for manual tool execution when the supervisor
    delegates to specialist agents.
    
    Args:
        agent_name: Name of the agent (e.g., "claim_assessor", "policy_checker")
        
    Returns:
        Dict mapping function names to callables, or None if not found
    """
    return _AZURE_AGENT_FUNCTIONS_V2.get(agent_name)


def is_azure_agent_available_v2(agent_name: str) -> bool:
    """Check if an Azure AI agent is available for the given name (v2).
    
    Args:
        agent_name: Name of the agent (e.g., "claim_assessor", "policy_checker")
        
    Returns:
        True if Azure agent is deployed and available
    """
    return agent_name in _AZURE_AGENT_IDS_V2


def deploy_azure_agents_v2() -> Dict[str, str]:
    """Deploy all Azure AI Agent Service agents at startup using new SDK.
    
    This function attempts to deploy or retrieve existing Azure AI agents.
    If deployment fails (e.g., PROJECT_ENDPOINT not configured), it logs
    a warning and returns an empty dict, allowing the app to fall back to
    LangGraph agents.
    
    Returns:
        Dictionary mapping agent names to their Azure AI agent IDs
    """
    global _AZURE_AGENT_IDS_V2, _AZURE_AGENT_TOOLSETS_V2, _AZURE_AGENT_FUNCTIONS_V2
    
    logger.info("🚀 Deploying Azure AI Agent Service agents (v2)...")
    
    try:
        # Get project client
        project_client = get_project_client_v2()
        
        # Deploy each agent
        agent_creators = {
            "claim_assessor": _deploy_claim_assessor_v2,
            "policy_checker": _deploy_policy_checker_v2,
            "communication_agent": _deploy_communication_agent_v2,
            "risk_analyst": _deploy_risk_analyst_v2,
        }
        
        deployed_count = 0
        for agent_name, creator_func in agent_creators.items():
            try:
                agent_id, toolset, functions = creator_func(project_client)
                _AZURE_AGENT_IDS_V2[agent_name] = agent_id
                _AZURE_AGENT_TOOLSETS_V2[agent_name] = toolset
                _AZURE_AGENT_FUNCTIONS_V2[agent_name] = functions
                logger.info(f"✅ Deployed {agent_name} (v2): {agent_id} (tools: {'Yes' if toolset else 'No'}, functions: {len(functions) if functions else 0})")
                deployed_count += 1
            except Exception as e:
                logger.warning(f"⚠️  Failed to deploy {agent_name} (v2): {e}")
        
        if deployed_count > 0:
            logger.info(f"✅ Successfully deployed {deployed_count}/{len(agent_creators)} Azure AI agents (v2)")
        else:
            logger.warning("⚠️  No Azure AI agents (v2) deployed - will use LangGraph fallback")
        
        return _AZURE_AGENT_IDS_V2.copy()
        
    except Exception as e:
        logger.warning(f"⚠️  Azure AI Agent Service (v2) not available: {e}")
        logger.warning("⚠️  Application will use LangGraph agents as fallback")
        return {}


def _deploy_claim_assessor_v2(project_client: AIProjectClient) -> tuple[str, Any, Dict[str, Any]]:
    """Deploy or retrieve Claim Assessor agent (v2).
    
    Args:
        project_client: Azure AI Project client
        
    Returns:
        Tuple of (agent_id, toolset, functions_dict)
    """
    from app.workflow.agents.azure_claim_assessor_v2 import create_claim_assessor_agent_v2, get_claim_assessor_functions
    
    agent, toolset = create_claim_assessor_agent_v2(project_client)
    functions = get_claim_assessor_functions()
    return agent.id, toolset, functions


def _deploy_policy_checker_v2(project_client: AIProjectClient) -> tuple[str, Any, Dict[str, Any]]:
    """Deploy or retrieve Policy Checker agent (v2).
    
    Args:
        project_client: Azure AI Project client
        
    Returns:
        Tuple of (agent_id, toolset, functions_dict)
    """
    from app.workflow.agents.azure_policy_checker_v2 import create_policy_checker_agent_v2, get_policy_checker_functions
    
    agent, toolset = create_policy_checker_agent_v2(project_client)
    functions = get_policy_checker_functions()
    return agent.id, toolset, functions


def _deploy_communication_agent_v2(project_client: AIProjectClient) -> tuple[str, Any, Dict[str, Any]]:
    """Deploy or retrieve Communication agent (v2).
    
    Args:
        project_client: Azure AI Project client
        
    Returns:
        Tuple of (agent_id, toolset, functions_dict)
    """
    from app.workflow.agents.azure_communication_agent_v2 import create_communication_agent_v2
    
    agent, toolset = create_communication_agent_v2(project_client)
    # Communication agent has no tools
    return agent.id, toolset, {}


def _deploy_risk_analyst_v2(project_client: AIProjectClient) -> tuple[str, Any, Dict[str, Any]]:
    """Deploy or retrieve Risk Analyst agent (v2).
    
    Args:
        project_client: Azure AI Project client
        
    Returns:
        Tuple of (agent_id, toolset, functions_dict)
    """
    from app.workflow.agents.azure_risk_analyst_v2 import create_risk_analyst_agent_v2, get_risk_analyst_functions
    
    agent, toolset = create_risk_analyst_agent_v2(project_client)
    functions = get_risk_analyst_functions()
    return agent.id, toolset, functions
