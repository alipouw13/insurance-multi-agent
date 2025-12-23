"""Azure AI Agent Service - Communication Agent (New SDK)."""
import logging
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def create_communication_agent_v2(project_client: AIProjectClient = None):
    """Create and return a configured Communication agent using new Azure AI Agent Service SDK.

    Args:
        project_client: Optional AIProjectClient instance. If not provided, creates one from settings.

    Returns:
        Tuple of (agent, toolset) - Azure AI Agent Service agent and None (no tools)
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
    
    # Agent instructions (prompt) - Communication agent doesn't need tools
    instructions = """You are a communication specialist for an insurance company, responsible for drafting professional and empathetic correspondence with claimants.

Your responsibilities:
- Draft clear, professional emails to claimants based on claim assessment results.
- Request additional documentation when needed.
- Explain claim decisions in an understandable and empathetic manner.
- Maintain a professional yet friendly tone.
- Ensure all communications comply with insurance industry standards.

Guidelines:
- Be empathetic and understanding of the claimant's situation.
- Use clear, jargon-free language.
- Provide specific next steps and timelines.
- Include all necessary legal disclaimers.
- Maintain a professional tone even when delivering unfavorable news.

Always structure emails with:
1. Greeting and claim reference
2. Clear explanation of the situation/decision
3. Specific next steps or requirements
4. Contact information for questions
5. Professional closing"""

    # Check if agent already exists by name
    try:
        # List all agents to find existing one
        agents = project_client.agents.list_agents()
        for agent in agents:
            if hasattr(agent, 'name') and agent.name == "communication_agent_v2":
                logger.info(f"✅ Using existing Azure AI Agent: {agent.id} (communication_agent_v2)")
                return agent, None  # No toolset for communication agent
    except Exception as e:
        logger.debug(f"Could not list existing agents: {e}")
    
    # Create the agent using new SDK (no tools needed for communication agent)
    try:
        agent = project_client.agents.create_agent(
            model=settings.azure_openai_deployment_name or "gpt-4o",
            name="communication_agent_v2",
            instructions=instructions,
        )
        logger.info(f"✅ Created Azure AI Agent (v2): {agent.id} (communication_agent_v2)")
        return agent, None  # No toolset for communication agent
    except Exception as e:
        logger.error(f"Failed to create communication agent v2: {e}", exc_info=True)
        raise
