"""Test script for Azure AI Agent Service - Risk Analyst

Run this script to test the migrated risk analyst agent.

Usage:
    cd backend
    uv run python tests/test_azure_risk_analyst.py
"""
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.workflow.agents.azure_risk_analyst import create_risk_analyst_agent
from app.workflow.azure_agent_client import run_agent, delete_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def test_risk_analyst():
    """Test the Risk Analyst Agent's ability to assess fraud risk."""
    try:
        logger.info("\n" + "=" * 80)
        logger.info("🧪 Testing Azure AI Risk Analyst Agent")
        logger.info("=" * 80)
        
        # Step 1: Create agent
        logger.info("\n📌 Step 1: Creating Risk Analyst Agent...")
        agent = create_risk_analyst_agent()
        logger.info(f"✅ Agent created: {agent.id}")
        
        # Test Case 1: Low-risk claimant
        logger.info("\n" + "=" * 80)
        logger.info("📋 Test Case 1: Low-Risk Claimant (CLM-001)")
        logger.info("=" * 80)
        
        test_claim_low_risk = {
            "claim_id": "CLM-2024-999",
            "claimant_id": "CLM-001",
            "policy_number": "POL-2024-001",
            "incident_description": "Minor parking lot collision, front bumper damage",
            "incident_date": "2024-12-10",
            "estimated_damage_cost": 2500,
        }
        
        user_message_1 = f"""Analyze the risk for this insurance claim:

{json.dumps(test_claim_low_risk, indent=2)}

Please evaluate the claimant's history and provide a risk assessment."""
        
        logger.info("\n📌 Step 2: Running Risk Analysis (Low-Risk Case)...")
        response_1 = run_agent(agent.id, user_message_1)
        
        logger.info("\n📌 Step 3: Risk Assessment Results:")
        logger.info("=" * 80)
        
        assessment_1 = ""
        for msg in response_1:
            role = str(msg["role"]).lower()
            if "assistant" in role or "agent" in role:
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            text_data = item.get("text", {})
                            if isinstance(text_data, dict):
                                assessment_text = text_data.get("value", "")
                                logger.info(f"\n{assessment_text}\n")
                                assessment_1 = assessment_text
        logger.info("=" * 80)
        
        # Test Case 2: High-risk claimant
        logger.info("\n" + "=" * 80)
        logger.info("📋 Test Case 2: High-Risk Claimant (CLM-002)")
        logger.info("=" * 80)
        
        test_claim_high_risk = {
            "claim_id": "CLM-2024-888",
            "claimant_id": "CLM-002",
            "policy_number": "POL-2024-002",
            "incident_description": "Collision on highway, significant rear damage",
            "incident_date": "2024-12-11",
            "estimated_damage_cost": 7500,
        }
        
        user_message_2 = f"""Analyze the risk for this insurance claim:

{json.dumps(test_claim_high_risk, indent=2)}

Please evaluate the claimant's history and provide a risk assessment."""
        
        logger.info("\n📌 Step 4: Running Risk Analysis (High-Risk Case)...")
        response_2 = run_agent(agent.id, user_message_2)
        
        logger.info("\n📌 Step 5: Risk Assessment Results:")
        logger.info("=" * 80)
        
        assessment_2 = ""
        for msg in response_2:
            role = str(msg["role"]).lower()
            if "assistant" in role or "agent" in role:
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            text_data = item.get("text", {})
                            if isinstance(text_data, dict):
                                assessment_text = text_data.get("value", "")
                                logger.info(f"\n{assessment_text}\n")
                                assessment_2 = assessment_text
        logger.info("=" * 80)
        
        # Step 6: Validate assessments
        logger.info("\n📌 Step 6: Validating risk assessments...")
        
        validations = {
            "Low-risk case contains LOW_RISK": "LOW_RISK" in assessment_1.upper(),
            "Low-risk mentions claimant history": "CLM-001" in assessment_1 or "John Smith" in assessment_1 or "history" in assessment_1.lower(),
            "Low-risk mentions claim count": "2" in assessment_1 or "two" in assessment_1.lower(),
            "High-risk case contains HIGH_RISK or MEDIUM_RISK": "HIGH_RISK" in assessment_2.upper() or "MEDIUM_RISK" in assessment_2.upper(),
            "High-risk mentions fraud indicators": "fraud" in assessment_2.lower() or "indicator" in assessment_2.lower() or "frequency" in assessment_2.lower(),
            "High-risk mentions multiple claims": "5" in assessment_2 or "five" in assessment_2.lower() or "multiple" in assessment_2.lower(),
        }
        
        all_passed = True
        for check, passed in validations.items():
            status = "✅" if passed else "❌"
            logger.info(f"{status} {check}: {'PASS' if passed else 'FAIL'}")
            if not passed:
                all_passed = False
        
        # Step 7: Cleanup
        logger.info("\n📌 Step 7: Cleanup...")
        try:
            delete_agent(agent.id)
            logger.info(f"✅ Deleted agent: {agent.id}")
        except Exception as e:
            logger.warning(f"⚠️  Could not delete agent: {e}")
        
        if all_passed:
            logger.info("\n✅ All tests passed successfully!")
        else:
            logger.warning("\n⚠️  Some validation checks failed")
        
        return all_passed
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        logger.error("\n💡 Troubleshooting:")
        logger.error("   1. Ensure PROJECT_ENDPOINT is set in .env")
        logger.error("   2. Run 'az login' to authenticate")
        logger.error("   3. Verify Azure AI User role on the Foundry project")
        return False


if __name__ == "__main__":
    success = test_risk_analyst()
    exit(0 if success else 1)
