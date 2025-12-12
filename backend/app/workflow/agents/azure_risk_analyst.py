"""Azure AI Agent Service - Risk Analyst agent factory.

This module provides a risk analyst agent that specializes in fraud detection
and risk assessment for insurance claims.
"""
import logging
from typing import Dict, Any
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import FunctionTool, ToolSet
from app.core.config import get_settings
from app.workflow.azure_agent_client import get_project_client, find_agent_by_name

logger = logging.getLogger(__name__)


def get_claimant_history(claimant_id: str) -> Dict[str, Any]:
    """Retrieve historical claim information for a given claimant.
    
    Args:
        claimant_id: Unique identifier for the claimant
        
    Returns:
        Dictionary containing claimant history including past claims,
        risk factors, and fraud indicators
    """
    logger.info(f"Fetching claimant history for: {claimant_id}")
    
    # Mock database of claimant information
    claimant_database = {
        "CLM-001": {
            "claimant_id": "CLM-001",
            "name": "John Smith",
            "customer_since": "2020-01-15",
            "total_claims": 2,
            "claim_history": [
                {
                    "claim_id": "CLM-2023-456",
                    "date": "2023-08-15",
                    "type": "collision",
                    "amount_claimed": 3500,
                    "amount_paid": 3000,
                    "status": "closed",
                    "description": "Minor fender bender in parking lot",
                },
                {
                    "claim_id": "CLM-2022-123",
                    "date": "2022-03-10",
                    "type": "comprehensive",
                    "amount_claimed": 1200,
                    "amount_paid": 950,
                    "status": "closed",
                    "description": "Hail damage to vehicle",
                },
            ],
            "risk_factors": {
                "claim_frequency": "low",
                "average_claim_amount": 2350,
                "fraud_indicators": [],
                "credit_score": "good",
                "driving_record": "clean",
            },
            "contact_info": {
                "phone": "555-0101",
                "email": "john.smith@example.com",
                "address": "123 Main St, Springfield, IL 62701",
            },
        },
        "CLM-002": {
            "claimant_id": "CLM-002",
            "name": "Jane Doe",
            "customer_since": "2021-06-01",
            "total_claims": 5,
            "claim_history": [
                {
                    "claim_id": "CLM-2024-789",
                    "date": "2024-11-20",
                    "type": "collision",
                    "amount_claimed": 8500,
                    "amount_paid": 6000,
                    "status": "closed",
                    "description": "Rear-end collision on highway",
                },
                {
                    "claim_id": "CLM-2024-555",
                    "date": "2024-08-10",
                    "type": "collision",
                    "amount_claimed": 5000,
                    "amount_paid": 4500,
                    "status": "closed",
                    "description": "Side-swipe in parking garage",
                },
                {
                    "claim_id": "CLM-2023-333",
                    "date": "2023-12-05",
                    "type": "comprehensive",
                    "amount_claimed": 3200,
                    "amount_paid": 2800,
                    "status": "closed",
                    "description": "Vandalism damage",
                },
                {
                    "claim_id": "CLM-2023-111",
                    "date": "2023-05-15",
                    "type": "collision",
                    "amount_claimed": 4500,
                    "amount_paid": 4000,
                    "status": "closed",
                    "description": "Intersection collision",
                },
                {
                    "claim_id": "CLM-2022-888",
                    "date": "2022-09-20",
                    "type": "collision",
                    "amount_claimed": 6000,
                    "amount_paid": 5500,
                    "status": "closed",
                    "description": "Multi-vehicle accident",
                },
            ],
            "risk_factors": {
                "claim_frequency": "high",
                "average_claim_amount": 5440,
                "fraud_indicators": [
                    "High claim frequency in short period",
                    "Multiple collision claims within 18 months",
                ],
                "credit_score": "fair",
                "driving_record": "multiple_violations",
            },
            "contact_info": {
                "phone": "555-0202",
                "email": "jane.doe@example.com",
                "address": "456 Oak Ave, Springfield, IL 62702",
            },
        },
    }
    
    if claimant_id in claimant_database:
        return claimant_database[claimant_id]
    else:
        return {
            "error": f"Claimant {claimant_id} not found in system",
            "claimant_id": claimant_id,
            "total_claims": 0,
            "claim_history": [],
            "risk_factors": {
                "claim_frequency": "unknown",
                "fraud_indicators": ["No history available"],
            },
        }


def create_risk_analyst_agent():
    """Create or retrieve the Risk Analyst Agent using Azure AI Agent Service.
    
    This agent specializes in fraud detection and risk assessment for insurance claims,
    analyzing claimant history and identifying potential risk factors.
    
    Returns:
        Configured Azure AI Agent for risk analysis
    """
    settings = get_settings()
    project_client = get_project_client()
    
    # Check if agent already exists
    existing_agent = find_agent_by_name("risk_analyst")
    if existing_agent:
        logger.info(f"♻️  Found existing risk_analyst: {existing_agent.id}")
        return existing_agent
    
    # Define the function that the agent can call
    user_functions = {
        get_claimant_history,
    }
    
    # Create function tool and enable auto function calls
    functions = FunctionTool(functions=user_functions)
    toolset = ToolSet()
    toolset.add(functions)
    
    # Enable automatic function calling
    project_client.agents.enable_auto_function_calls(toolset)
    
    # Agent instructions (prompt)
    instructions = """You are a risk analyst specializing in fraud detection and risk assessment for insurance claims.

Your responsibilities:
- Analyze claimant history and claim frequency patterns.
- Identify potential fraud indicators.
- Assess risk factors based on incident details.
- Evaluate supporting documentation quality.
- Provide risk scoring and recommendations.

Use the `get_claimant_history` tool when you have a claimant ID to analyze risk factors.

When analyzing risk:
1. Review the claimant's total number of claims and claim frequency
2. Examine the pattern of claim amounts and types
3. Look for fraud indicators in their history
4. Consider their credit score and driving record
5. Evaluate if the current claim fits suspicious patterns

Focus on objective risk factors and provide evidence-based assessments.
End your assessment with risk level: LOW_RISK, MEDIUM_RISK, or HIGH_RISK.

Provide specific reasoning for your risk assessment based on the data."""
    
    # Create the agent
    try:
        agent = project_client.agents.create_agent(
            model=settings.azure_openai_deployment_name or "gpt-4o",
            name="risk_analyst",
            instructions=instructions,
            toolset=toolset,
        )
        logger.info(f"✅ Created Azure AI Agent: {agent.id} (risk_analyst)")
        return agent
    except Exception as e:
        logger.error(f"Failed to create risk analyst agent: {e}", exc_info=True)
        raise
