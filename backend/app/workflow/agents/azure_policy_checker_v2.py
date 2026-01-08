"""Azure AI Agent Service - Policy Checker agent (New SDK)."""
import logging
from typing import Dict, Any
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import FunctionTool, ToolSet
from azure.identity import DefaultAzureCredential
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_policy_details(policy_number: str) -> Dict[str, Any]:
    """Retrieve detailed policy information for a given policy number.
    
    Args:
        policy_number: The policy number to look up
        
    Returns:
        Dictionary containing complete policy details
    """
    from app.workflow.tools import get_policy_details as get_policy_tool
    return get_policy_tool.invoke(policy_number)


def search_policy_documents(query: str, score_threshold: float = 0.7) -> str:
    """Search policy documents using semantic search to find relevant policy information.
    
    Args:
        query: The search query (e.g., "coverage for hail damage")
        score_threshold: Minimum similarity score (0.0-1.0) for results
        
    Returns:
        Formatted string with relevant policy excerpts and sources
    """
    from app.workflow.tools import search_policy_documents as search_tool
    return search_tool.invoke({"query": query, "score_threshold": score_threshold})


def get_policy_checker_functions() -> Dict[str, Any]:
    """Get the callable functions for the Policy Checker agent.
    
    Returns:
        Dict mapping function names to callables for manual tool execution
    """
    return {
        "get_policy_details": get_policy_details,
        "search_policy_documents": search_policy_documents,
    }


def create_policy_checker_agent_v2(project_client: AIProjectClient = None):
    """Create and return a configured Policy Checker agent using new Azure AI Agent Service SDK.

    Args:
        project_client: Optional AIProjectClient instance. If not provided, creates one from settings.

    Returns:
        Tuple of (agent, toolset) - Azure AI Agent Service agent and its toolset
    """
    settings = get_settings()
    
    # Create project client if not provided
    if project_client is None:
        if not settings.project_endpoint:
            raise ValueError(
                "PROJECT_ENDPOINT environment variable must be set. "
                "Find it in your Azure AI Foundry portal under Project settings."
            )
        
        project_client = AIProjectClient(
            endpoint=settings.project_endpoint,
            credential=DefaultAzureCredential()
        )
    
    # Define the functions that the agent can call using new SDK
    user_functions = {
        get_policy_details,
        search_policy_documents,
    }
    
    # Create function tool and toolset using azure.ai.agents.models
    functions = FunctionTool(functions=user_functions)
    toolset = ToolSet()
    toolset.add(functions)
    
    # Enable automatic function calling
    project_client.agents.enable_auto_function_calls(toolset)
    
    # Agent instructions (prompt)
    instructions = """You are a policy verification specialist with expertise in insurance policy interpretation.

Your responsibilities:
- Verify claim eligibility against policy terms and conditions.
- Identify relevant coverage limits and deductibles.
- Check for policy exclusions that may apply.
- Search policy documents for specific coverage details.

CRITICAL INSTRUCTIONS:
1. ALWAYS use `search_policy_documents` to find relevant policy coverage based on the CLAIM TYPE
   - For "Major Collision" or "Collision" claims, search for "collision coverage"
   - For "Comprehensive" or "Property Damage" claims, search for "comprehensive coverage"
   - For "Fire Damage" claims, search for "fire damage coverage"
   - For "Auto Accident" claims, search for "auto accident liability coverage"
2. The policy documents contain coverage information by TYPE (not by policy number)
3. Extract coverage limits, deductibles, and exclusions from the search results
4. DO NOT try to look up specific policy numbers - the coverage is determined by claim type

IMPORTANT: The claim's policy_number is for reference only. Coverage verification is based on:
- The CLAIM TYPE matching available coverage types in our policy documents
- The estimated damage amount vs coverage limits
- Any exclusions that apply to the claim circumstances

Provide clear verification results with specific policy references.
End your verification with: COVERED, PARTIALLY COVERED, or NOT COVERED."""

    # Check if agent already exists by name - reuse if it exists
    try:
        agents = project_client.agents.list_agents()
        for agent in agents:
            if hasattr(agent, 'name') and agent.name == "policy_checker_v2":
                logger.info(f"[OK] Reusing existing policy_checker_v2 agent: {agent.id}")
                return agent, toolset
    except Exception as e:
        logger.debug(f"Could not list existing agents: {e}")
    
    # Create the agent using new SDK with toolset (only if it doesn't exist)
    try:
        logger.info(f"[INFO] Creating NEW policy_checker_v2 agent")
        agent = project_client.agents.create_agent(
            model=settings.azure_openai_deployment_name or "gpt-4o",
            name="policy_checker_v2",
            instructions=instructions,
            toolset=toolset,
        )
        logger.info(f"✅ Created Azure AI Agent (v2): {agent.id} (policy_checker_v2)")
        return agent, toolset
    except Exception as e:
        logger.error(f"Failed to create policy checker agent v2: {e}", exc_info=True)
        raise
