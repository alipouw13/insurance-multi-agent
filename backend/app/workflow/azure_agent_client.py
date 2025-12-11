"""Azure AI Agent Service client management and execution helpers."""
import logging
from typing import Dict, Any, List
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_project_client = None


def get_project_client() -> AIProjectClient:
    """Get or create a singleton AIProjectClient instance.
    
    Returns:
        AIProjectClient configured with project endpoint and credentials
    """
    global _project_client
    
    if _project_client is None:
        settings = get_settings()
        
        if not settings.project_endpoint:
            raise ValueError(
                "PROJECT_ENDPOINT environment variable must be set. "
                "Find it in your Azure AI Foundry portal: "
                "Project Overview > Libraries > Foundry"
            )
        
        logger.info(f"Initializing Azure AI Project Client: {settings.project_endpoint}")
        _project_client = AIProjectClient(
            endpoint=settings.project_endpoint,
            credential=DefaultAzureCredential()
        )
        logger.info("✅ Azure AI Project Client initialized")
    
    return _project_client


def run_agent(agent_id: str, user_message: str) -> List[Dict[str, Any]]:
    """Run an Azure AI Agent Service agent with a user message.
    
    Args:
        agent_id: ID of the agent to run
        user_message: The user's input message
        
    Returns:
        List of messages from the agent's response
    """
    project_client = get_project_client()
    
    try:
        # Create a thread for this conversation
        thread = project_client.agents.threads.create()
        logger.info(f"Created thread: {thread.id}")
        
        # Add the user message to the thread
        message = project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )
        logger.info(f"Added user message to thread: {message['id']}")
        
        # Create and process the run
        logger.info(f"Running agent {agent_id}...")
        run = project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent_id
        )
        logger.info(f"Agent run completed with status: {run.status}")
        
        if run.status == "failed":
            logger.error(f"Agent run failed: {run.last_error}")
            return [{
                "role": "assistant",
                "content": f"Error: Agent run failed - {run.last_error}"
            }]
        
        # Fetch all messages from the thread
        messages = project_client.agents.messages.list(thread_id=thread.id)
        
        # Convert to list format expected by the API
        result_messages = []
        for msg in messages:
            result_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return result_messages
        
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        raise


def delete_agent(agent_id: str):
    """Delete an Azure AI Agent Service agent.
    
    Args:
        agent_id: ID of the agent to delete
    """
    project_client = get_project_client()
    try:
        project_client.agents.delete_agent(agent_id)
        logger.info(f"Deleted agent: {agent_id}")
    except Exception as e:
        logger.error(f"Error deleting agent: {e}", exc_info=True)
        raise
