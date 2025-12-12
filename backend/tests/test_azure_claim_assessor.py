"""Test script for Azure AI Agent Service - Claim Assessor

Run this script to test the migrated claim assessor agent.

Usage:
    cd backend
    uv run python tests/test_azure_claim_assessor.py
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.workflow.agents.azure_claim_assessor import create_claim_assessor_agent
from app.workflow.azure_agent_client import get_project_client, run_agent, delete_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def test_claim_assessment():
    """Test the claim assessor agent with a sample claim."""
    
    logger.info("=" * 80)
    logger.info("🚀 Testing Azure AI Agent Service - Claim Assessor")
    logger.info("=" * 80)
    
    # Sample claim data
    sample_claim = {
        "claim_id": "CLM-2024-001",
        "policy_number": "POL-2024-001",
        "claimant_id": "CLM-001",
        "incident_description": "Vehicle collision at intersection. Front-end damage to my silver Honda Civic.",
        "incident_date": "2024-12-10",
        "estimated_damage_cost": 4500,
        "vin": "1HGBH41JXMN109186",
        "supporting_images": []  # Empty for now to test without image analysis
    }
    
    # Create the user message
    user_message = f"""Please process this insurance claim:

{json.dumps(sample_claim, indent=2)}

Assess the claim and provide your evaluation."""
    
    try:
        # Step 1: Get project client
        logger.info("\n📌 Step 1: Initializing Azure AI Project Client...")
        project_client = get_project_client()
        logger.info("✅ Project client initialized")
        
        # Step 2: Create the agent
        logger.info("\n📌 Step 2: Creating Claim Assessor agent...")
        agent = create_claim_assessor_agent(project_client)
        logger.info(f"✅ Agent created: {agent.id}")
        
        # Step 3: Run the agent
        logger.info("\n📌 Step 3: Running agent with sample claim...")
        messages = run_agent(agent.id, user_message)
        
        # Step 4: Display results
        logger.info("\n📌 Step 4: Agent Response:")
        logger.info("=" * 80)
        for msg in messages:
            if msg["role"] == "assistant":
                logger.info(f"\n🤖 Assistant:\n{msg['content']}\n")
            elif msg["role"] == "user":
                logger.info(f"\n👤 User:\n{msg['content']}\n")
        logger.info("=" * 80)
        
        # Step 5: Cleanup
        logger.info("\n📌 Step 5: Cleanup...")
        from app.workflow.azure_agent_client import delete_agent
        try:
            delete_agent(agent.id)
            logger.info(f"✅ Deleted agent: {agent.id}")
        except Exception as e:
            logger.warning(f"⚠️  Could not delete agent: {e}")
        
        logger.info("\n✅ Test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        logger.error("\n💡 Troubleshooting:")
        logger.error("   1. Ensure PROJECT_ENDPOINT is set in .env")
        logger.error("   2. Run 'az login' to authenticate")
        logger.error("   3. Verify Azure AI User role on the Foundry project")
        logger.error("   4. Check that AZURE_OPENAI_DEPLOYMENT_NAME matches a deployed model")
        return False


if __name__ == "__main__":
    success = test_claim_assessment()
    exit(0 if success else 1)
