"""Azure AI Agent Service client management (New SDK)."""
import logging
from typing import Dict, Any, List
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_project_client = None


def get_project_client_v2() -> AIProjectClient:
    """Get or create a singleton AIProjectClient instance using new SDK.
    
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
        
        logger.info(f"Initializing Azure AI Project Client (v2): {settings.project_endpoint}")
        _project_client = AIProjectClient(
            endpoint=settings.project_endpoint,
            credential=DefaultAzureCredential()
        )
        logger.info("✅ Azure AI Project Client (v2) initialized")
    
    return _project_client


def run_agent_v2(agent_id: str, user_message: str, toolset=None) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Run an Azure AI Agent Service agent with a user message using new SDK.
    
    Args:
        agent_id: ID of the agent to run
        user_message: The user's input message
        toolset: Optional ToolSet with functions for the agent to use
        
    Returns:
        Tuple of (messages, usage_info) where usage_info contains token counts
    """
    project_client = get_project_client_v2()
    
    try:
        # Enable auto function calls if toolset provided
        if toolset:
            project_client.agents.enable_auto_function_calls(toolset)
            logger.debug(f"✅ Enabled auto function calls with toolset")
        
        # Create a thread for this conversation using threads.create()
        thread = project_client.agents.threads.create()
        logger.debug(f"Created thread: {thread.id}")
        
        # Add the user message to the thread using messages.create()
        message = project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )
        logger.debug(f"Added user message to thread")
        
        # Create and process the run using runs.create_and_process()
        logger.debug(f"Running agent {agent_id}...")
        run = project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent_id
        )
        
        logger.debug(f"Agent run completed with status: {run.status}")
        
        # Extract usage information if available
        usage_info = {}
        if hasattr(run, 'usage') and run.usage:
            logger.debug(f"📊 Agent run usage: {run.usage}")
            usage_info = {
                "prompt_tokens": getattr(run.usage, 'prompt_tokens', 0),
                "completion_tokens": getattr(run.usage, 'completion_tokens', 0),
                "total_tokens": getattr(run.usage, 'total_tokens', 0)
            }
        
        if run.status == "failed":
            error_msg = getattr(run, 'last_error', 'Unknown error')
            logger.error(f"Agent run failed: {error_msg}")
            return ([{
                "role": "assistant",
                "content": f"Error: Agent run failed - {error_msg}"
            }], usage_info)
        
        # Fetch all messages from the thread using messages.list()
        messages = project_client.agents.messages.list(thread_id=thread.id)
        
        # Convert to list format expected by the API
        result_messages = []
        for msg in messages:
            if hasattr(msg, 'role') and hasattr(msg, 'content'):
                # Handle different content formats
                content_text = ""
                if isinstance(msg.content, list):
                    for content_item in msg.content:
                        if hasattr(content_item, 'text'):
                            if hasattr(content_item.text, 'value'):
                                content_text += content_item.text.value
                            else:
                                content_text += str(content_item.text)
                elif isinstance(msg.content, str):
                    content_text = msg.content
                elif hasattr(msg.content, 'value'):
                    content_text = msg.content.value
                else:
                    content_text = str(msg.content)
                
                result_messages.append({
                    "role": msg.role,
                    "content": content_text
                })
        
        # Filter to only assistant responses (most recent first)
        assistant_messages = [m for m in result_messages if m["role"] == "assistant"]
        
        logger.debug(f"Retrieved {len(assistant_messages)} assistant messages")
        return (assistant_messages, usage_info)
        
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        return ([{
            "role": "assistant",
            "content": f"Error executing agent: {str(e)}"
        }], {})
