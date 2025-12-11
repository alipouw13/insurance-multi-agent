"""Test runner for Azure AI Agent Service tests.

This script runs all Azure agent tests and ensures proper cleanup.
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_all_agents():
    """Clean up all test agents from Azure AI Foundry."""
    try:
        from app.workflow.azure_agent_client import list_agents, delete_agent
        
        logger.info("\n🧹 Cleaning up all agents...")
        agents = list_agents()
        
        if not agents:
            logger.info("No agents found to clean up")
            return
        
        for agent in agents:
            try:
                logger.info(f"Deleting agent: {agent.name} ({agent.id})")
                delete_agent(agent.id)
            except Exception as e:
                logger.warning(f"Could not delete agent {agent.id}: {e}")
        
        logger.info("✅ Cleanup completed")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)


def run_all_tests():
    """Run all Azure agent tests."""
    logger.info("=" * 80)
    logger.info("🧪 Running Azure AI Agent Service Tests")
    logger.info("=" * 80)
    
    results = {}
    
    # Test 1: Claim Assessor
    logger.info("\n📋 Test 1: Claim Assessor Agent")
    logger.info("-" * 80)
    try:
        from tests.test_azure_claim_assessor import test_claim_assessment
        results['claim_assessor'] = test_claim_assessment()
    except Exception as e:
        logger.error(f"Claim Assessor test failed: {e}", exc_info=True)
        results['claim_assessor'] = False
    
    # Test 2: Policy Checker
    logger.info("\n📋 Test 2: Policy Checker Agent")
    logger.info("-" * 80)
    try:
        from tests.test_azure_policy_checker import test_policy_verification, test_dutch_policy_verification
        success1 = test_policy_verification()
        success2 = test_dutch_policy_verification()
        results['policy_checker'] = success1 and success2
    except Exception as e:
        logger.error(f"Policy Checker test failed: {e}", exc_info=True)
        results['policy_checker'] = False
    
    # Test 3: Agent Comparison
    logger.info("\n📋 Test 3: LangGraph vs Azure AI Comparison")
    logger.info("-" * 80)
    try:
        from tests.test_agent_comparison import main as run_comparison
        results['comparison'] = run_comparison()
    except Exception as e:
        logger.error(f"Comparison test failed: {e}", exc_info=True)
        results['comparison'] = False
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED")
    else:
        logger.info("❌ SOME TESTS FAILED")
    logger.info("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    try:
        all_passed = run_all_tests()
        
        # Always cleanup agents after tests
        cleanup_all_agents()
        
        sys.exit(0 if all_passed else 1)
        
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Tests interrupted by user")
        cleanup_all_agents()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test runner error: {e}", exc_info=True)
        cleanup_all_agents()
        sys.exit(1)
