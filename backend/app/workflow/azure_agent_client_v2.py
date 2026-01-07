"""Azure AI Agent Service client management (New SDK)."""
import json
import logging
import time
from typing import Dict, Any, List, Callable, Set, Optional
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
        logger.info("[OK] Azure AI Project Client (v2) initialized")
    
    return _project_client


def run_agent_v2(
    agent_id: str, 
    user_message: str, 
    toolset=None, 
    functions: Optional[Dict[str, Callable]] = None,
    tool_choice: str = None
) -> tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
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
        
    Returns:
        Tuple of (messages, usage_info, tool_results) where:
        - messages: List of assistant message dicts
        - usage_info: Dict with token counts  
        - tool_results: List of dicts with tool execution details (function_name, args, output)
    """
    logger.info(f"[RUN_AGENT_V2] Called with agent_id={agent_id}, tool_choice={tool_choice}, has_functions={bool(functions)}")
    
    if not agent_id:
        logger.error("[RUN_AGENT_V2] agent_id is None or empty!")
        return ([{
            "role": "assistant",
            "content": "Error: Agent ID is not configured. Please check agent deployment."
        }], {}, [])
    
    project_client = get_project_client_v2()
    
    try:
        # Create a thread for this conversation
        thread = project_client.agents.threads.create()
        logger.info(f"[RUN_AGENT_V2] Created thread: {thread.id}")
        
        # Add the user message to the thread
        project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )
        logger.info(f"[RUN_AGENT_V2] Added user message to thread (length: {len(user_message)} chars)")
        
        # If we have functions, use manual tool execution for reliability
        if functions:
            logger.info(f"[RUN_AGENT_V2] Using manual tool execution with {len(functions)} functions")
            return _run_agent_with_manual_tools(
                project_client, agent_id, thread.id, functions
            )
        else:
            # No functions, just run normally (but may use Azure-managed tools like FabricTool)
            logger.info(f"[RUN_AGENT_V2] Using simple mode (Azure-managed tools) with tool_choice={tool_choice}")
            messages, usage = _run_agent_simple(project_client, agent_id, thread.id, tool_choice)
            return (messages, usage, [])  # No tool results in simple mode
        
    except Exception as e:
        logger.error(f"[RUN_AGENT_V2] Error running agent: {e}", exc_info=True)
        return ([{
            "role": "assistant",
            "content": f"Error executing agent: {str(e)}"
        }], {}, [])


def _run_agent_simple(
    project_client: AIProjectClient, 
    agent_id: str, 
    thread_id: str,
    tool_choice: str = None
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
    """
    logger.info(f"[SIMPLE_RUN] Running agent {agent_id} in simple mode (Azure-managed tools)")
    
    # Build run parameters
    run_kwargs = {
        "thread_id": thread_id,
        "agent_id": agent_id
    }
    
    # Add tool_choice if specified (forces the tool to be invoked)
    if tool_choice:
        run_kwargs["tool_choice"] = {"type": tool_choice}
        logger.info(f"[SIMPLE_RUN] Forcing tool_choice: {tool_choice}")
    
    logger.info(f"[SIMPLE_RUN] Creating run with kwargs: thread_id={thread_id}, agent_id={agent_id}, tool_choice={tool_choice}")
    run = project_client.agents.runs.create_and_process(**run_kwargs)
    
    logger.info(f"[SIMPLE_RUN] Agent run completed - Status: {run.status}")
    if run.status == "failed":
        logger.error(f"[SIMPLE_RUN] Run failed with error: {getattr(run, 'last_error', 'Unknown')}")
    
    # Log additional run details for debugging Fabric integration
    if hasattr(run, 'tools') and run.tools:
        logger.info(f"[SIMPLE_RUN] Agent tools configured: {[t.type if hasattr(t, 'type') else str(t) for t in run.tools]}")
    
    # Check for tool calls that were made during the run
    run_steps = _get_run_steps(project_client, thread_id, run.id)
    if run_steps:
        logger.info(f"[SIMPLE_RUN] Run had {len(run_steps)} steps")
        for step in run_steps:
            step_type = getattr(step, 'type', 'unknown')
            logger.info(f"  Run step: {step_type}")
            if step_type == 'tool_calls' and hasattr(step, 'step_details'):
                tool_calls = getattr(step.step_details, 'tool_calls', [])
                for tc in tool_calls:
                    tc_type = getattr(tc, 'type', 'unknown')
                    logger.info(f"    Tool call type: {tc_type}")
                    if hasattr(tc, 'fabric'):
                        logger.info(f"    Fabric query executed: {getattr(tc.fabric, 'query', 'N/A')}")
    
    usage_info = _extract_usage(run)
    
    if run.status == "failed":
        error_msg = getattr(run, 'last_error', 'Unknown error')
        logger.error(f"Agent run failed: {error_msg}")
        return ([{
            "role": "assistant",
            "content": f"Error: Agent run failed - {error_msg}"
        }], usage_info)
    
    return (_get_assistant_messages(project_client, thread_id), usage_info)


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
            time.sleep(0.5)
        
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
    
    while True:
        run = project_client.agents.runs.get(thread_id=thread_id, run_id=run_id)
        
        if run.status in terminal_states:
            return run
        
        if time.time() - start_time > timeout_seconds:
            logger.warning(f"Polling timeout after {timeout_seconds}s, status: {run.status}")
            return run
        
        time.sleep(0.5)


def _get_run_steps(
    project_client: AIProjectClient,
    thread_id: str,
    run_id: str
) -> list:
    """Get the steps executed during a run (for debugging tool calls)."""
    try:
        steps = project_client.agents.runs.steps.list(
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
