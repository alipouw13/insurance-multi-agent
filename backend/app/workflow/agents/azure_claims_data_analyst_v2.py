"""Azure AI Agent Service - Claims Data Analyst agent with Microsoft Fabric integration.

This agent queries enterprise claims data from a Microsoft Fabric Lakehouse through
the Fabric Data Agent tool. It provides historical claims analytics, pattern analysis,
and data-driven insights to support claim decision-making.

Requirements:
- Published Fabric Data Agent endpoint in your Fabric workspace
- Connection configured in Azure AI Foundry pointing to your Fabric resource
- FABRIC_CONNECTION_NAME environment variable set to the connection name
- Azure AI User RBAC role on the Foundry hub/project
- READ access to the Fabric data agent

IMPORTANT: Fabric Data Agent requires USER identity authentication (not Service Principal).
The agent uses AzureCliCredential or InteractiveBrowserCredential for authentication.
Run 'az login' before starting the backend to authenticate with your user account.

The Fabric Lakehouse should contain tables such as:
- claims_history: Historical claim records with amounts, status, dates
- claimant_profiles: Customer demographics and account information  
- fraud_indicators: Known fraud patterns and flagged claims
- regional_statistics: Claims statistics by region/location
- policy_claims_summary: Aggregated claims per policy
"""
import logging
from typing import Dict, Any, Optional
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ToolSet
from azure.identity import ChainedTokenCredential, AzureCliCredential, InteractiveBrowserCredential
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Try to import FabricTool - may not be available in all SDK versions
try:
    from azure.ai.agents.models import FabricTool
    FABRIC_TOOL_AVAILABLE = True
    logger.info("[OK] FabricTool is available in the SDK")
except ImportError:
    FABRIC_TOOL_AVAILABLE = False
    logger.warning(
        "[WARN] FabricTool not available in current azure-ai-agents SDK version. "
        "Fabric Data Agent integration will not be available. "
        "Check for SDK updates or use Azure AI Foundry portal to test Fabric integration."
    )


# ---------------------------------------------------------------------------
# Agent Instructions  
# ---------------------------------------------------------------------------

# Microsoft Best Practices: Describe what data the Fabric tool can access
# See: https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/fabric
# IMPORTANT: Instructions must be clear about WHEN and HOW to use the Fabric tool
CLAIMS_DATA_ANALYST_INSTRUCTIONS = """You are a Claims Data Analyst with access to enterprise claims data through the Fabric tool.

IMPORTANT: You MUST use the Fabric tool to answer ANY question about claims, claimants, fraud, or data analytics. 
Do NOT respond with "I don't have access" - you DO have access through the Fabric tool.

The Fabric tool connects to a Microsoft Fabric Lakehouse with these tables:
- claims_history: claim_id, claimant_id, claimant_name, claim_type, estimated_damage, amount_paid, status, claim_date, incident_date, location, state, fraud_flag, police_report, photos_provided, witness_statements, license_plate, vehicle_info, description
- claimant_profiles: claimant_id, name, age, location, risk_score, policy_number

For ANY data-related question:
1. Call the Fabric tool with a natural language query
2. Present the results clearly to the user
3. Include relevant statistics and insights

Never say you cannot access data - always use the Fabric tool first."""


def get_claims_data_analyst_functions() -> Dict[str, Any]:
    """Get the callable functions for the Claims Data Analyst agent.
    
    Note: The Fabric tool handles all data queries internally through natural language.
    There are no additional Python functions to expose since Fabric translates
    natural language queries to SQL against the lakehouse.
    
    Returns:
        Empty dict - Fabric tool is managed by Azure AI Agent Service
    """
    # The Fabric tool is handled entirely by the Azure AI Agent Service
    # No Python functions needed - queries go directly to Fabric
    return {}


def create_claims_data_analyst_agent_v2(project_client: AIProjectClient = None):
    """Create and return a configured Claims Data Analyst agent with Fabric tool.

    This agent uses Microsoft Fabric Data Agent to query enterprise claims data
    from a Fabric Lakehouse, enabling natural language queries against SQL tables.

    Args:
        project_client: Optional AIProjectClient instance. If not provided, creates one from settings.

    Returns:
        Tuple of (agent, toolset) - Azure AI Agent Service agent and its Fabric toolset
        
    Raises:
        ValueError: If FABRIC_CONNECTION_NAME is not configured or connection not found
        ImportError: If FabricTool is not available in the SDK
    """
    # Check if FabricTool is available
    if not FABRIC_TOOL_AVAILABLE:
        raise ImportError(
            "FabricTool is not available in the current azure-ai-agents SDK version. "
            "Please check for SDK updates or use Azure AI Foundry portal to test Fabric integration. "
            "Current SDK may require a preview version for Fabric support."
        )
    
    settings = get_settings()
    
    # Validate Fabric configuration
    if not settings.fabric_connection_name:
        raise ValueError(
            "FABRIC_CONNECTION_NAME environment variable must be set to use the Claims Data Analyst. "
            "This should be the name of your Fabric connection in Azure AI Foundry."
        )
    
    # Create project client if not provided
    # IMPORTANT: Fabric Data Agent requires USER identity (not Service Principal)
    # We use ChainedTokenCredential with AzureCliCredential first to ensure user identity
    if project_client is None:
        if not settings.project_endpoint:
            raise ValueError(
                "PROJECT_ENDPOINT environment variable must be set. "
                "Find it in your Azure AI Foundry portal under Project settings."
            )
        
        # Use user-identity credentials for Fabric Data Agent
        # AzureCliCredential uses the logged-in user from 'az login'
        # InteractiveBrowserCredential prompts for login if CLI not available
        user_credential = ChainedTokenCredential(
            AzureCliCredential(),
            InteractiveBrowserCredential()
        )
        logger.info("[FABRIC] Using user identity authentication (AzureCliCredential/InteractiveBrowserCredential)")
        logger.info("[FABRIC] Ensure you have run 'az login' with a user account that has Fabric access")
        
        project_client = AIProjectClient(
            endpoint=settings.project_endpoint,
            credential=user_credential
        )
    
    # Get the Fabric connection ID from the connection name
    try:
        connection = project_client.connections.get(settings.fabric_connection_name)
        fabric_connection_id = connection.id
        logger.info(f"[FABRIC] === CONNECTION DETAILS ===")
        logger.info(f"[FABRIC] Connection name: {settings.fabric_connection_name}")
        logger.info(f"[FABRIC] Connection ID: {fabric_connection_id}")
        
        # Log ALL connection attributes for debugging
        conn_attrs = [a for a in dir(connection) if not a.startswith('_')]
        logger.info(f"[FABRIC] Connection attributes: {conn_attrs}")
        for attr in ['type', 'target', 'properties', 'metadata', 'credentials', 'is_shared', 'category']:
            if hasattr(connection, attr):
                val = getattr(connection, attr)
                if val is not None:
                    # Don't log sensitive credential info
                    if attr == 'credentials':
                        logger.info(f"[FABRIC]   {attr}: <credentials present>")
                    else:
                        logger.info(f"[FABRIC]   {attr}: {val}")
        
        # Check if connection has target endpoint (Fabric endpoint URL)
        if hasattr(connection, 'target') and connection.target:
            logger.info(f"[FABRIC] Fabric endpoint: {connection.target}")
            
    except Exception as e:
        logger.error(f"[FABRIC] Failed to get connection: {e}", exc_info=True)
        raise ValueError(
            f"Could not find Fabric connection '{settings.fabric_connection_name}' in Azure AI Foundry. "
            f"Ensure the connection exists and you have access. Error: {e}"
        )
    
    # Create Fabric tool with the connection ID
    # The connection_id should be the full Azure resource ID
    fabric_tool = FabricTool(connection_id=fabric_connection_id)
    logger.info(f"[FABRIC] === FABRIC TOOL DETAILS ===")
    logger.info(f"[FABRIC] FabricTool connection_id: {fabric_connection_id}")
    logger.info(f"[FABRIC] FabricTool definitions: {fabric_tool.definitions}")
    
    # Log the tool definition structure
    if fabric_tool.definitions:
        for i, defn in enumerate(fabric_tool.definitions):
            logger.info(f"[FABRIC] Tool definition {i+1}:")
            defn_attrs = [a for a in dir(defn) if not a.startswith('_')]
            for attr in defn_attrs:
                try:
                    val = getattr(defn, attr)
                    if not callable(val) and val is not None:
                        logger.info(f"[FABRIC]   {attr}: {val}")
                except:
                    pass
    
    # Create toolset with Fabric tool
    toolset = ToolSet()
    toolset.add(fabric_tool)
    
    logger.info(f"[FABRIC] Created Fabric toolset successfully")
    
    # Check if agent already exists by name - REUSE it instead of recreating
    # This prevents issues where multiple processes (backend + diagnostic scripts)
    # delete each other's agents, causing "No assistant found" errors
    try:
        agents = project_client.agents.list_agents()
        for agent in agents:
            if hasattr(agent, 'name') and agent.name == "claims_data_analyst_v2":
                logger.info(f"[FABRIC] Found existing claims_data_analyst_v2 agent: {agent.id}")
                
                # Verify the agent has the Fabric tool configured
                has_fabric_tool = False
                if hasattr(agent, 'tools') and agent.tools:
                    for tool in agent.tools:
                        tool_type = getattr(tool, 'type', None)
                        if tool_type and 'fabric' in str(tool_type).lower():
                            has_fabric_tool = True
                            break
                
                if has_fabric_tool:
                    logger.info(f"[FABRIC] Reusing existing agent with Fabric tool: {agent.id}")
                    return agent, toolset
                else:
                    # Agent exists but doesn't have Fabric tool - need to recreate
                    logger.warning(f"[FABRIC] Agent exists but has no Fabric tool - recreating...")
                    project_client.agents.delete_agent(agent.id)
                    logger.info(f"[FABRIC] Deleted old agent without Fabric tool: {agent.id}")
                    break
    except Exception as e:
        logger.debug(f"Could not list/check existing agents: {e}")
    
    # Create the agent with Fabric tool (only if it doesn't exist)
    model_name = settings.azure_openai_deployment_name or "gpt-4.1-mini"
    logger.info(f"[INFO] Creating NEW claims_data_analyst_v2 with model: {model_name}")
    
    try:
        agent = project_client.agents.create_agent(
            model=model_name,
            name="claims_data_analyst_v2",
            instructions=CLAIMS_DATA_ANALYST_INSTRUCTIONS,
            tools=fabric_tool.definitions,  # Fabric tool definitions
            headers={"x-ms-enable-preview": "true"},  # Required for Fabric Data Agent preview
        )
        logger.info(f"[OK] Created Azure AI Agent (v2): {agent.id} (claims_data_analyst_v2) with model: {model_name}")
        logger.info(f"   Agent tools: {[t.type if hasattr(t, 'type') else str(t) for t in agent.tools] if hasattr(agent, 'tools') and agent.tools else 'None'}")
        return agent, toolset
    except Exception as e:
        logger.error(f"Failed to create claims data analyst agent v2: {e}", exc_info=True)
        raise


def is_fabric_tool_available() -> bool:
    """Check if the FabricTool is available in the current SDK.
    
    Returns:
        True if FabricTool can be imported, False otherwise
    """
    return FABRIC_TOOL_AVAILABLE


def get_fabric_tool_description() -> str:
    """Get a description of what the Fabric Data Agent can query.
    
    This is useful for documentation and for the supervisor to understand
    what data the Claims Data Analyst can access.
    
    Returns:
        Human-readable description of Fabric capabilities
    """
    return """
    The Claims Data Analyst uses Microsoft Fabric to query:
    
    📊 CLAIMS HISTORY
    - All historical claims with amounts, dates, and outcomes
    - Filter by policy, claimant, date range, claim type
    - Aggregate statistics (avg, sum, count, trends)
    
    👤 CLAIMANT PROFILES  
    - Customer demographics and account history
    - Risk scores and claim patterns per customer
    - Policy ownership and tenure information
    
    🚨 FRAUD INDICATORS
    - Known fraud patterns and flagged claims
    - Severity levels and investigation status
    - Pattern matching against current claims
    
    🗺️ REGIONAL STATISTICS
    - Geographic claims distribution
    - Regional fraud rates and trends
    - Seasonal patterns by location
    
    📋 POLICY SUMMARIES
    - Aggregated claims per policy
    - Payment history and trends
    - Policy-level risk indicators
    """
