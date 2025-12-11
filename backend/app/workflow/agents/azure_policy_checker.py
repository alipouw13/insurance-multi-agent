"""Azure AI Agent Service - Policy Checker agent factory."""
import logging
from typing import Dict, Any
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import FunctionTool, ToolSet
from azure.identity import DefaultAzureCredential
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_policy_details(policy_number: str) -> Dict[str, Any]:
    """Retrieve detailed policy information for a given policy number.
    
    Args:
        policy_number: The policy number to look up
        
    Returns:
        Dictionary containing policy details including coverage, limits, deductibles, etc.
    """
    from app.workflow.tools import get_policy_details as get_details_tool
    return get_details_tool.invoke(policy_number)


def search_policy_documents(query: str) -> Dict[str, Any]:
    """Search through policy documents using semantic search to find relevant sections.
    
    Args:
        query: The search query (e.g., "collision coverage", "eigen schade")
        
    Returns:
        Dictionary with search results including policy sections and relevance scores
    """
    from app.workflow.tools import search_policy_documents as search_tool
    return search_tool.invoke(query)


def create_policy_checker_agent(project_client: AIProjectClient = None):
    """Create and return a configured Policy Checker agent using Azure AI Agent Service.

    Args:
        project_client: Optional AIProjectClient instance. If not provided, creates one from settings.

    Returns:
        Azure AI Agent Service agent configured for policy verification
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
    
    # Define the functions that the agent can call
    user_functions = {
        get_policy_details,
        search_policy_documents,
    }
    
    # Create function tool and enable auto function calls
    functions = FunctionTool(functions=user_functions)
    toolset = ToolSet()
    toolset.add(functions)
    
    # Enable automatic function calling
    project_client.agents.enable_auto_function_calls(toolset)
    
    # Agent instructions (prompt)
    instructions = """You are a policy-verification specialist. Your task is to decide whether the reported loss is covered under the customer's policy.

MANDATORY STEPS
1. Call `get_policy_details_function` to confirm the policy is in-force and gather limits / deductibles.
2. Craft one or more focused queries for `search_policy_documents_function` to locate wording that applies (coverage, exclusions, definitions, limits).
3. If initial searches return no results, try alternative search terms (e.g., "collision", "damage", "vehicle", "exclusions", "coverage").

LANGUAGE-SPECIFIC POLICY SEARCH STRATEGY
• DUTCH CLAIMS: If the claim contains Dutch text, names, locations, or policy numbers starting with "UNAuto", prioritize Dutch policy terms:
  - Use Dutch search terms: "eigen schade", "aanrijding", "uitsluitingen", "dekking", "schadegarant", "rechtsbijstand"
  - Search for "Autoverzekering", "WA All risk", "Polisvoorwaarden", "UNAuto"
  - Look for Dutch-specific services: "DAS", "Glasgarant", "Pechhulp Nederland"
• ENGLISH CLAIMS: Use standard English terms: "collision coverage", "exclusions", "deductible", "comprehensive"
• MIXED RESULTS: If you get both Dutch and English policy results, prioritize the language that matches the claim context

INSUFFICIENT EVIDENCE DETECTION
• LANGUAGE MISMATCH: If you detect a Dutch claim but only find English policy documents (or vice versa), this indicates the relevant policy documents may not be indexed.
• POLICY MISMATCH: If the policy number format suggests a specific policy type (e.g., "UNAuto-02" for Dutch policies) but search results don't contain matching policy documents.
• LOW RELEVANCE: If all search results have very low relevance scores and don't contain terms related to the claim type.

WHEN READING SEARCH RESULTS
• Each result dict contains `policy_type`, `section`, `content`, and `relevance_score`.
• EVALUATE RELEVANCE: Check if the search results actually relate to the claim context (language, policy type, coverage area).
• Cite every passage you rely on. Prefix the quotation or paraphrase with a citation in the form:  `[{{policy_type}} §{{section}}]`.
  Example:  `[Comprehensive Auto §2.1 – Collision Coverage] Damage from collisions with other vehicles is covered …`
  Example:  `[Autoverzekering UNAuto-02 §6.3] Verder ben je verzekerd voor schade aan je auto, als deze is veroorzaakt door een aanrijding …`

WHAT TO INCLUDE IN YOUR ANSWER
• A bullet list of each cited section followed by a short explanation of how it affects coverage.
• Applicable limits and deductibles.
• Any exclusions that negate or restrict coverage.
• If insufficient evidence: Clearly state the mismatch between claim context and available policy documents.

FORMAT
End with a single line containing exactly:  `FINAL ASSESSMENT: COVERED`, `NOT_COVERED`, `PARTIALLY_COVERED`, or `INSUFFICIENT_EVIDENCE` (choose one).

RULES
• Try multiple search queries before concluding no relevant sections exist.
• INSUFFICIENT_EVIDENCE should be used when:
  - Language mismatch between claim and available policy documents
  - Policy type mismatch (e.g., Dutch policy number but only English policies found)
  - No relevant policy sections found despite comprehensive searching
  - Search results don't contain terms or context related to the specific claim
• If you find relevant policy sections that match the claim context, proceed with normal coverage assessment.
• Do NOT hallucinate policy language; only quote or paraphrase returned passages.
• Be concise yet complete."""

    # Check if agent already exists
    from app.workflow.azure_agent_client import find_agent_by_name
    existing_agent = find_agent_by_name("policy_checker")
    
    if existing_agent:
        logger.info(f"✅ Using existing Azure AI Agent: {existing_agent.id} (policy_checker)")
        return existing_agent
    
    # Create the agent
    try:
        agent = project_client.agents.create_agent(
            model=settings.azure_openai_deployment_name or "gpt-4o",
            name="policy_checker",
            instructions=instructions,
            toolset=toolset,
        )
        logger.info(f"✅ Created Azure AI Agent: {agent.id} (policy_checker)")
        return agent
    except Exception as e:
        logger.error(f"Failed to create policy checker agent: {e}", exc_info=True)
        raise
