"""Simple Azure agent test to debug message extraction."""
import logging
import json
from app.workflow.agents.azure_claim_assessor import create_claim_assessor_agent
from app.workflow.azure_agent_client import get_project_client, run_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

claim_data = {
    "claim_id": "CLM-TEST-001",
    "vin": "1HGBH41JXMN109186",
    "incident_description": "Front collision",
    "estimated_damage_cost": 4500
}

# Create agent and run
project_client = get_project_client()
agent = create_claim_assessor_agent(project_client)
user_message = f"Process this claim:\n\n{json.dumps(claim_data, indent=2)}"
messages = run_agent(agent.id, user_message)

print(f"\n=== Got {len(messages)} messages ===\n")
for i, msg in enumerate(messages):
    print(f"Message {i}:")
    print(f"  Role: {msg.get('role')} (type: {type(msg.get('role'))})")
    print(f"  Content type: {type(msg.get('content'))}")
    content = msg.get('content')
    if isinstance(content, list):
        print(f"  Content is list with {len(content)} items")
        for j, item in enumerate(content):
            print(f"    Item {j}: {item}")
    else:
        print(f"  Content: {str(content)[:200]}")
    print()
