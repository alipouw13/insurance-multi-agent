"""Supervisor orchestration for the insurance claim workflow (v2 - Azure AI Agent Service).

This module creates a supervisor agent using Azure AI Agent Service that orchestrates
specialized agents for insurance claim processing. It mirrors the functionality of
the original LangGraph supervisor but uses the new Azure AI Agent Service SDK.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Set, Callable

from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import FunctionTool, ToolSet
from azure.identity import DefaultAzureCredential

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.workflow.azure_agent_client_v2 import get_project_client_v2
from app.workflow.azure_agent_manager_v2 import (
    get_azure_agent_id_v2,
    get_azure_agent_toolset_v2,
    get_azure_agent_functions_v2,
    deploy_azure_agents_v2,
)

# ---------------------------------------------------------------------------
# Configure logging
# ---------------------------------------------------------------------------

configure_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global supervisor agent ID cache
# ---------------------------------------------------------------------------

_SUPERVISOR_AGENT_ID: Optional[str] = None
_SUPERVISOR_TOOLSET: Optional[ToolSet] = None
_AUTO_FUNCTION_CALLS_ENABLED: bool = False


# ---------------------------------------------------------------------------
# Tool functions that the supervisor can call to delegate to specialists
# ---------------------------------------------------------------------------


def call_claim_assessor(claim_data: str) -> str:
    """Delegate claim assessment to the Claim Assessor specialist.
    
    The Claim Assessor evaluates damage validity, cost assessment, and 
    verifies supporting documentation like photos and police reports.
    
    Args:
        claim_data: JSON string containing the claim details to assess
        
    Returns:
        The Claim Assessor's assessment including validity determination
    """
    from app.workflow.azure_agent_client_v2 import run_agent_v2
    
    agent_id = get_azure_agent_id_v2("claim_assessor")
    functions = get_azure_agent_functions_v2("claim_assessor")
    
    if not agent_id:
        return "Error: Claim Assessor agent not available"
    
    prompt = f"""Please assess this insurance claim:

{claim_data}

Provide a detailed assessment including:
1. Damage evaluation and consistency with incident description
2. Cost assessment reasonableness
3. Documentation verification
4. Any red flags or inconsistencies
5. Final verdict: VALID, QUESTIONABLE, or INVALID"""

    try:
        messages, usage, _, _ = run_agent_v2(agent_id, prompt, functions=functions)
        if messages:
            logger.info(f"Claim Assessor completed (tokens: {usage.get('total_tokens', 'N/A')})")
            return messages[0].get('content', 'No response from Claim Assessor')
        return "No response from Claim Assessor"
    except Exception as e:
        logger.error(f"Error calling Claim Assessor: {e}")
        return f"Error from Claim Assessor: {str(e)}"


def call_policy_checker(policy_and_claim_info: str) -> str:
    """Delegate policy verification to the Policy Checker specialist.
    
    The Policy Checker verifies claim eligibility against policy terms,
    identifies coverage limits and deductibles, and checks for exclusions.
    
    Args:
        policy_and_claim_info: JSON string with policy number and claim details
        
    Returns:
        The Policy Checker's verification including coverage determination
    """
    import json
    from app.workflow.azure_agent_client_v2 import run_agent_v2
    
    agent_id = get_azure_agent_id_v2("policy_checker")
    functions = get_azure_agent_functions_v2("policy_checker")
    
    if not agent_id:
        return "Error: Policy Checker agent not available"
    
    # Parse claim info to extract key fields for better policy matching
    try:
        claim_data = json.loads(policy_and_claim_info) if isinstance(policy_and_claim_info, str) else policy_and_claim_info
    except json.JSONDecodeError:
        claim_data = {"raw_info": policy_and_claim_info}
    
    claim_type = claim_data.get('claim_type', 'unknown')
    estimated_damage = claim_data.get('estimated_damage', 0)
    
    prompt = f"""Please verify coverage for this insurance claim:

Claim Details:
{policy_and_claim_info}

IMPORTANT: Use the search_policy_documents tool to find relevant policy coverage based on the CLAIM TYPE: "{claim_type}"
Search for policies that cover this type of claim (e.g., "collision coverage", "comprehensive coverage", "property damage", "fire damage", etc.)

Provide verification including:
1. Policy coverage type that applies to this claim type: {claim_type}
2. Relevant coverage limits and deductibles for claims of this type
3. Any applicable exclusions that might affect this claim
4. Whether the estimated damage (${estimated_damage:,.2f}) is within typical coverage limits
5. Final verdict: COVERED, PARTIALLY COVERED, or NOT COVERED"""

    try:
        messages, usage, _, _ = run_agent_v2(agent_id, prompt, functions=functions)
        if messages:
            logger.info(f"Policy Checker completed (tokens: {usage.get('total_tokens', 'N/A')})")
            return messages[0].get('content', 'No response from Policy Checker')
        return "No response from Policy Checker"
    except Exception as e:
        logger.error(f"Error calling Policy Checker: {e}")
        return f"Error from Policy Checker: {str(e)}"


def call_risk_analyst(claimant_and_claim_info: str) -> str:
    """Delegate risk analysis to the Risk Analyst specialist.
    
    The Risk Analyst analyzes fraud risk, claimant history patterns,
    and identifies red flags in claim details.
    
    Args:
        claimant_and_claim_info: JSON string with claimant ID and claim details
        
    Returns:
        The Risk Analyst's assessment including risk level determination
    """
    from app.workflow.azure_agent_client_v2 import run_agent_v2
    
    agent_id = get_azure_agent_id_v2("risk_analyst")
    functions = get_azure_agent_functions_v2("risk_analyst")
    
    if not agent_id:
        return "Error: Risk Analyst agent not available"
    
    prompt = f"""Please analyze the risk for this claim:

{claimant_and_claim_info}

Provide risk analysis including:
1. Claimant history patterns
2. Claim frequency and amounts evaluation
3. Red flags identification
4. Fraud indicators assessment
5. Final verdict: LOW RISK, MODERATE RISK, or HIGH RISK"""

    try:
        messages, usage, _, _ = run_agent_v2(agent_id, prompt, functions=functions)
        if messages:
            logger.info(f"Risk Analyst completed (tokens: {usage.get('total_tokens', 'N/A')})")
            return messages[0].get('content', 'No response from Risk Analyst')
        return "No response from Risk Analyst"
    except Exception as e:
        logger.error(f"Error calling Risk Analyst: {e}")
        return f"Error from Risk Analyst: {str(e)}"


def call_communication_agent(communication_request: str) -> str:
    """Delegate communication drafting to the Communication Agent specialist.
    
    The Communication Agent drafts professional emails to claimants
    requesting additional documentation or explaining decisions.
    
    Args:
        communication_request: JSON string with claimant info and message requirements
        
    Returns:
        The drafted communication/email
    """
    from app.workflow.azure_agent_client_v2 import run_agent_v2
    
    agent_id = get_azure_agent_id_v2("communication_agent")
    # Communication agent has no tools - it just drafts emails
    
    if not agent_id:
        return "Error: Communication Agent not available"
    
    prompt = f"""Please draft a professional email based on this request:

{communication_request}

The email should:
1. Have appropriate greeting and claim reference
2. Clearly explain the situation/request
3. Provide specific next steps
4. Include contact information
5. Have professional closing"""

    try:
        # No functions needed for communication agent
        messages, usage, _, _ = run_agent_v2(agent_id, prompt)
        if messages:
            logger.info(f"Communication Agent completed (tokens: {usage.get('total_tokens', 'N/A')})")
            return messages[0].get('content', 'No response from Communication Agent')
        return "No response from Communication Agent"
    except Exception as e:
        logger.error(f"Error calling Communication Agent: {e}")
        return f"Error from Communication Agent: {str(e)}"


def call_claims_data_analyst(claim_query: str) -> str:
    """Delegate enterprise data analysis to the Claims Data Analyst specialist.
    
    The Claims Data Analyst uses Microsoft Fabric to query historical claims data,
    claimant profiles, fraud patterns, and regional statistics from the enterprise
    data lakehouse.
    
    Args:
        claim_query: JSON string with claim details and specific data questions to answer
        
    Returns:
        The Claims Data Analyst's findings including historical patterns and statistics
    """
    import json
    from app.workflow.azure_agent_client_v2 import run_agent_v2
    
    agent_id = get_azure_agent_id_v2("claims_data_analyst")
    # Claims Data Analyst uses Fabric tool - no Python functions needed
    
    if not agent_id:
        return "Error: Claims Data Analyst not available (Fabric integration not enabled)"
    
    # Parse the claim query to extract key fields for a simple, focused query
    try:
        claim_data = json.loads(claim_query) if isinstance(claim_query, str) else claim_query
    except json.JSONDecodeError:
        claim_data = {"raw_query": claim_query}
    
    # Extract key identifiers
    claimant_id = claim_data.get('claimant_id', 'unknown')
    claim_type = claim_data.get('claim_type', 'unknown')
    state = claim_data.get('state', 'unknown')
    claimant_name = claim_data.get('claimant_name', 'unknown')
    
    # Generate claim-specific simple query (Fabric works best with natural language)
    fabric_query = _generate_fabric_query_for_supervisor(claim_data)
    
    logger.info(f"[CLAIMS_DATA_ANALYST] Fabric Query: {fabric_query}")

    try:
        # Force the Fabric Data Agent tool to be invoked
        messages, usage, _, _ = run_agent_v2(agent_id, fabric_query, tool_choice="fabric_dataagent")
        if messages:
            logger.info(f"Claims Data Analyst completed (tokens: {usage.get('total_tokens', 'N/A')})")
            response_content = messages[0].get('content', 'No response from Claims Data Analyst')
            # Prepend the query to the response for UI display
            return f"**📊 Fabric Query:** `{fabric_query}`\n\n---\n\n{response_content}"
        return "No response from Claims Data Analyst"
    except Exception as e:
        logger.error(f"Error calling Claims Data Analyst: {e}")
        return f"Error from Claims Data Analyst: {str(e)}"


def _generate_fabric_query_for_supervisor(claim_data: dict) -> str:
    """Generate a claim-specific Fabric query for the supervisor workflow.
    
    Creates simple, natural language queries optimized for Fabric Data Agent.
    """
    claimant_id = claim_data.get('claimant_id', 'unknown')
    claim_type = claim_data.get('claim_type', 'unknown')
    state = claim_data.get('state', 'unknown')
    # Don't include claimant_name in query - can confuse Fabric when it's "unknown"
    
    claim_type_lower = claim_type.lower()
    
    if 'collision' in claim_type_lower or 'major collision' in claim_type_lower:
        return f"Show claims history for claimant {claimant_id} and fraud rate for collision claims over 20000 in {state}"
    elif 'property' in claim_type_lower or 'property damage' in claim_type_lower:
        return f"Show claims history for claimant {claimant_id} and average property damage claims in {state}"
    elif 'auto accident' in claim_type_lower or 'accident' in claim_type_lower:
        return f"Show claims history for claimant {claimant_id} and fraud rate for auto accident claims in {state}"
    elif 'fire' in claim_type_lower or 'fire damage' in claim_type_lower:
        return f"Show claims history for claimant {claimant_id} and fire damage fraud indicators in {state}"
    elif 'theft' in claim_type_lower or 'auto theft' in claim_type_lower:
        return f"Show claims history for claimant {claimant_id} and auto theft fraud rate in {state}"
    elif 'liability' in claim_type_lower:
        return f"Show claims history for claimant {claimant_id} and liability claim patterns in {state}"
    else:
        return f"Show claims history for claimant {claimant_id} and fraud rate for {claim_type} claims in {state}"


# ---------------------------------------------------------------------------
# Supervisor Agent Creation
# ---------------------------------------------------------------------------

# Instructions for supervisor WITHOUT Fabric Data Agent
SUPERVISOR_INSTRUCTIONS_STANDARD = """You are a senior claims manager supervising a team of insurance claim processing specialists. Your role is to coordinate your team's analysis and provide comprehensive advisory recommendations to support human decision-makers.

Your team consists of specialized agents that you can call using your tools:
1. call_claim_assessor - Evaluates damage validity and cost assessment
2. call_policy_checker - Verifies coverage and policy terms
3. call_risk_analyst - Analyzes fraud risk and claimant history
4. call_communication_agent - Drafts customer emails for missing information

Your responsibilities:
- Coordinate the claim-processing workflow in the optimal order
- Ensure each specialist completes their assessment before moving on
- Delegate to the Communication Agent whenever information is missing
- Synthesize all team inputs into a structured advisory assessment
- Provide clear reasoning and recommendations to empower human decision-making

WORKFLOW PROCESS:
1. FIRST: Call the Claim Assessor (call_claim_assessor) with the full claim data to evaluate damage and documentation
2. THEN: Call the Policy Checker (call_policy_checker) with policy number and claim details to verify coverage
3. THEN: Call the Risk Analyst (call_risk_analyst) with claimant ID and claim details to evaluate fraud potential
4. IF any specialist reports missing information: Call the Communication Agent (call_communication_agent) to draft a customer email
5. FINALLY: Compile a comprehensive assessment summary for human review

IMPORTANT: You MUST call all three primary specialists (Claim Assessor, Policy Checker, Risk Analyst) before providing your final assessment. Pass the claim data as a JSON string to each tool.

End with a structured assessment in this format:

ASSESSMENT_COMPLETE

PRIMARY RECOMMENDATION: [APPROVE/DENY/INVESTIGATE] (Confidence: HIGH/MEDIUM/LOW)
- Brief rationale for the recommendation

SUPPORTING FACTORS:
- Key evidence that supports the recommendation
- Positive indicators identified by the team
- Policy compliance confirmations

RISK FACTORS:
- Concerns or red flags identified
- Potential fraud indicators
- Policy coverage limitations or exclusions

INFORMATION GAPS:
- Missing documentation or data
- Areas requiring clarification
- Additional verification needed

RECOMMENDED NEXT STEPS:
- Specific actions for the human reviewer
- Priority areas for further investigation
- Suggested timeline for decision

This assessment empowers human decision-makers with comprehensive AI analysis while preserving human authority over final claim decisions."""

# Instructions for supervisor WITH Fabric Data Agent (enhanced with enterprise data)
SUPERVISOR_INSTRUCTIONS_WITH_FABRIC = """You are a senior claims manager supervising a team of insurance claim processing specialists. Your role is to coordinate your team's analysis and provide comprehensive advisory recommendations to support human decision-makers.

Your team consists of specialized agents that you can call using your tools:
1. call_claim_assessor - Evaluates damage validity and cost assessment
2. call_policy_checker - Verifies coverage and policy terms  
3. call_risk_analyst - Analyzes fraud risk and claimant history
4. call_claims_data_analyst - Queries enterprise data from Fabric (historical claims, statistics, fraud patterns)
5. call_communication_agent - Drafts customer emails for missing information

CRITICAL DATA FORMAT INSTRUCTIONS:
When calling each agent, you MUST pass the COMPLETE claim data as a JSON string. Extract ALL fields from the original claim and pass them to each agent.

Required fields for each agent call:
- call_claim_assessor: Full claim JSON including claim_id, claim_type, description, estimated_damage, location, police_report, photos_provided
- call_policy_checker: Full claim JSON including policy_number, claim_type, estimated_damage, incident_date, state (The policy checker will match by claim_type to find relevant coverage)
- call_claims_data_analyst: Full claim JSON including claimant_id, claimant_name, claim_type, state, estimated_damage
- call_risk_analyst: Full claim JSON including claimant_id, claimant_name, claim_type, estimated_damage, state

WORKFLOW PROCESS:
1. FIRST: Call the Claim Assessor (call_claim_assessor) with the full claim data to evaluate damage and documentation
2. THEN: Call the Policy Checker (call_policy_checker) with the full claim data to verify coverage by claim_type
3. THEN: Call the Claims Data Analyst (call_claims_data_analyst) with the full claim data to query historical data
4. THEN: Call the Risk Analyst (call_risk_analyst) with the full claim data to evaluate fraud potential
5. IF any specialist reports missing information: Call the Communication Agent (call_communication_agent) to draft a customer email
6. FINALLY: Compile a comprehensive assessment summary for human review

IMPORTANT: Always pass the COMPLETE original claim JSON to each tool. Do not extract just one or two fields - pass the entire claim object as a JSON string.

Example format for tool calls:
call_claims_data_analyst('{"claim_id": "CLM-2026-000001", "claimant_id": "CLM-1310", "claimant_name": "Linda Ramirez", "claim_type": "Major Collision", "state": "CA", "estimated_damage": 28392.64, ...}')

End with a structured assessment in this format:

ASSESSMENT_COMPLETE

PRIMARY RECOMMENDATION: [APPROVE/DENY/INVESTIGATE] (Confidence: HIGH/MEDIUM/LOW)
- Brief rationale for the recommendation

SUPPORTING FACTORS:
- Key evidence that supports the recommendation
- Positive indicators identified by the team
- Policy compliance confirmations
- Data-driven insights from enterprise analytics

RISK FACTORS:
- Concerns or red flags identified
- Potential fraud indicators
- Policy coverage limitations or exclusions
- Anomalies detected in historical data

ENTERPRISE DATA INSIGHTS:
- Historical claim patterns for this claimant
- Comparison to similar claims (benchmarking)
- Regional statistics and trends
- Fraud pattern matches

INFORMATION GAPS:
- Missing documentation or data
- Areas requiring clarification
- Additional verification needed

RECOMMENDED NEXT STEPS:
- Specific actions for the human reviewer
- Priority areas for further investigation
- Suggested timeline for decision

This assessment empowers human decision-makers with comprehensive AI analysis while preserving human authority over final claim decisions."""


def create_supervisor_agent_v2(project_client: AIProjectClient = None):
    """Create and return a configured Supervisor agent using Azure AI Agent Service.

    The Supervisor coordinates the claim processing workflow by delegating to
    specialized agents and synthesizing their outputs into a final assessment.
    
    Conditionally includes the Claims Data Analyst (Fabric) if USE_FABRIC_DATA_AGENT=true.

    Args:
        project_client: Optional AIProjectClient instance. If not provided, creates one from settings.

    Returns:
        Tuple of (agent, toolset) - Azure AI Agent Service agent and its toolset
    """
    global _SUPERVISOR_AGENT_ID, _SUPERVISOR_TOOLSET
    
    settings = get_settings()
    
    # Create project client if not provided
    if project_client is None:
        project_client = get_project_client_v2()
    
    # Define the supervisor's tools - functions to call other agents
    # Base set of functions (always included)
    supervisor_functions = {
        call_claim_assessor,
        call_policy_checker,
        call_risk_analyst,
        call_communication_agent,
    }
    
    # Conditionally add Claims Data Analyst if Fabric is enabled
    use_fabric = settings.use_fabric_data_agent and settings.fabric_connection_name
    if use_fabric:
        supervisor_functions.add(call_claims_data_analyst)
        instructions = SUPERVISOR_INSTRUCTIONS_WITH_FABRIC
        logger.info("📊 Fabric Data Agent enabled - Claims Data Analyst added to supervisor tools")
    else:
        instructions = SUPERVISOR_INSTRUCTIONS_STANDARD
        logger.info("Standard workflow (without Fabric Data Agent)")
    
    logger.info(f"Registering {len(supervisor_functions)} tool functions for supervisor:")
    for func in supervisor_functions:
        logger.info(f"  - {func.__name__}")
    
    # Create function tool and toolset
    functions = FunctionTool(functions=supervisor_functions)
    toolset = ToolSet()
    toolset.add(functions)
    
    # Enable automatic function calling
    project_client.agents.enable_auto_function_calls(toolset)
    logger.info("Enabled auto function calls for toolset")

    # Check if supervisor agent already exists
    expected_tool_count = len(supervisor_functions)
    try:
        agents = project_client.agents.list_agents()
        for agent in agents:
            if hasattr(agent, 'name') and agent.name == "insurance_supervisor_v2":
                # Check if agent has the right number of tools (function tools)
                agent_tools = agent.tools or []
                has_function_tool = any(
                    (t.get('type') if isinstance(t, dict) else getattr(t, 'type', None)) == 'function'
                    for t in agent_tools
                )
                if has_function_tool:
                    logger.info(f"[OK] Using existing Supervisor Agent: {agent.id}")
                    _SUPERVISOR_AGENT_ID = agent.id
                    _SUPERVISOR_TOOLSET = toolset
                    return agent, toolset
                else:
                    # Agent exists but without proper tools - delete and recreate
                    logger.info(f"[WARN] Existing supervisor {agent.id} missing tools, recreating...")
                    try:
                        project_client.agents.delete_agent(agent.id)
                    except Exception as del_err:
                        logger.warning(f"Could not delete existing agent: {del_err}")
                    break
    except Exception as e:
        logger.debug(f"Could not list existing agents: {e}")
    
    # Create the supervisor agent with fresh toolset
    try:
        agent = project_client.agents.create_agent(
            model=settings.azure_openai_deployment_name or "gpt-4o",
            name="insurance_supervisor_v2",
            instructions=instructions,
            toolset=toolset,
        )
        logger.info(f"[OK] Created Supervisor Agent (v2): {agent.id}")
        _SUPERVISOR_AGENT_ID = agent.id
        _SUPERVISOR_TOOLSET = toolset
        return agent, toolset
    except Exception as e:
        logger.error(f"Failed to create supervisor agent v2: {e}", exc_info=True)
        raise


def get_supervisor_agent_id() -> Optional[str]:
    """Get the cached supervisor agent ID."""
    return _SUPERVISOR_AGENT_ID


def get_supervisor_toolset() -> Optional[ToolSet]:
    """Get the cached supervisor toolset."""
    return _SUPERVISOR_TOOLSET


# ---------------------------------------------------------------------------
# Initialize supervisor and specialized agents
# ---------------------------------------------------------------------------


def initialize_v2_agents():
    """Initialize all v2 agents including the supervisor.
    
    This should be called at application startup to deploy all agents.
    """
    logger.info("Initializing Azure AI Agent Service v2 agents...")
    
    # First deploy specialized agents
    deployed = deploy_azure_agents_v2()
    if not deployed:
        logger.warning("No specialized agents deployed - supervisor will not function correctly")
        return None
    
    # Then create supervisor agent
    try:
        supervisor, toolset = create_supervisor_agent_v2()
        logger.info("Supervisor agent initialized successfully")
        logger.info("Workflow: Supervisor -> Specialists -> Coordinated Decision")
        logger.info("=" * 80)
        logger.info("MULTI-AGENT INSURANCE CLAIM PROCESSING SYSTEM (v2)")
        logger.info("=" * 80)
        return supervisor
    except Exception as e:
        logger.error(f"Failed to initialize supervisor: {e}")
        return None


# ---------------------------------------------------------------------------
# Public helper - process claim through supervisor
# ---------------------------------------------------------------------------


def process_claim_with_supervisor_v2(claim_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run the claim through the v2 supervisor and return detailed trace information.

    This function mirrors the original process_claim_with_supervisor but uses
    Azure AI Agent Service for orchestration.

    Args:
        claim_data: Dictionary containing the claim information

    Returns:
        List of trace chunks showing the workflow progression
    """
    from app.workflow.azure_agent_client_v2 import run_agent_v2, get_project_client_v2
    
    logger.info("")
    logger.info("Starting supervisor-based claim processing (v2)...")
    logger.info(f"Processing Claim ID: {claim_data.get('claim_id', 'Unknown')}")
    logger.info("=" * 60)

    # Initialize agents if not already done (reuses existing agents)
    supervisor_id = get_supervisor_agent_id()
    if not supervisor_id:
        logger.info("Initializing supervisor and specialized agents...")
        initialize_v2_agents()
        supervisor_id = get_supervisor_agent_id()
    
    if not supervisor_id:
        logger.error("Failed to initialize supervisor agent")
        return [{
            "error": "Supervisor agent not available",
            "message": "Could not initialize the supervisor agent"
        }]

    # IMPORTANT: Recreate the toolset fresh with functions for this run
    # The enable_auto_function_calls needs the actual Python callables
    settings = get_settings()
    use_fabric = settings.use_fabric_data_agent and settings.fabric_connection_name
    
    supervisor_functions_set = {
        call_claim_assessor,
        call_policy_checker,
        call_risk_analyst,
        call_communication_agent,
    }
    
    # Create a dict mapping function names to callables for manual tool execution
    supervisor_functions_dict: Dict[str, Callable] = {
        "call_claim_assessor": call_claim_assessor,
        "call_policy_checker": call_policy_checker,
        "call_risk_analyst": call_risk_analyst,
        "call_communication_agent": call_communication_agent,
    }
    
    # Conditionally add Claims Data Analyst if Fabric is enabled
    if use_fabric:
        supervisor_functions_set.add(call_claims_data_analyst)
        supervisor_functions_dict["call_claims_data_analyst"] = call_claims_data_analyst
        logger.info("📊 Claims Data Analyst (Fabric) included in workflow")
    
    logger.info(f"Prepared {len(supervisor_functions_dict)} functions for manual tool execution")

    # Create the user message with claim data - dynamically adjust based on Fabric availability
    if use_fabric:
        user_message = f"""Please process this insurance claim through your team of specialists:

{json.dumps(claim_data, indent=2)}

Follow this workflow - you MUST call ALL FIVE specialist agents in order:
1. First call the Claim Assessor to evaluate the damage and documentation
2. Then call the Policy Checker to verify coverage
3. Then call the Claims Data Analyst to query historical data and statistics from Fabric
4. Then call the Risk Analyst to assess fraud risk
5. Finally, call the Communication Agent to draft a summary email to the claimant with the status and any next steps
6. After all five agents respond, provide your comprehensive assessment summary

IMPORTANT: You must call all five agents (claim_assessor, policy_checker, claims_data_analyst, risk_analyst, communication_agent) in sequence."""
    else:
        user_message = f"""Please process this insurance claim through your team of specialists:

{json.dumps(claim_data, indent=2)}

Follow this workflow - you MUST call ALL FOUR specialist agents in order:
1. First call the Claim Assessor to evaluate the damage and documentation
2. Then call the Policy Checker to verify coverage
3. Then call the Risk Analyst to assess fraud risk
4. Finally, call the Communication Agent to draft a summary email to the claimant with the status and any next steps
5. After all four agents respond, provide your comprehensive assessment summary

IMPORTANT: You must call all four agents (claim_assessor, policy_checker, risk_analyst, communication_agent) in sequence."""

    chunks: List[Dict[str, Any]] = []
    
    try:
        # Run the supervisor agent with manual tool execution
        # Pass the functions dict so run_agent_v2 can execute them when needed
        messages, usage, tool_results, _ = run_agent_v2(
            supervisor_id, 
            user_message, 
            functions=supervisor_functions_dict
        )
        
        # Build trace-like output similar to LangGraph format
        # First, add the supervisor's initial delegation
        chunks.append({
            "supervisor": {
                "messages": [{
                    "role": "assistant",
                    "content": "Processing claim through specialist agents..."
                }],
                "source": "azure_agents_v2"
            }
        })
        
        # Map function names to agent names for trace output
        function_to_agent = {
            "call_claim_assessor": "claim_assessor",
            "call_policy_checker": "policy_checker",
            "call_claims_data_analyst": "claims_data_analyst",
            "call_risk_analyst": "risk_analyst",
            "call_communication_agent": "communication_agent"
        }
        
        # Add chunks for each tool call result (these are the specialist agent responses)
        for tool_result in tool_results:
            function_name = tool_result.get("function_name", "unknown")
            agent_name = function_to_agent.get(function_name, function_name.replace("call_", ""))
            output = tool_result.get("output", "")
            
            # Create a chunk that matches LangGraph format
            chunks.append({
                agent_name: {
                    "messages": [{
                        "role": "assistant",
                        "content": output
                    }],
                    "source": "azure_agents_v2"
                }
            })
            logger.info(f"Added trace chunk for {agent_name}")
        
        # Add final supervisor response with the comprehensive assessment
        if messages:
            supervisor_response = messages[0].get('content', '')
            
            chunks.append({
                "supervisor": {
                    "messages": [{
                        "role": "assistant",
                        "content": supervisor_response
                    }],
                    "final_assessment": True,
                    "source": "azure_agents_v2"
                }
            })
            
            logger.info(f"Workflow completed successfully")
            logger.info(f"Total agents involved: {len(tool_results)}")
            logger.info(f"Total tokens used: {usage.get('total_tokens', 'N/A')}")
        else:
            chunks.append({
                "error": "No response from supervisor",
                "message": "The supervisor agent did not return a response"
            })
        
        return chunks
        
    except Exception as e:
        logger.error(f"Error in workflow processing: {e}", exc_info=True)
        return [{
            "error": str(e),
            "message": "Error during claim processing"
        }]


# ---------------------------------------------------------------------------
# Module initialization logging
# ---------------------------------------------------------------------------

logger.info("Supervisor v2 module loaded")
logger.info("Use initialize_v2_agents() to deploy agents at startup")
