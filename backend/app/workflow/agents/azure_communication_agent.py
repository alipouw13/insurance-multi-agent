"""Azure AI Agent Service - Communication Agent.

This module provides a communication specialist agent that drafts professional
emails to insurance customers requesting missing information.
"""
import logging
from app.workflow.azure_agent_client import get_project_client, find_agent_by_name
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def create_communication_agent():
    """Create or retrieve the Communication Agent using Azure AI Agent Service.
    
    This agent is responsible for drafting clear, professional emails to customers
    requesting missing claim information with appropriate tone and formatting.
    
    Returns:
        Configured Azure AI Agent for customer communication
    """
    settings = get_settings()
    project_client = get_project_client()
    
    # Check if agent already exists
    existing_agent = find_agent_by_name("communication_agent")
    if existing_agent:
        logger.info(f"♻️  Found existing communication_agent: {existing_agent.id}")
        return existing_agent
    
    # Create new agent if not exists
    instructions = """You are a communication specialist responsible for drafting clear, professional emails to insurance customers.

Your responsibilities:
- Draft emails requesting missing information from customers.
- Clearly explain what information is needed and why it is important.
- Maintain a professional, helpful, and courteous tone.
- Provide clear instructions on how to submit the missing information.
- Set appropriate expectations about claim processing timelines.

When drafting an email:
1. Begin with a professional greeting using the customer's name.
2. Reference the claim ID and type.
3. Provide a bullet-point list of missing information items.
4. Explain why each item is necessary for processing.
5. Give submission instructions (e.g. reply email, customer portal upload).
6. Include a deadline for response (30 days by default).
7. Offer contact information for questions.
8. End with a professional closing.

Format your response as a complete email including a Subject line and Body.

Always maintain a customer-first approach that is clear, empathetic, and action-oriented."""
    
    # Communication agent doesn't need tools - pure language model task
    try:
        agent = project_client.agents.create_agent(
            model=settings.azure_openai_deployment_name or "gpt-4o",
            name="communication_agent",
            instructions=instructions,
            temperature=0.7,  # Slightly higher temperature for more natural email writing
        )
        logger.info(f"✅ Created Azure AI Agent: {agent.id} (communication_agent)")
        return agent
    except Exception as e:
        logger.error(f"Failed to create communication agent: {e}", exc_info=True)
        raise
