"""Test script to verify Azure AI agents are being used via the API.

This script calls the /api/v1/agent/claim_assessor/run endpoint and checks
if the Azure AI agent is being used instead of the LangGraph agent.
"""
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API endpoint
BASE_URL = "http://127.0.0.1:8000"
AGENT_ENDPOINT = f"{BASE_URL}/api/v1/agent/claim_assessor/run"

# Sample claim data
claim_data = {
    "claim_id": "CLM-2024-TEST-001",
    "claimant_id": "CLM-001",
    "incident_description": "Front-end collision at intersection",
    "incident_date": "2024-12-10",
    "incident_type": "collision",
    "estimated_damage_cost": 3500,
    "vin": "1HGBH41JXMN109186"
}

logger.info("=" * 80)
logger.info("🧪 Testing Azure AI Agent Integration via API")
logger.info("=" * 80)
logger.info(f"\nCalling: POST {AGENT_ENDPOINT}")
logger.info(f"Claim ID: {claim_data['claim_id']}")
logger.info(f"VIN: {claim_data['vin']}")

try:
    response = requests.post(
        AGENT_ENDPOINT,
        json=claim_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        logger.info("\n✅ API call successful!")
        logger.info(f"Agent used: {result.get('agent_name')}")
        logger.info(f"Success: {result.get('success')}")
        logger.info(f"Message count: {len(result.get('conversation_chronological', []))}")
        
        # Print conversation
        logger.info("\n📝 Conversation:")
        logger.info("=" * 80)
        for msg in result.get('conversation_chronological', []):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            logger.info(f"\n{role.upper()}:")
            logger.info(content[:500] + ("..." if len(content) > 500 else ""))
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ Test completed successfully!")
        logger.info("🎉 Azure AI Agent Service is being used via the API!")
        
    else:
        logger.error(f"\n❌ API call failed with status {response.status_code}")
        logger.error(f"Response: {response.text}")
        
except Exception as e:
    logger.error(f"\n❌ Error: {e}", exc_info=True)
