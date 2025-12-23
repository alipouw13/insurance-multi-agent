"""Test Azure AI Agent Service agents using new SDK (v2)."""
import logging
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.workflow.azure_agent_manager_v2 import deploy_azure_agents_v2, get_azure_agent_id_v2, get_azure_agent_toolset_v2
from app.workflow.azure_agent_client_v2 import run_agent_v2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_claim_assessor_v2():
    """Test the Claim Assessor agent (v2)."""
    logger.info("\n" + "="*80)
    logger.info("Testing Claim Assessor Agent (v2)")
    logger.info("="*80)
    
    agent_id = get_azure_agent_id_v2("claim_assessor")
    toolset = get_azure_agent_toolset_v2("claim_assessor")
    if not agent_id:
        logger.error("❌ Claim Assessor agent not deployed")
        return False
    
    test_message = """Please assess this claim:
    
Claim ID: CLM-TEST-001
Policy: POL-2024-001
VIN: 1HGBH41JXMN109186
Incident: Vehicle rear-ended at traffic light, damage to rear bumper and trunk
Estimated Repair: $3,500
Supporting Images: None provided yet

Please analyze this claim."""
    
    try:
        messages, usage = run_agent_v2(agent_id, test_message, toolset=toolset)
        logger.info(f"\n✅ Agent Response:\n{messages[0]['content'] if messages else 'No response'}")
        logger.info(f"\n📊 Token Usage: {usage}")
        return True
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


def test_policy_checker_v2():
    """Test the Policy Checker agent (v2)."""
    logger.info("\n" + "="*80)
    logger.info("Testing Policy Checker Agent (v2)")
    logger.info("="*80)
    
    agent_id = get_azure_agent_id_v2("policy_checker")
    toolset = get_azure_agent_toolset_v2("policy_checker")
    if not agent_id:
        logger.error("❌ Policy Checker agent not deployed")
        return False
    
    test_message = """Please verify coverage for this claim:
    
Policy Number: POL-2024-001
Damage Type: Collision (rear-end)
Claim Amount: $3,500

Is this claim covered under the policy?"""
    
    try:
        messages, usage = run_agent_v2(agent_id, test_message, toolset=toolset)
        logger.info(f"\n✅ Agent Response:\n{messages[0]['content'] if messages else 'No response'}")
        logger.info(f"\n📊 Token Usage: {usage}")
        return True
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


def test_risk_analyst_v2():
    """Test the Risk Analyst agent (v2)."""
    logger.info("\n" + "="*80)
    logger.info("Testing Risk Analyst Agent (v2)")
    logger.info("="*80)
    
    agent_id = get_azure_agent_id_v2("risk_analyst")
    toolset = get_azure_agent_toolset_v2("risk_analyst")
    if not agent_id:
        logger.error("❌ Risk Analyst agent not deployed")
        return False
    
    test_message = """Please analyze the risk for this claim:
    
Claimant ID: CLM-001
Claim Amount: $3,500
Incident Type: Collision

What is the risk level for this claim?"""
    
    try:
        messages, usage = run_agent_v2(agent_id, test_message, toolset=toolset)
        logger.info(f"\n✅ Agent Response:\n{messages[0]['content'] if messages else 'No response'}")
        logger.info(f"\n📊 Token Usage: {usage}")
        return True
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


def test_communication_agent_v2():
    """Test the Communication agent (v2)."""
    logger.info("\n" + "="*80)
    logger.info("Testing Communication Agent (v2)")
    logger.info("="*80)
    
    agent_id = get_azure_agent_id_v2("communication_agent")
    toolset = get_azure_agent_toolset_v2("communication_agent")  # Will be None
    if not agent_id:
        logger.error("❌ Communication agent not deployed")
        return False
    
    test_message = """Please draft an email to the claimant requesting additional documentation:
    
Claim ID: CLM-TEST-001
Claimant: John Smith
Missing: Photos of rear damage and police report

Draft a professional request email."""
    
    try:
        messages, usage = run_agent_v2(agent_id, test_message, toolset=toolset)
        logger.info(f"\n✅ Agent Response:\n{messages[0]['content'] if messages else 'No response'}")
        logger.info(f"\n📊 Token Usage: {usage}")
        return True
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


def main():
    """Run all agent tests."""
    logger.info("🚀 Starting Azure AI Agent Service v2 Tests")
    
    # Deploy agents
    logger.info("\n📦 Deploying agents...")
    agents = deploy_azure_agents_v2()
    
    if not agents:
        logger.error("❌ No agents deployed. Check your PROJECT_ENDPOINT configuration.")
        return
    
    logger.info(f"✅ Deployed {len(agents)} agents: {list(agents.keys())}")
    
    # Run tests
    results = {
        "Claim Assessor": test_claim_assessor_v2(),
        "Policy Checker": test_policy_checker_v2(),
        "Risk Analyst": test_risk_analyst_v2(),
        "Communication Agent": test_communication_agent_v2(),
    }
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    for agent_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{agent_name}: {status}")
    
    passed_count = sum(results.values())
    total_count = len(results)
    logger.info(f"\nTotal: {passed_count}/{total_count} tests passed")


if __name__ == "__main__":
    main()
