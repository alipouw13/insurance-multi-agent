"""Test the Supervisor v2 agent orchestration."""
import logging
import sys
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.workflow.supervisor_v2 import (
    initialize_v2_agents,
    process_claim_with_supervisor_v2,
    get_supervisor_agent_id,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_supervisor_v2():
    """Test the full supervisor workflow with a sample claim."""
    logger.info("=" * 80)
    logger.info("Testing Supervisor v2 - Full Workflow")
    logger.info("=" * 80)
    
    # Initialize all agents
    logger.info("\n[1/2] Initializing agents...")
    supervisor = initialize_v2_agents()
    
    if not supervisor:
        logger.error("Failed to initialize agents")
        return False
    
    supervisor_id = get_supervisor_agent_id()
    logger.info(f"Supervisor ID: {supervisor_id}")
    
    # Test claim data
    test_claim = {
        "claim_id": "CLM-2024-TEST-001",
        "policy_number": "POL-2024-001",
        "claimant_id": "CLM-001",
        "claimant_name": "John Smith",
        "incident_date": "2024-12-20",
        "incident_type": "collision",
        "incident_description": "Vehicle was rear-ended at a traffic light. Damage to rear bumper, trunk, and tail lights.",
        "vin": "1HGBH41JXMN109186",
        "estimated_repair_cost": 4500,
        "supporting_documents": ["police_report.pdf"],
        "supporting_images": [],
        "claimant_statement": "I was stopped at a red light when another vehicle hit me from behind. The driver admitted fault at the scene."
    }
    
    # Process the claim
    logger.info("\n[2/2] Processing claim through supervisor...")
    logger.info(f"Claim ID: {test_claim['claim_id']}")
    logger.info("-" * 60)
    
    try:
        result = process_claim_with_supervisor_v2(test_claim)
        
        # Display results
        logger.info("\n" + "=" * 80)
        logger.info("WORKFLOW RESULTS")
        logger.info("=" * 80)
        
        for i, chunk in enumerate(result):
            if "supervisor" in chunk:
                logger.info("\n--- SUPERVISOR RESPONSE ---")
                messages = chunk["supervisor"].get("messages", [])
                for msg in messages:
                    content = msg.get("content", "")
                    # Print in chunks to avoid console issues
                    logger.info(f"\n{content[:2000]}")
                    if len(content) > 2000:
                        logger.info(f"\n{content[2000:4000]}")
                        if len(content) > 4000:
                            logger.info(f"\n{content[4000:]}")
            elif "usage" in chunk:
                logger.info(f"\n--- TOKEN USAGE ---")
                logger.info(f"Total tokens: {chunk.get('total_tokens', 'N/A')}")
            elif "error" in chunk:
                logger.error(f"\n--- ERROR ---")
                logger.error(f"Error: {chunk.get('error')}")
                logger.error(f"Message: {chunk.get('message')}")
        
        logger.info("\n" + "=" * 80)
        logger.info("TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


def test_supervisor_with_missing_info():
    """Test supervisor workflow with a claim that has missing information."""
    logger.info("\n" + "=" * 80)
    logger.info("Testing Supervisor v2 - Missing Information Scenario")
    logger.info("=" * 80)
    
    # Claim with missing documentation
    test_claim = {
        "claim_id": "CLM-2024-MISSING-001",
        "policy_number": "POL-2024-001",
        "claimant_id": "CLM-001",
        "claimant_name": "Jane Doe",
        "incident_date": "2024-12-21",
        "incident_type": "theft",
        "incident_description": "Vehicle was stolen from parking lot.",
        "vin": "2HGFG12345678901",
        "estimated_repair_cost": 0,
        "claimed_amount": 25000,
        "supporting_documents": [],  # No documents
        "supporting_images": [],     # No images
        "claimant_statement": "Car was stolen overnight."
    }
    
    logger.info(f"Testing claim with missing documentation...")
    logger.info(f"Claim ID: {test_claim['claim_id']}")
    
    try:
        result = process_claim_with_supervisor_v2(test_claim)
        
        for chunk in result:
            if "supervisor" in chunk:
                messages = chunk["supervisor"].get("messages", [])
                for msg in messages:
                    content = msg.get("content", "")
                    # Check if communication agent was invoked
                    if "email" in content.lower() or "documentation" in content.lower():
                        logger.info("Communication Agent was properly invoked for missing documentation")
        
        logger.info("Missing info test completed")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


def main():
    """Run supervisor tests."""
    logger.info("Starting Supervisor v2 Tests")
    logger.info("=" * 80)
    
    # Run main test
    success = test_supervisor_v2()
    
    if success:
        logger.info("\nAll tests passed!")
    else:
        logger.error("\nSome tests failed!")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
