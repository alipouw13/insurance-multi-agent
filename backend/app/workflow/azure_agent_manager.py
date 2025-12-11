"""Azure AI Agent Service deployment and management.

This module handles deploying and retrieving Azure AI Agent Service agents
at application startup, with fallback to LangGraph agents when Azure agents
are unavailable.
"""
import logging
from typing import Dict, Optional
from azure.ai.projects import AIProjectClient
from azure.core.exceptions import ResourceNotFoundError

from app.workflow.azure_agent_client import get_project_client

logger = logging.getLogger(__name__)

# Global cache of deployed Azure agent IDs
_AZURE_AGENT_IDS: Dict[str, str] = {}


def get_azure_agent_id(agent_name: str) -> Optional[str]:
    """Get the Azure AI agent ID for a given agent name.
    
    Args:
        agent_name: Name of the agent (e.g., "claim_assessor", "policy_checker")
        
    Returns:
        Agent ID if deployed, None otherwise
    """
    return _AZURE_AGENT_IDS.get(agent_name)


def is_azure_agent_available(agent_name: str) -> bool:
    """Check if an Azure AI agent is available for the given name.
    
    Args:
        agent_name: Name of the agent (e.g., "claim_assessor", "policy_checker")
        
    Returns:
        True if Azure agent is deployed and available
    """
    return agent_name in _AZURE_AGENT_IDS


def deploy_azure_agents() -> Dict[str, str]:
    """Deploy all Azure AI Agent Service agents at startup.
    
    This function attempts to deploy or retrieve existing Azure AI agents.
    If deployment fails (e.g., PROJECT_ENDPOINT not configured), it logs
    a warning and returns an empty dict, allowing the app to fall back to
    LangGraph agents.
    
    Returns:
        Dictionary mapping agent names to their Azure AI agent IDs
    """
    global _AZURE_AGENT_IDS
    
    logger.info("🚀 Deploying Azure AI Agent Service agents...")
    
    try:
        # Get project client
        project_client = get_project_client()
        
        # Deploy each agent
        agent_creators = {
            "claim_assessor": _deploy_claim_assessor,
            "policy_checker": _deploy_policy_checker,
            # Add more agents as they are migrated
            # "communication_agent": _deploy_communication_agent,
            # "risk_analyst": _deploy_risk_analyst,
        }
        
        deployed_count = 0
        for agent_name, creator_func in agent_creators.items():
            try:
                agent_id = creator_func(project_client)
                _AZURE_AGENT_IDS[agent_name] = agent_id
                logger.info(f"✅ Deployed {agent_name}: {agent_id}")
                deployed_count += 1
            except Exception as e:
                logger.warning(f"⚠️  Failed to deploy {agent_name}: {e}")
        
        if deployed_count > 0:
            logger.info(f"✅ Successfully deployed {deployed_count}/{len(agent_creators)} Azure AI agents")
        else:
            logger.warning("⚠️  No Azure AI agents deployed - will use LangGraph fallback")
        
        return _AZURE_AGENT_IDS.copy()
        
    except Exception as e:
        logger.warning(f"⚠️  Azure AI Agent Service not available: {e}")
        logger.warning("⚠️  Application will use LangGraph agents as fallback")
        return {}


def _deploy_claim_assessor(project_client: AIProjectClient) -> str:
    """Deploy or retrieve Claim Assessor agent.
    
    Args:
        project_client: Azure AI Project client
        
    Returns:
        Agent ID
    """
    from app.workflow.agents.azure_claim_assessor import create_claim_assessor_agent
    agent = create_claim_assessor_agent(project_client)
    return agent.id


def _deploy_policy_checker(project_client: AIProjectClient) -> str:
    """Deploy or retrieve Policy Checker agent.
    
    Args:
        project_client: Azure AI Project client
        
    Returns:
        Agent ID
    """
    from app.workflow.agents.azure_policy_checker import create_policy_checker_agent
    agent = create_policy_checker_agent(project_client)
    return agent.id


# Add more deployment functions as agents are migrated
# def _deploy_communication_agent(project_client: AIProjectClient) -> str:
#     from app.workflow.agents.azure_communication_agent import create_communication_agent
#     agent = create_communication_agent(project_client)
#     return agent.id
#
# def _deploy_risk_analyst(project_client: AIProjectClient) -> str:
#     from app.workflow.agents.azure_risk_analyst import create_risk_analyst_agent
#     agent = create_risk_analyst_agent(project_client)
#     return agent.id
