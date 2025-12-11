"""Test script for Azure AI Agent Service - Policy Checker

Run this script to test the migrated policy checker agent.

Usage:
    cd backend
    uv run python test_azure_policy_checker.py
"""
import json
import logging
from app.workflow.agents.azure_policy_checker import create_policy_checker_agent
from app.workflow.azure_agent_client import get_project_client, run_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_policy_verification():
    """Test the policy checker agent with a sample claim."""
    
    logger.info("=" * 80)
    logger.info("🚀 Testing Azure AI Agent Service - Policy Checker")
    logger.info("=" * 80)
    
    # Sample claim data for policy verification
    sample_claim = {
        "claim_id": "CLM-2024-001",
        "policy_number": "POL-2024-001",
        "claimant_id": "CLM-001",
        "incident_description": "Vehicle collision at intersection. Front-end damage to my silver Honda Civic.",
        "incident_date": "2024-12-10",
        "incident_type": "collision",
        "estimated_damage_cost": 4500,
        "vin": "1HGBH41JXMN109186"
    }
    
    # Create the user message
    user_message = f"""Please verify policy coverage for this insurance claim:

{json.dumps(sample_claim, indent=2)}

Check if this type of damage is covered under the policy, what the coverage limits are, and what deductible applies."""
    
    try:
        # Step 1: Get project client
        logger.info("\n📌 Step 1: Initializing Azure AI Project Client...")
        project_client = get_project_client()
        logger.info("✅ Project client initialized")
        
        # Step 2: Create the agent
        logger.info("\n📌 Step 2: Creating Policy Checker agent...")
        agent = create_policy_checker_agent(project_client)
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
        logger.info("⚠️  Agent left in Foundry project for reuse.")
        logger.info(f"   Agent ID: {agent.id}")
        logger.info("   To delete manually, use: project_client.agents.delete_agent(agent.id)")
        
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


def test_dutch_policy_verification():
    """Test the policy checker agent with a Dutch policy claim."""
    
    logger.info("\n\n" + "=" * 80)
    logger.info("🚀 Testing Azure AI Agent Service - Policy Checker (Dutch Policy)")
    logger.info("=" * 80)
    
    # Sample Dutch claim data
    dutch_claim = {
        "claim_id": "CLM-2024-NL-001",
        "policy_number": "UNAuto-02-2024-567890",
        "claimant_id": "CLM-004",
        "incident_description": "Aanrijding op kruispunt. Schade aan voorkant van mijn auto.",
        "incident_date": "2024-12-10",
        "incident_type": "aanrijding",
        "estimated_damage_cost": 3200,
        "location": "Amsterdam, Nederland"
    }
    
    user_message = f"""Verifieer de dekking voor deze schade claim:

{json.dumps(dutch_claim, indent=2)}

Controleer of dit type schade gedekt is onder de polis, wat de dekkingslimieten zijn, en welk eigen risico van toepassing is."""
    
    try:
        logger.info("\n📌 Running Policy Checker with Dutch claim...")
        project_client = get_project_client()
        
        # Reuse or create agent
        agent = create_policy_checker_agent(project_client)
        logger.info(f"✅ Using agent: {agent.id}")
        
        messages = run_agent(agent.id, user_message)
        
        logger.info("\n📌 Agent Response:")
        logger.info("=" * 80)
        for msg in messages:
            if msg["role"] == "assistant":
                logger.info(f"\n🤖 Assistant:\n{msg['content']}\n")
        logger.info("=" * 80)
        
        logger.info("\n✅ Dutch policy test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Dutch policy test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    agent_id = None
    try:
        # Test with English policy first
        success1 = test_policy_verification()
        
        # Test with Dutch policy (reuses same agent)
        success2 = test_dutch_policy_verification()
        
        # Cleanup - delete the test agent
        from app.workflow.azure_agent_client import delete_agent, find_agent_by_name
        agent = find_agent_by_name("policy_checker")
        if agent:
            logger.info("\n🧹 Cleaning up test agent...")
            delete_agent(agent.id)
            logger.info(f"✅ Deleted agent: {agent.id}")
        
        exit(0 if (success1 and success2) else 1)
    except Exception as e:
        logger.error(f"Test execution error: {e}", exc_info=True)
        exit(1)
