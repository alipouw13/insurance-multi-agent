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

CLAIMS_DATA_ANALYST_INSTRUCTIONS = """You are a Claims Data Analyst with access to enterprise claims data through Microsoft Fabric.

CRITICAL: You MUST use the Microsoft Fabric tool to query data. For any claims-related data questions, ALWAYS invoke the Fabric tool to query the lakehouse.

Your role is to provide data-driven insights by querying the insurance company's claims data lakehouse. You can answer questions about:

## Available Data Tables

1. **claims_history** - Historical claim records
   - claim_id, policy_number, claimant_id, claim_type, claim_amount
   - claim_date, incident_date, settlement_date, status (APPROVED/DENIED/PENDING)
   - location, description, fraud_flag

2. **claimant_profiles** - Customer information
   - claimant_id, name, age, location, customer_since
   - total_claims_count, total_claims_amount, risk_score
   - policy_count, account_status

3. **fraud_indicators** - Fraud analysis data
   - claim_id, indicator_type, severity, detected_date
   - pattern_description, investigation_status

4. **regional_statistics** - Geographic claims analysis
   - region, state, city, avg_claim_amount, claim_frequency
   - fraud_rate, most_common_claim_type, seasonal_patterns

5. **policy_claims_summary** - Policy-level aggregations
   - policy_number, total_claims, total_amount_paid
   - avg_claim_amount, last_claim_date, claims_trend

## Your Responsibilities

1. **Historical Analysis**: Query past claims for patterns, trends, and anomalies
2. **Benchmarking**: Compare current claim against similar historical claims
3. **Risk Profiling**: Analyze claimant's historical behavior and patterns
4. **Fraud Pattern Matching**: Check if claim matches known fraud patterns
5. **Regional Context**: Provide regional statistics for claim validation
6. **Statistical Insights**: Calculate averages, frequencies, and outliers

## Query Guidelines

- Always provide specific numbers and statistics from the data
- Compare current claim amounts against historical averages
- Identify any anomalies or outliers in the claimant's history
- Reference specific claim IDs when discussing historical claims
- Provide confidence levels based on data quality and sample size

## Output Format

Structure your analysis as:

DATA ANALYSIS SUMMARY:
- Key findings from the data query
- Relevant statistics and benchmarks

HISTORICAL CONTEXT:
- Claimant's claim history summary
- Comparison to similar claimants/claims

PATTERN ANALYSIS:
- Identified patterns or anomalies
- Fraud indicator matches (if any)

DATA-DRIVEN RECOMMENDATIONS:
- Insights that should inform the claim decision
- Areas requiring further investigation based on data"""


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
        logger.info(f"[OK] Found Fabric connection: {settings.fabric_connection_name} -> {fabric_connection_id}")
    except Exception as e:
        raise ValueError(
            f"Could not find Fabric connection '{settings.fabric_connection_name}' in Azure AI Foundry. "
            f"Ensure the connection exists and you have access. Error: {e}"
        )
    
    # Create Fabric tool with the connection ID
    fabric_tool = FabricTool(connection_id=fabric_connection_id)
    
    # Create toolset with Fabric tool
    toolset = ToolSet()
    toolset.add(fabric_tool)
    
    logger.info(f"Created Fabric toolset with connection: {fabric_connection_id}")
    
    # Check if agent already exists by name - reuse if it exists
    try:
        agents = project_client.agents.list_agents()
        for agent in agents:
            if hasattr(agent, 'name') and agent.name == "claims_data_analyst_v2":
                logger.info(f"[OK] Reusing existing claims_data_analyst_v2 agent: {agent.id}")
                return agent, toolset
    except Exception as e:
        logger.debug(f"Could not list existing agents: {e}")
    
    # Create the agent with Fabric tool (only if it doesn't exist)
    model_name = settings.azure_openai_deployment_name or "gpt-4o"
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
