"""Test script for Azure AI Agent Service - Communication Agent

Run this script to test the migrated communication agent.

Usage:
    cd backend
    uv run python tests/test_azure_communication_agent.py
"""
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.workflow.agents.azure_communication_agent import create_communication_agent
from app.workflow.azure_agent_client import get_project_client, run_agent, delete_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def test_communication_agent():
    """Test the Communication Agent's ability to draft professional emails."""
    try:
        logger.info("\n" + "=" * 80)
        logger.info("🧪 Testing Azure AI Communication Agent")
        logger.info("=" * 80)
        
        # Step 1: Create agent
        logger.info("\n📌 Step 1: Creating Communication Agent...")
        agent = create_communication_agent()
        logger.info(f"✅ Agent created: {agent.id}")
        
        # Step 2: Prepare test scenario - missing information request
        logger.info("\n📌 Step 2: Preparing test scenario...")
        missing_info_request = {
            "claim_id": "CLM-2024-001",
            "customer_name": "John Smith",
            "claim_type": "Vehicle Collision",
            "missing_items": [
                "Police report reference number",
                "Photos of vehicle damage (all angles)",
                "Contact information for other driver involved",
                "Repair shop estimate or invoice"
            ],
            "incident_date": "2024-12-10",
            "policy_number": "POL-2024-001"
        }
        
        user_message = f"""Please draft a professional email to the customer requesting missing information for their claim.

Claim Details:
{json.dumps(missing_info_request, indent=2)}

The email should be clear, professional, and provide specific instructions on how to submit each item."""
        
        logger.info(f"Request prepared for claim: {missing_info_request['claim_id']}")
        
        # Step 3: Run agent
        logger.info("\n📌 Step 3: Running Communication Agent...")
        response = run_agent(agent.id, user_message)
        logger.info("✅ Agent completed email drafting")
        
        # Step 4: Display results
        logger.info("\n📌 Step 4: Email Draft:")
        logger.info("=" * 80)
        
        # Debug: Show raw response structure
        logger.info(f"DEBUG: Response type: {type(response)}")
        logger.info(f"DEBUG: Number of messages: {len(response)}")
        
        for msg in response:
            role = str(msg["role"]).lower()
            logger.info(f"DEBUG: Message role: {role}, type: {type(msg.get('content'))}")
            
            if "assistant" in role or "agent" in role:
                # Extract content
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            text_data = item.get("text", {})
                            if isinstance(text_data, dict):
                                email_text = text_data.get("value", "")
                                logger.info(f"\n{email_text}\n")
                elif isinstance(content, str):
                    logger.info(f"\n{content}\n")
        logger.info("=" * 80)
        
        # Step 5: Validate email structure
        logger.info("\n📌 Step 5: Validating email structure...")
        email_content = ""
        for msg in response:
            role = str(msg["role"]).lower()
            if "assistant" in role or "agent" in role:
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            text_data = item.get("text", {})
                            if isinstance(text_data, dict):
                                email_content = text_data.get("value", "")
        
        # Check for key email components
        validations = {
            "Has Subject line": "subject" in email_content.lower(),
            "Mentions customer name": missing_info_request["customer_name"] in email_content,
            "Mentions claim ID": missing_info_request["claim_id"] in email_content,
            "Lists missing items": any(item in email_content for item in missing_info_request["missing_items"]),
            "Professional tone": any(word in email_content.lower() for word in ["dear", "sincerely", "regards", "thank you"]),
            "Submission instructions": any(word in email_content.lower() for word in ["submit", "upload", "send", "provide"])
        }
        
        for check, passed in validations.items():
            status = "✅" if passed else "❌"
            logger.info(f"{status} {check}: {'PASS' if passed else 'FAIL'}")
        
        all_passed = all(validations.values())
        if all_passed:
            logger.info("\n✅ All validation checks passed!")
        else:
            logger.warning("\n⚠️  Some validation checks failed")
        
        # Step 6: Cleanup
        logger.info("\n📌 Step 6: Cleanup...")
        try:
            delete_agent(agent.id)
            logger.info(f"✅ Deleted agent: {agent.id}")
        except Exception as e:
            logger.warning(f"⚠️  Could not delete agent: {e}")
        
        logger.info("\n✅ Test completed successfully!")
        return all_passed
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        logger.error("\n💡 Troubleshooting:")
        logger.error("   1. Ensure PROJECT_ENDPOINT is set in .env")
        logger.error("   2. Run 'az login' to authenticate")
        logger.error("   3. Verify Azure AI User role on the Foundry project")
        return False


if __name__ == "__main__":
    success = test_communication_agent()
    exit(0 if success else 1)
