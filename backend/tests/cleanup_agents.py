"""Utility to clean up all test agents from Azure AI Foundry."""
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.workflow.azure_agent_client import list_agents, delete_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_test_agents():
    """Delete all claim_assessor and policy_checker agents (test agents)."""
    try:
        logger.info("🧹 Cleaning up test agents from Azure AI Foundry...")
        agents = list_agents()
        
        test_agent_names = ["claim_assessor", "policy_checker"]
        deleted_count = 0
        
        for agent in agents:
            if agent.name in test_agent_names:
                try:
                    logger.info(f"Deleting: {agent.name} ({agent.id})")
                    delete_agent(agent.id)
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Could not delete {agent.id}: {e}")
        
        logger.info(f"\n✅ Deleted {deleted_count} test agent(s)")
        
        # Show remaining agents
        remaining = list_agents()
        logger.info(f"\n📊 Remaining agents in Foundry: {len(remaining)}")
        for agent in remaining:
            logger.info(f"  - {agent.name} ({agent.id})")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)


if __name__ == "__main__":
    cleanup_test_agents()
