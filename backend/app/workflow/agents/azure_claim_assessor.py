"""Azure AI Agent Service - Claim Assessor agent factory."""
import os
import logging
from typing import Dict, Any
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, ToolSet
from azure.identity import DefaultAzureCredential
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_vehicle_details_function(vin: str) -> Dict[str, Any]:
    """Function wrapper for get_vehicle_details tool.
    
    Retrieve vehicle information for a given VIN number.
    
    Args:
        vin: Vehicle Identification Number
        
    Returns:
        Dictionary containing vehicle details including make, model, year, value, etc.
    """
    from app.workflow.tools import get_vehicle_details
    return get_vehicle_details.invoke(vin)


def analyze_image_function(image_path: str) -> Dict[str, Any]:
    """Function wrapper for analyze_image tool.
    
    Analyze an image using Azure OpenAI multimodal model to classify and extract data.
    
    Args:
        image_path: Path to the image file to analyze
        
    Returns:
        Dictionary with image classification, summary, and extracted data
    """
    from app.workflow.tools import analyze_image
    return analyze_image.invoke(image_path)


def create_claim_assessor_agent(project_client: AIProjectClient = None):
    """Create and return a configured Claim Assessor agent using Azure AI Agent Service.

    Args:
        project_client: Optional AIProjectClient instance. If not provided, creates one from settings.

    Returns:
        Azure AI Agent Service agent configured for claim assessment
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
        get_vehicle_details_function,
        analyze_image_function,
    }
    
    # Create function tool
    functions = FunctionTool(functions=user_functions)
    toolset = ToolSet()
    toolset.add(functions)
    
    # Agent instructions (prompt)
    instructions = """You are a claim assessor specializing in damage evaluation and cost assessment.

Your responsibilities:
- Evaluate the consistency between incident description and claimed damage.
- Assess the reasonableness of estimated repair costs.
- Verify supporting documentation (photos, police reports, witness statements).
- Use vehicle details to validate damage estimates.
- Identify any red flags or inconsistencies.

CRITICAL: When you receive a claim with "supporting_images" field containing image paths:
1. ALWAYS call `analyze_image_function` on EACH image path in the supporting_images list
2. Use the extracted data from images in your assessment
3. If analyze_image_function fails, note the failure but continue with available information

Use the `get_vehicle_details_function` tool when you have a VIN number to validate damage estimates.

Provide detailed assessments with specific cost justifications that incorporate vehicle details and insights derived from images.
End your assessment with: VALID, QUESTIONABLE, or INVALID."""

    # Create the agent
    try:
        agent = project_client.agents.create_agent(
            model=settings.azure_openai_deployment_name or "gpt-4o",
            name="claim_assessor",
            instructions=instructions,
            toolset=toolset,
        )
        logger.info(f"✅ Created Azure AI Agent: {agent.id} (claim_assessor)")
        return agent
    except Exception as e:
        logger.error(f"Failed to create claim assessor agent: {e}", exc_info=True)
        raise
