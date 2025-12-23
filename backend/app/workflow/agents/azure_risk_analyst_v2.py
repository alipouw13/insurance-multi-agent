"""Azure AI Agent Service - Risk Analyst agent (New SDK)."""
import logging
from typing import Dict, Any
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import FunctionTool, ToolSet
from azure.identity import DefaultAzureCredential
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_claimant_history(claimant_id: str) -> Dict[str, Any]:
    """Retrieve historical claim information for a given claimant.
    
    Args:
        claimant_id: The claimant's unique identifier
        
    Returns:
        Dictionary containing claimant history and risk factors
    """
    from app.workflow.tools import get_claimant_history as get_history_tool
    return get_history_tool.invoke(claimant_id)


def create_risk_analyst_agent_v2(project_client: AIProjectClient = None):
    """Create and return a configured Risk Analyst agent using new Azure AI Agent Service SDK.

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
        get_claimant_history,
    }
    
    # Create function tool and toolset using azure.ai.agents.models
    functions = FunctionTool(functions=user_functions)
    toolset = ToolSet()
    toolset.add(functions)
    
    # Enable automatic function calling
    project_client.agents.enable_auto_function_calls(toolset)
    
    # Agent instructions (prompt)
    instructions = """You are a risk analyst specializing in fraud detection and risk assessment for insurance claims.

Your responsibilities:
- Analyze claimant history for patterns of fraudulent behavior.
- Evaluate claim frequency and amounts against industry norms.
- Identify red flags in claim details (inconsistencies, suspicious timing, etc.).
- Assess the overall risk profile of the claimant.
- Provide a risk score and recommendation.

CRITICAL: ALWAYS call `get_claimant_history` to retrieve the claimant's history before analysis.

Key fraud indicators to check:
- Multiple claims in short time periods
- Claims shortly after policy inception
- Inconsistent damage descriptions
- Unusually high claim amounts
- History of policy cancellations
- Suspicious witness statements

Provide a detailed risk analysis with specific evidence.
End your analysis with a risk level: LOW RISK, MODERATE RISK, or HIGH RISK."""

    # Check if agent already exists by name
    try:
        # List all agents to find existing one
        agents = project_client.agents.list_agents()
        for agent in agents:
            if hasattr(agent, 'name') and agent.name == "risk_analyst_v2":
                logger.info(f"✅ Using existing Azure AI Agent: {agent.id} (risk_analyst_v2)")
                return agent, toolset
    except Exception as e:
        logger.debug(f"Could not list existing agents: {e}")
    
    # Create the agent using new SDK with toolset
    try:
        agent = project_client.agents.create_agent(
            model=settings.azure_openai_deployment_name or "gpt-4o",
            name="risk_analyst_v2",
            instructions=instructions,
            toolset=toolset,
        )
        logger.info(f"✅ Created Azure AI Agent (v2): {agent.id} (risk_analyst_v2)")
        return agent, toolset
    except Exception as e:
        logger.error(f"Failed to create risk analyst agent v2: {e}", exc_info=True)
        raise
