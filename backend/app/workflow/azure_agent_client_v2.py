"""Azure AI Agent Service client management (New SDK)."""
import json
import logging
import time
from typing import Dict, Any, List, Callable, Set, Optional
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AccessToken, TokenCredential
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_project_client = None
_fabric_project_client = None


class UserTokenCredential(TokenCredential):
    """Custom credential that uses a pre-obtained Azure AD user token.
    
    This credential is used for Fabric Data Agent which requires user identity
    passthrough (On-Behalf-Of). The token must be obtained from the frontend
    after user signs in with Azure AD.
    """
    
    def __init__(self, access_token: str, expires_on: int = None):
        """Initialize with an access token.
        
        Args:
            access_token: The Azure AD access token
            expires_on: Token expiration timestamp (defaults to 1 hour from now)
        """
        self._token = access_token
        # Default to 1 hour expiration if not specified
        self._expires_on = expires_on or (int(time.time()) + 3600)
    
    def get_token(self, *scopes, **kwargs) -> AccessToken:
        """Return the user's access token."""
        return AccessToken(self._token, self._expires_on)


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
        logger.info("[OK] Azure AI Project Client (v2) initialized")
    
    return _project_client


def get_project_client_with_user_token(user_token: str) -> AIProjectClient:
    """Create an AIProjectClient using a user's Azure AD token.
    
    This is required for Fabric Data Agent which uses identity passthrough (OBO).
    The user must sign in via Azure AD on the frontend and pass their token.
    
    Args:
        user_token: Azure AD access token from the user's frontend session
        
    Returns:
        AIProjectClient configured with user identity
    """
    settings = get_settings()
    
    if not settings.project_endpoint:
        raise ValueError(
            "PROJECT_ENDPOINT environment variable must be set. "
            "Find it in your Azure AI Foundry portal: "
            "Project Overview > Libraries > Foundry"
        )
    
    logger.info(f"[USER_TOKEN] Creating AIProjectClient with user token for Fabric OBO")
    user_credential = UserTokenCredential(user_token)
    
    client = AIProjectClient(
        endpoint=settings.project_endpoint,
        credential=user_credential
    )
    logger.info("[USER_TOKEN] AIProjectClient created with user identity")
    
    return client


def _get_fabric_project_client() -> AIProjectClient:
    """Get or create an AIProjectClient using user identity for Fabric Data Agent.
    
    Fabric Data Agent requires user identity (not service principal) for data access.
    DefaultAzureCredential picks up EnvironmentCredential (SPN) when AZURE_CLIENT_ID etc.
    are set, which Fabric rejects. This uses AzureCliCredential to ensure user identity.
    
    Returns:
        AIProjectClient configured with user identity credential
    """
    global _fabric_project_client
    
    if _fabric_project_client is None:
        from azure.identity import AzureCliCredential
        
        settings = get_settings()
        if not settings.project_endpoint:
            raise ValueError("PROJECT_ENDPOINT environment variable must be set.")
        
        logger.info("[FABRIC_CLIENT] Creating AIProjectClient with AzureCliCredential (user identity)")
        _fabric_project_client = AIProjectClient(
            endpoint=settings.project_endpoint,
            credential=AzureCliCredential()
        )
        logger.info("[FABRIC_CLIENT] AIProjectClient created with user identity")
    
    return _fabric_project_client


def run_agent_v2(
    agent_id: str, 
    user_message: str, 
    toolset=None, 
    functions: Optional[Dict[str, Callable]] = None,
    tool_choice: str = None,
    user_token: str = None,
    thread_id: str = None
) -> tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]], str]:
    """Run an Azure AI Agent Service agent with a user message using new SDK.
    
    This version uses manual tool execution for more reliable function calling.
    Instead of relying on enable_auto_function_calls which can have registration
    issues, we poll for tool calls and execute them ourselves.
    
    Args:
        agent_id: ID of the agent to run
        user_message: The user's input message
        toolset: Optional ToolSet with tool definitions (not used in manual mode)
        functions: Dict mapping function names to callable functions for manual execution
        tool_choice: Optional tool type to force (e.g., "fabric_dataagent" for FabricTool)
        user_token: Optional Azure AD user token for Fabric Data Agent authentication.
                    Required for Fabric Data Agent which uses identity passthrough (OBO).
        thread_id: Optional existing thread ID to continue a conversation
        
    Returns:
        Tuple of (messages, usage_info, tool_results, thread_id) where:
        - messages: List of assistant message dicts
        - usage_info: Dict with token counts  
        - tool_results: List of dicts with tool execution details (function_name, args, output)
        - thread_id: Thread ID for continuing the conversation
    """
    logger.info(f"[RUN_AGENT_V2] Called with agent_id={agent_id}, tool_choice={tool_choice}, has_functions={bool(functions)}, has_user_token={bool(user_token)}, thread_id={thread_id}")
    
    if not agent_id:
        logger.error("[RUN_AGENT_V2] agent_id is None or empty!")
        return ([{
            "role": "assistant",
            "content": "Error: Agent ID is not configured. Please check agent deployment."
        }], {}, [], None)
    
    # Use user token for Fabric Data Agent to enable identity passthrough (OBO)
    # This is required because Fabric Data Agent only supports user identity, not SPN
    if user_token and tool_choice == "fabric_dataagent":
        logger.info("[RUN_AGENT_V2] Using user token credential for Fabric Data Agent (OBO)")
        project_client = get_project_client_with_user_token(user_token)
    elif tool_choice == "fabric_dataagent":
        # Fabric Data Agent requires USER identity — DefaultAzureCredential may resolve to
        # EnvironmentCredential (service principal) if AZURE_CLIENT_ID/SECRET/TENANT_ID are
        # set in .env, which Fabric rejects with "Failed to retrieve data from conversational
        # data retrieval service." Use AzureCliCredential to ensure user identity.
        logger.info("[RUN_AGENT_V2] Using AzureCliCredential for Fabric Data Agent (user identity required)")
        project_client = _get_fabric_project_client()
    else:
        project_client = get_project_client_v2()
    
    # CRITICAL: Verify the agent still exists before attempting to run it
    # Agents can be deleted by other processes (diagnostic scripts, other backend instances)
    # If the agent is missing, fail fast with a clear error
    try:
        agent_check = project_client.agents.get_agent(agent_id=agent_id)
        logger.info(f"[RUN_AGENT_V2] Agent verified: {agent_check.name} (tools: {len(agent_check.tools) if agent_check.tools else 0})")
    except Exception as e:
        error_msg = str(e)
        if "No assistant found" in error_msg or "not found" in error_msg.lower():
            logger.error(f"[RUN_AGENT_V2] Agent {agent_id} NO LONGER EXISTS! The backend cache is stale.")
            logger.error(f"[RUN_AGENT_V2] SOLUTION: Restart the backend to recreate agents.")
            return ([{
                "role": "assistant",
                "content": f"Error: Agent no longer exists (ID: {agent_id}). Please restart the backend to recreate agents."
            }], {}, [], None)
        else:
            logger.warning(f"[RUN_AGENT_V2] Could not verify agent: {e}")
    
    try:
        # Create or reuse thread for this conversation
        if thread_id:
            logger.info(f"[RUN_AGENT_V2] Continuing conversation on existing thread: {thread_id}")
            current_thread_id = thread_id
            
            # Log existing thread messages for debugging
            try:
                existing_msgs = project_client.agents.messages.list(thread_id=current_thread_id)
                msg_list = list(existing_msgs)
                logger.info(f"[RUN_AGENT_V2] Thread has {len(msg_list)} existing messages")
                for i, msg in enumerate(msg_list[:5]):  # Log first 5
                    content = _extract_message_content(msg)
                    preview = content[:100] if len(content) > 100 else content
                    logger.info(f"[RUN_AGENT_V2]   Message {i+1}: role={msg.role}, preview='{preview}'")
            except Exception as e:
                logger.warning(f"[RUN_AGENT_V2] Could not list existing messages: {e}")
        else:
            thread = project_client.agents.threads.create()
            current_thread_id = thread.id
            logger.info(f"[RUN_AGENT_V2] Created new thread: {current_thread_id}")
        
        # Add the user message to the thread
        project_client.agents.messages.create(
            thread_id=current_thread_id,
            role="user",
            content=user_message
        )
        logger.info(f"[RUN_AGENT_V2] Added user message to thread (length: {len(user_message)} chars)")
        
        # If we have functions, use manual tool execution for reliability
        if functions:
            logger.info(f"[RUN_AGENT_V2] Using manual tool execution with {len(functions)} functions")
            messages, usage, tool_results = _run_agent_with_manual_tools(
                project_client, agent_id, current_thread_id, functions
            )
            return (messages, usage, tool_results, current_thread_id)
        else:
            # No functions, just run normally (but may use Azure-managed tools like FabricTool)
            logger.info(f"[RUN_AGENT_V2] Using simple mode (Azure-managed tools) with tool_choice={tool_choice}")
            messages, usage = _run_agent_simple(project_client, agent_id, current_thread_id, tool_choice)
            return (messages, usage, [], current_thread_id)  # No tool results in simple mode
        
    except Exception as e:
        logger.error(f"[RUN_AGENT_V2] Error running agent: {e}", exc_info=True)
        return ([{
            "role": "assistant",
            "content": f"Error executing agent: {str(e)}"
        }], {}, [], thread_id)


def _extract_message_content(msg) -> str:
    """Extract text content from an agent message.
    
    Args:
        msg: Message object from the agent API
        
    Returns:
        Text content as string
    """
    if isinstance(msg.content, list):
        for item in msg.content:
            if hasattr(item, 'text') and hasattr(item.text, 'value'):
                return item.text.value
        return ""
    else:
        return str(msg.content)


def _extract_fabric_output_from_run(project_client: AIProjectClient, thread_id: str, run_id: str) -> str | None:
    """Extract Fabric tool output from run steps.
    
    Sometimes the agent model doesn't include the Fabric output in its final message,
    but the tool call was successful. This function extracts the output directly.
    
    Note: The microsoft_fabric attribute is a dict, not an object, so we need to 
    use dict access (val.get('output')) rather than getattr().
    
    Args:
        project_client: AIProjectClient instance
        thread_id: Thread ID
        run_id: Run ID
        
    Returns:
        Fabric tool output string if found, None otherwise
    """
    try:
        steps = project_client.agents.run_steps.list(thread_id=thread_id, run_id=run_id)
        for step in steps:
            if hasattr(step, 'step_details') and step.step_details:
                tool_calls = getattr(step.step_details, 'tool_calls', [])
                for tc in tool_calls:
                    tc_type = getattr(tc, 'type', None)
                    logger.debug(f"[FABRIC] Checking tool call type: {tc_type}")
                    
                    # Try multiple attribute names for Fabric output
                    # Priority order: microsoft_fabric (current SDK), then legacy names
                    fabric_data = None
                    for attr_name in ['microsoft_fabric', 'fabric_dataagent', 'fabric']:
                        if hasattr(tc, attr_name):
                            fabric_data = getattr(tc, attr_name)
                            logger.debug(f"[FABRIC] Found attribute '{attr_name}' on tool call, type={type(fabric_data).__name__}")
                            break
                    
                    if fabric_data:
                        # Handle both dict and object types
                        output = None
                        if isinstance(fabric_data, dict):
                            output = fabric_data.get('output')
                            if output:
                                logger.info(f"[FABRIC] Extracted dict output from run steps ({len(output)} chars)")
                        else:
                            output = getattr(fabric_data, 'output', None)
                            if output:
                                logger.info(f"[FABRIC] Extracted object output from run steps ({len(output)} chars)")
                        
                        if output:
                            return output
                        else:
                            # Log available attributes for debugging
                            if isinstance(fabric_data, dict):
                                logger.debug(f"[FABRIC] fabric_data dict keys: {list(fabric_data.keys())}")
                            else:
                                attrs = [a for a in dir(fabric_data) if not a.startswith('_')]
                                logger.debug(f"[FABRIC] fabric_data attributes: {attrs}")
    except Exception as e:
        logger.warning(f"[FABRIC] Failed to extract output from run steps: {e}")
    return None


def _run_agent_simple(
    project_client: AIProjectClient, 
    agent_id: str, 
    thread_id: str,
    tool_choice: str = None,
    max_retries: int = 3
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Run agent without tool handling (simple mode).
    
    Used for agents with Azure-managed tools (like FabricTool) that don't need
    local function execution. Azure AI Agent Service handles tool invocations
    automatically via create_and_process.
    
    Args:
        project_client: AIProjectClient instance
        agent_id: ID of the agent to run
        thread_id: ID of the thread to run in
        tool_choice: Optional tool type to force (e.g., "fabric_dataagent" for FabricTool)
                     When set, passes tool_choice to create_and_process to FORCE tool usage.
        max_retries: Number of retries for failures (reduced from 5 to 3 with tool_choice fix)
    """
    import time as time_module
    from datetime import datetime
    
    start_time = time_module.time()
    logger.info(f"[SIMPLE_RUN] Starting agent run: agent_id={agent_id}, tool_choice={tool_choice}")
    
    # Build run parameters
    run_kwargs = {
        "thread_id": thread_id,
        "agent_id": agent_id
    }
    
    # Pass tool_choice to force tool invocation when specified.
    # The tool_choice parameter must be a dict with {"type": "<tool_type>"} format.
    # See inspect_agent.py which successfully uses tool_choice={"type": "fabric_dataagent"}.
    if tool_choice:
        # Convert string format to dict format if needed
        if isinstance(tool_choice, str):
            run_kwargs["tool_choice"] = {"type": tool_choice}
        else:
            run_kwargs["tool_choice"] = tool_choice
        logger.info(f"[SIMPLE_RUN] Using create_and_process with tool_choice={run_kwargs['tool_choice']}")
    else:
        logger.info(f"[SIMPLE_RUN] Using create_and_process without tool_choice (auto mode)")
    
    # Retry logic for Fabric tool connectivity issues and server errors
    # Reduced retries since Fabric is generally working
    retry_count = 0
    last_messages = None
    last_usage = {}
    retry_delays = [2, 3, 5]  # 3 retries with shorter delays
    
    while retry_count < max_retries:
        attempt_start = time_module.time()
        logger.info(f"[SIMPLE_RUN] -------- ATTEMPT {retry_count + 1}/{max_retries} --------")
        logger.info(f"[SIMPLE_RUN] Thread: {thread_id}, Agent: {agent_id}")
        
        try:
            # Use create_and_process — the standard pattern from MS docs
            # Pass tool_choice from run_kwargs to force tool invocation when configured
            logger.info(f"[SIMPLE_RUN] Creating run with create_and_process (kwargs: {list(run_kwargs.keys())})...")
            run = project_client.agents.runs.create_and_process(
                **run_kwargs
            )
            
            attempt_duration = time_module.time() - attempt_start
            
            logger.info(f"[SIMPLE_RUN] Run completed in {attempt_duration:.1f}s")
            logger.info(f"[SIMPLE_RUN] Run ID: {run.id}")
            logger.info(f"[SIMPLE_RUN] Run Status: {run.status}")
            
            # Log run metadata for debugging
            if hasattr(run, 'model'):
                logger.info(f"[SIMPLE_RUN] Model: {run.model}")
            if hasattr(run, 'created_at'):
                logger.info(f"[SIMPLE_RUN] Created at: {run.created_at}")
            if hasattr(run, 'completed_at'):
                logger.info(f"[SIMPLE_RUN] Completed at: {run.completed_at}")
                
        except Exception as run_error:
            attempt_duration = time_module.time() - attempt_start
            logger.error(f"[SIMPLE_RUN] Exception during run creation ({attempt_duration:.1f}s): {type(run_error).__name__}: {run_error}")
            
            if retry_count < max_retries - 1:
                retry_count += 1
                delay = retry_delays[min(retry_count - 1, len(retry_delays) - 1)]
                logger.warning(f"[SIMPLE_RUN] Will retry in {delay}s...")
                time_module.sleep(delay)
                
                # Create new thread for retry
                new_thread = project_client.agents.threads.create()
                original_messages = project_client.agents.messages.list(thread_id=thread_id)
                for msg in original_messages:
                    if msg.role == "user":
                        content_text = _extract_message_content(msg)
                        project_client.agents.messages.create(
                            thread_id=new_thread.id,
                            role="user",
                            content=content_text
                        )
                        break
                thread_id = new_thread.id
                run_kwargs["thread_id"] = thread_id
                continue
            else:
                return ([{
                    "role": "assistant",
                    "content": f"Error: Failed to execute agent after {max_retries} attempts - {run_error}"
                }], {})
        
        # Only fetch detailed run steps for Fabric runs or failures (avoid extra API calls)
        run_steps = None
        if tool_choice == "fabric_dataagent" or run.status == "failed":
            run_steps = _get_run_steps(project_client, thread_id, run.id)
            if run_steps:
                logger.debug(f"[SIMPLE_RUN] Run had {len(run_steps)} steps")
                for i, step in enumerate(run_steps):
                    step_type = getattr(step, 'type', 'unknown')
                    step_status = getattr(step, 'status', 'unknown')
                    logger.debug(f"  Run step {i+1}: type={step_type}, status={step_status}")
                    
                    if hasattr(step, 'last_error') and step.last_error:
                        logger.error(f"    Step error: {step.last_error}")
        
        last_usage = _extract_usage(run)
        
        # Handle run failures - retry on server errors
        if run.status == "failed":
            error_msg = getattr(run, 'last_error', 'Unknown error')
            
            # Extract detailed error information
            error_code = 'unknown'
            error_message = str(error_msg)
            if isinstance(error_msg, dict):
                error_code = error_msg.get('code', 'unknown')
                error_message = error_msg.get('message', str(error_msg))
            elif hasattr(error_msg, 'code'):
                error_code = error_msg.code
                error_message = getattr(error_msg, 'message', str(error_msg))
            
            logger.error(f"[SIMPLE_RUN] ❌ Run FAILED")
            logger.error(f"[SIMPLE_RUN]   Error code: {error_code}")
            logger.error(f"[SIMPLE_RUN]   Error message: {error_message}")
            logger.error(f"[SIMPLE_RUN]   Run ID: {run.id}")
            logger.error(f"[SIMPLE_RUN]   Thread ID: {thread_id}")
            logger.error(f"[SIMPLE_RUN]   Agent ID: {agent_id}")
            
            # Log incomplete_details if available (often contains Fabric-specific errors)
            if hasattr(run, 'incomplete_details') and run.incomplete_details:
                logger.error(f"[SIMPLE_RUN]   Incomplete details: {run.incomplete_details}")
            
            # Log required_action if the run was waiting for something
            if hasattr(run, 'required_action') and run.required_action:
                logger.error(f"[SIMPLE_RUN]   Required action: {run.required_action}")
            
            # Try to get more context from run steps
            if run_steps:
                for step in run_steps:
                    if getattr(step, 'status', '') == 'failed':
                        step_error = getattr(step, 'last_error', None)
                        if step_error:
                            logger.error(f"[SIMPLE_RUN]   Step {step.id} failed: {step_error}")
            
            logger.error(f"[SIMPLE_RUN] Full error object: {json.dumps(error_msg) if isinstance(error_msg, dict) else repr(error_msg)}")
            logger.error(f"[SIMPLE_RUN] Tool choice was: {tool_choice if tool_choice else 'auto (create_and_process)'}")
            
            # Check if this is a retryable server error
            error_str = str(error_msg).lower()
            is_retryable = any(phrase in error_str for phrase in [
                "server_error", "something went wrong", "internal error", 
                "service unavailable", "timeout", "rate limit", "throttl",
                "capacity", "overload", "busy", "temporarily unavailable"
            ])
            
            if is_retryable and retry_count < max_retries - 1:
                retry_count += 1
                delay = retry_delays[min(retry_count - 1, len(retry_delays) - 1)]
                logger.warning(f"[SIMPLE_RUN] ⚠️ Retryable error detected, will retry in {delay}s ({retry_count}/{max_retries})...")
                
                # Create a new thread for retry
                new_thread = project_client.agents.threads.create()
                original_messages = project_client.agents.messages.list(thread_id=thread_id)
                for msg in original_messages:
                    if msg.role == "user":
                        content_text = _extract_message_content(msg)
                        project_client.agents.messages.create(
                            thread_id=new_thread.id,
                            role="user",
                            content=content_text
                        )
                        break
                thread_id = new_thread.id
                run_kwargs["thread_id"] = thread_id
                time_module.sleep(delay)
                continue
            else:
                total_duration = time_module.time() - start_time
                logger.error(f"[SIMPLE_RUN] ❌ Non-retryable error or max retries reached (total time: {total_duration:.1f}s)")
                return ([{
                    "role": "assistant",
                    "content": f"Error: Agent run failed - {error_msg}"
                }], last_usage)
        
        # Get the messages
        last_messages = _get_assistant_messages(project_client, thread_id)
        
        # For Fabric tool runs, verify the tool was actually invoked
        if tool_choice == "fabric_dataagent" and last_messages:
            response_text = last_messages[-1].get("content", "") if last_messages else ""
            logger.info(f"[SIMPLE_RUN] Fabric response length: {len(response_text)} chars")
            logger.info(f"[SIMPLE_RUN] Response preview: {response_text[:300]}...")
            
            # Check run steps to verify Fabric tool was invoked
            if not run_steps:
                run_steps = _get_run_steps(project_client, thread_id, run.id)
            
            tool_was_invoked = False
            if run_steps:
                for step in run_steps:
                    if getattr(step, 'type', '') == 'tool_calls':
                        tool_was_invoked = True
                        break
            
            if not tool_was_invoked:
                logger.warning(f"[SIMPLE_RUN] ⚠️ Fabric tool was NOT invoked in run steps!")
                
                # Check if Fabric tool returned data in run steps that the model didn't include
                fabric_output = _extract_fabric_output_from_run(project_client, thread_id, run.id)
                if fabric_output and len(fabric_output) > 100:
                    logger.info(f"[SIMPLE_RUN] Found Fabric data in run steps ({len(fabric_output)} chars) - using direct output")
                    import re
                    clean_output = re.sub(r'【\d+:\d+†source】\s*', '', fabric_output)
                    last_messages = [{"role": "assistant", "content": clean_output}]
                elif retry_count < max_retries - 1:
                    # Tool wasn't invoked — retry with a new thread
                    retry_count += 1
                    delay = retry_delays[min(retry_count - 1, len(retry_delays) - 1)]
                    logger.warning(f"[SIMPLE_RUN] Retrying in {delay}s ({retry_count}/{max_retries})...")
                    new_thread = project_client.agents.threads.create()
                    original_messages = project_client.agents.messages.list(thread_id=thread_id)
                    for msg in original_messages:
                        if msg.role == "user":
                            content_text = _extract_message_content(msg)
                            project_client.agents.messages.create(
                                thread_id=new_thread.id,
                                role="user",
                                content=content_text
                            )
                            break
                    thread_id = new_thread.id
                    run_kwargs["thread_id"] = thread_id
                    time_module.sleep(delay)
                    continue
                else:
                    total_duration = time_module.time() - start_time
                    logger.error(f"[SIMPLE_RUN] Fabric tool not invoked after {max_retries} attempts ({total_duration:.1f}s)")
            else:
                # Tool was invoked — check if model relayed the data or gave a generic error
                # If the model says it can't access data but the tool DID run, extract tool output directly
                fabric_error_indicators = [
                    "unable to retrieve", "unable to access", "cannot access",
                    "having trouble", "technical difficulties", "connectivity issue",
                    "do not have direct access", "currently unable"
                ]
                response_lower = response_text.lower()
                has_fabric_error = any(phrase in response_lower for phrase in fabric_error_indicators)
                
                if has_fabric_error:
                    fabric_output = _extract_fabric_output_from_run(project_client, thread_id, run.id)
                    if fabric_output and len(fabric_output) > 100:
                        logger.info(f"[SIMPLE_RUN] Tool invoked but model gave error — using direct Fabric output ({len(fabric_output)} chars)")
                        import re
                        clean_output = re.sub(r'【\d+:\d+†source】\s*', '', fabric_output)
                        last_messages = [{"role": "assistant", "content": clean_output}]
                    else:
                        logger.warning(f"[SIMPLE_RUN] Tool invoked but returned error. Response: {response_text[:200]}")
                else:
                    total_duration = time_module.time() - start_time
                    logger.info(f"[SIMPLE_RUN] ✅ Fabric tool returned data successfully in {total_duration:.1f}s")
            break
        else:
            # Not a Fabric tool call, no need to check for retries
            total_duration = time_module.time() - start_time
            logger.info(f"[SIMPLE_RUN] ✅ Agent completed successfully in {total_duration:.1f}s")
            break
    
    logger.info(f"[SIMPLE_RUN] ========== END AGENT RUN ==========")
    return (last_messages or [], last_usage)


def _run_agent_with_manual_tools(
    project_client: AIProjectClient,
    agent_id: str,
    thread_id: str,
    functions: Dict[str, Callable],
    max_iterations: int = 10
) -> tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    """Run agent with manual tool execution loop.
    
    This approach:
    1. Creates a run
    2. Polls until complete or requires_action
    3. If requires_action, execute the tool calls manually
    4. Submit tool outputs back
    5. Repeat until done
    
    Returns:
        Tuple of (messages, usage_info, tool_results) where tool_results contains
        each tool call with its function name, arguments, and output
    """
    # Create the run (not create_and_process - we handle processing ourselves)
    run = project_client.agents.runs.create(
        thread_id=thread_id,
        agent_id=agent_id
    )
    logger.info(f"Created run {run.id} for agent {agent_id}")
    logger.info(f"Available functions for tool calls: {list(functions.keys())}")
    
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    tool_results: List[Dict[str, Any]] = []  # Collect all tool executions
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # Poll for run status
        run = _poll_run_status(project_client, thread_id, run.id)
        logger.info(f"Run status: {run.status} (iteration {iteration})")
        
        # Accumulate usage if available
        if hasattr(run, 'usage') and run.usage:
            total_usage["prompt_tokens"] += getattr(run.usage, 'prompt_tokens', 0)
            total_usage["completion_tokens"] += getattr(run.usage, 'completion_tokens', 0)
            total_usage["total_tokens"] += getattr(run.usage, 'total_tokens', 0)
        
        if run.status == "completed":
            logger.info(f"Run completed successfully after {iteration} iterations")
            logger.info(f"Captured {len(tool_results)} tool call results")
            return (_get_assistant_messages(project_client, thread_id), total_usage, tool_results)
        
        elif run.status == "failed":
            error_msg = getattr(run, 'last_error', 'Unknown error')
            logger.error(f"Run failed: {error_msg}")
            return ([{
                "role": "assistant",
                "content": f"Error: Agent run failed - {error_msg}"
            }], total_usage, tool_results)
        
        elif run.status == "requires_action":
            # Handle tool calls
            tool_calls = _get_required_tool_calls(run)
            if not tool_calls:
                logger.warning("requires_action but no tool calls found")
                break
            
            logger.info(f"Processing {len(tool_calls)} tool call(s)")
            tool_outputs = []
            
            for tool_call in tool_calls:
                tool_call_id = tool_call.get("id")
                function_name = tool_call.get("function", {}).get("name")
                arguments_str = tool_call.get("function", {}).get("arguments", "{}")
                
                logger.info(f"  Tool call: {function_name}")
                
                # Execute the function
                if function_name in functions:
                    try:
                        # Parse arguments
                        args = json.loads(arguments_str) if arguments_str else {}
                        
                        # Call the function
                        logger.debug(f"  Executing {function_name} with args: {list(args.keys())}")
                        result = functions[function_name](**args)
                        
                        logger.info(f"  [OK] {function_name} executed successfully")
                        
                        # Capture tool result for trace output
                        tool_results.append({
                            "function_name": function_name,
                            "arguments": args,
                            "output": str(result),
                            "success": True
                        })
                        
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "output": str(result)
                        })
                    except Exception as e:
                        logger.error(f"  [ERROR] Error executing {function_name}: {e}")
                        error_output = f"Error executing {function_name}: {str(e)}"
                        
                        # Capture error for trace output
                        tool_results.append({
                            "function_name": function_name,
                            "arguments": args if 'args' in locals() else {},
                            "output": error_output,
                            "success": False,
                            "error": str(e)
                        })
                        
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "output": error_output
                        })
                else:
                    logger.warning(f"  [WARN] Function '{function_name}' not found in provided functions")
                    error_output = f"Error: Function '{function_name}' is not available"
                    
                    # Capture error for trace output
                    tool_results.append({
                        "function_name": function_name,
                        "arguments": {},
                        "output": error_output,
                        "success": False,
                        "error": "Function not found"
                    })
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call_id,
                        "output": error_output
                    })
            
            # Submit tool outputs back to the run
            if tool_outputs:
                run = project_client.agents.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
                logger.debug(f"Submitted {len(tool_outputs)} tool outputs")
        
        elif run.status in ["queued", "in_progress"]:
            # Still processing, wait and poll again
            time.sleep(0.2)
        
        else:
            logger.warning(f"Unexpected run status: {run.status}")
            break
    
    logger.warning(f"Max iterations ({max_iterations}) reached")
    return (_get_assistant_messages(project_client, thread_id), total_usage, tool_results)


def _poll_run_status(
    project_client: AIProjectClient,
    thread_id: str,
    run_id: str,
    timeout_seconds: int = 120
) -> Any:
    """Poll until run reaches a terminal or actionable state."""
    start_time = time.time()
    terminal_states = {"completed", "failed", "cancelled", "expired", "requires_action"}
    poll_interval = 0.2  # Start with fast polling
    
    while True:
        run = project_client.agents.runs.get(thread_id=thread_id, run_id=run_id)
        
        if run.status in terminal_states:
            return run
        
        if time.time() - start_time > timeout_seconds:
            logger.warning(f"Polling timeout after {timeout_seconds}s, status: {run.status}")
            return run
        
        time.sleep(poll_interval)
        # Gradually increase interval to reduce API calls on long-running agents
        poll_interval = min(poll_interval * 1.3, 1.0)


def _get_run_steps(
    project_client: AIProjectClient,
    thread_id: str,
    run_id: str
) -> list:
    """Get the steps executed during a run (for debugging tool calls)."""
    try:
        # Correct API path: agents.run_steps.list (not agents.runs.steps.list)
        steps = project_client.agents.run_steps.list(
            thread_id=thread_id,
            run_id=run_id
        )
        return list(steps)
    except Exception as e:
        logger.debug(f"Could not retrieve run steps: {e}")
        return []


def _get_required_tool_calls(run) -> List[Dict[str, Any]]:
    """Extract tool calls from a run in requires_action state."""
    tool_calls = []
    
    if not hasattr(run, 'required_action') or not run.required_action:
        return tool_calls
    
    action = run.required_action
    if not hasattr(action, 'submit_tool_outputs') or not action.submit_tool_outputs:
        return tool_calls
    
    submit_tool_outputs = action.submit_tool_outputs
    if not hasattr(submit_tool_outputs, 'tool_calls'):
        return tool_calls
    
    for tc in submit_tool_outputs.tool_calls:
        tool_call_dict = {
            "id": getattr(tc, 'id', None),
            "type": getattr(tc, 'type', 'function'),
            "function": {
                "name": getattr(tc.function, 'name', None) if hasattr(tc, 'function') else None,
                "arguments": getattr(tc.function, 'arguments', '{}') if hasattr(tc, 'function') else '{}'
            }
        }
        tool_calls.append(tool_call_dict)
    
    return tool_calls


def _extract_usage(run) -> Dict[str, int]:
    """Extract usage information from a run."""
    usage_info = {}
    if hasattr(run, 'usage') and run.usage:
        usage_info = {
            "prompt_tokens": getattr(run.usage, 'prompt_tokens', 0),
            "completion_tokens": getattr(run.usage, 'completion_tokens', 0),
            "total_tokens": getattr(run.usage, 'total_tokens', 0)
        }
    return usage_info


def _get_assistant_messages(
    project_client: AIProjectClient,
    thread_id: str
) -> List[Dict[str, Any]]:
    """Get assistant messages from a thread."""
    messages = project_client.agents.messages.list(thread_id=thread_id)
    
    result_messages = []
    for msg in messages:
        if hasattr(msg, 'role') and hasattr(msg, 'content'):
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
    
    # Filter to only assistant responses
    return [m for m in result_messages if m["role"] == "assistant"]
