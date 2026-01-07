"""Script to test the Claims Data Analyst agent with Lakehouse-compatible IDs"""
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from app.core.config import get_settings
import json

settings = get_settings()
client = AIProjectClient(endpoint=settings.project_endpoint, credential=DefaultAzureCredential())

# Get the existing claims_data_analyst_v2 agent
AGENT_ID = "asst_QjzziOun7UQhtEqpQvwoAPaI"

def test_with_lakehouse_ids():
    """Test agent with IDs that match the Fabric Lakehouse data"""
    print("\n=== Testing with Lakehouse-Compatible IDs ===")
    thread = client.agents.threads.create()
    
    # Use IDs that match the Lakehouse tables:
    # - claimant_id: CLM-1310 (from claims_history)
    # - policy_number: POL-2025-914 (from policy_claims_summary)
    # - claim_type: Major Collision (from claims_history)
    claim_data = {
        "claim_id": "CLM-2026-000001",
        "claimant_name": "Linda Ramirez",
        "claimant_id": "CLM-1310",  # Matches claims_history claimant_id
        "policy_number": "POL-2025-914",  # Matches policy_claims_summary
        "claim_type": "Major Collision",
        "incident_date": "2025-05-22",
        "estimated_damage": 28392.64,
        "description": "Vehicle collision with significant damage",
        "status": "UNDER_REVIEW",
        "state": "CA"
    }
    
    user_message = f"""Please analyze enterprise data for this claim using the Fabric data tool:

{json.dumps(claim_data, indent=2)}

IMPORTANT: You MUST use the Microsoft Fabric tool to query the lakehouse data.

Query the Fabric data lakehouse to provide:
1. Historical claims data for this claimant (if any) - look up by claimant_id CLM-1310
2. Similar claims from other claimants for benchmarking - search by claim_type Major Collision
3. Regional statistics for the claim location - search by state CA
4. Any matching fraud patterns - check fraud_indicators table
5. Policy claims summary for POL-2025-914

Provide specific numbers and statistics from your Fabric data queries."""
    
    print(f"Testing with claimant_id: CLM-1310, policy_number: POL-2025-914")
    
    message = client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message
    )
    
    run = client.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=AGENT_ID,
        tool_choice={"type": "fabric_dataagent"}
    )
    
    print(f"Run status: {run.status}")
    print(f"Last error: {run.last_error}")
    
    messages = client.agents.messages.list(thread_id=thread.id)
    for msg in messages:
        if msg.role == "assistant":
            for content in msg.content:
                if hasattr(content, 'text') and hasattr(content.text, 'value'):
                    print(f"\nAgent Response:\n{content.text.value}")
    
    client.agents.threads.delete(thread_id=thread.id)
    return run.status


if __name__ == "__main__":
    print("Testing Claims Data Analyst with Lakehouse-Compatible IDs")
    print("=" * 60)
    
    status = test_with_lakehouse_ids()
    
    print("\n" + "=" * 60)
    print(f"Test result: {status}")
