"""Side-by-side comparison test: LangGraph vs Azure AI Agent Service.

This script runs the same claim through both the LangGraph claim assessor
and the Azure AI Agent Service claim assessor to verify they produce
equivalent results.
"""
import json
import logging
from typing import Dict, Any

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Reduce Azure SDK logging
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)


def run_langgraph_agent(claim_data: Dict[str, Any]) -> str:
    """Run the LangGraph claim assessor agent.
    
    Args:
        claim_data: Claim information dict
        
    Returns:
        Agent response as string
    """
    logger.info("\n" + "=" * 80)
    logger.info("🔷 Running LangGraph Claim Assessor")
    logger.info("=" * 80)
    
    from app.workflow.agents.claim_assessor import create_claim_assessor_agent
    from app.workflow.supervisor import LLM
    
    # Create LangGraph agent
    agent = create_claim_assessor_agent(LLM)
    
    # Prepare message
    messages = [
        {
            "role": "user",
            "content": f"Please process this insurance claim:\n\n{json.dumps(claim_data, indent=2)}"
        }
    ]
    
    # Run agent
    result = agent.invoke({"messages": messages})
    msgs = result.get("messages", []) if isinstance(result, dict) else result
    
    # Extract assistant response
    response = ""
    for msg in msgs:
        # Handle LangGraph BaseMessage objects
        if hasattr(msg, 'content'):
            if hasattr(msg, 'type') and msg.type == "ai":
                response = msg.content
                break
            elif not hasattr(msg, 'type'):  # Fallback for any message with content
                content = msg.content
                if content and len(content) > 0:
                    response = content
        # Handle dict format
        elif isinstance(msg, dict) and msg.get("role") == "assistant":
            response = msg.get("content", "")
            break
    
    # If still no response found, check all messages
    if not response:
        logger.warning("No AI message found in expected format. Checking all messages...")
        for i, msg in enumerate(msgs):
            logger.debug(f"Message {i}: type={type(msg)}, hasattr content={hasattr(msg, 'content')}")
            if hasattr(msg, 'content'):
                logger.debug(f"  Content preview: {str(msg.content)[:100]}")
                # Take the last message with content as fallback
                if msg.content:
                    response = msg.content
    
    logger.info(f"\n📄 LangGraph Response ({len(response)} chars):")
    logger.info("-" * 80)
    logger.info(response[:1000] + ("..." if len(response) > 1000 else ""))
    logger.info("-" * 80)
    
    return response


def run_azure_agent(claim_data: Dict[str, Any]) -> str:
    """Run the Azure AI Agent Service claim assessor.
    
    Args:
        claim_data: Claim information dict
        
    Returns:
        Agent response as string
    """
    logger.info("\n" + "=" * 80)
    logger.info("☁️  Running Azure AI Agent Service Claim Assessor")
    logger.info("=" * 80)
    
    from app.workflow.agents.azure_claim_assessor import create_claim_assessor_agent
    from app.workflow.azure_agent_client import get_project_client, run_agent
    
    # Get project client and create agent
    project_client = get_project_client()
    agent = create_claim_assessor_agent(project_client)
    
    # Prepare message
    user_message = f"Please process this insurance claim:\n\n{json.dumps(claim_data, indent=2)}"
    
    # Run agent
    messages = run_agent(agent.id, user_message)
    
    # Extract assistant response
    response = ""
    logger.debug(f"Received {len(messages)} messages from Azure agent")
    for i, msg in enumerate(messages):
        role = msg.get('role')
        # Convert role to string for comparison (handles MessageRole enum)
        role_str = str(role).lower() if role else ""
        logger.debug(f"Message {i}: role={role} (str: {role_str}), content type={type(msg.get('content'))}")
        
        # Check for assistant/agent role
        if role_str in ["assistant", "messagerole.agent", "agent"]:
            content = msg["content"]
            if isinstance(content, list):
                # Azure AI format: [{'type': 'text', 'text': {'value': '...', 'annotations': []}}]
                text_parts = []
                for item in content:
                    if item.get("type") == "text" and isinstance(item.get("text"), dict):
                        text_parts.append(item["text"].get("value", ""))
                response = "\n".join(text_parts)
            elif isinstance(content, str):
                response = content
            else:
                logger.warning(f"Unexpected content format: {type(content)}")
                response = str(content)
            
            if response:  # Found non-empty response
                break
    
    if not response:
        logger.warning(f"No assistant response found in {len(messages)} messages")
        for msg in messages:
            logger.debug(f"  Message role: {msg.get('role')}, content preview: {str(msg.get('content'))[:100]}")
    
    logger.info(f"\n📄 Azure AI Response ({len(response)} chars):")
    logger.info("-" * 80)
    logger.info(response[:1000] + ("..." if len(response) > 1000 else ""))
    logger.info("-" * 80)
    
    return response


def compare_responses(langgraph_response: str, azure_response: str):
    """Compare the two responses and provide analysis.
    
    Args:
        langgraph_response: Response from LangGraph agent
        azure_response: Response from Azure AI agent
    """
    logger.info("\n" + "=" * 80)
    logger.info("📊 COMPARISON ANALYSIS")
    logger.info("=" * 80)
    
    # Length comparison
    logger.info(f"\n📏 Response Length:")
    logger.info(f"  LangGraph: {len(langgraph_response)} characters")
    logger.info(f"  Azure AI:  {len(azure_response)} characters")
    logger.info(f"  Difference: {abs(len(langgraph_response) - len(azure_response))} characters")
    
    # Key terms analysis
    key_terms = [
        "VIN", "vehicle", "damage", "cost", "assessment",
        "VALID", "APPROVED", "DENIED", "value", "make", "model",
        "year", "Honda", "Civic", "collision", "repair"
    ]
    
    logger.info(f"\n🔍 Key Terms Presence:")
    for term in key_terms:
        in_langgraph = term.lower() in langgraph_response.lower()
        in_azure = term.lower() in azure_response.lower()
        if in_langgraph and in_azure:
            logger.info(f"  ✅ '{term}': Present in both")
        elif in_langgraph:
            logger.info(f"  ⚠️  '{term}': Only in LangGraph")
        elif in_azure:
            logger.info(f"  ⚠️  '{term}': Only in Azure AI")
        else:
            logger.info(f"  ❌ '{term}': Missing from both")
    
    # Decision analysis
    logger.info(f"\n⚖️  Decision Keywords:")
    decisions = ["VALID", "INVALID", "APPROVED", "DENIED", "INVESTIGATE"]
    for decision in decisions:
        if decision in langgraph_response.upper():
            logger.info(f"  LangGraph: Contains '{decision}'")
        if decision in azure_response.upper():
            logger.info(f"  Azure AI:  Contains '{decision}'")
    
    # Tool usage analysis
    logger.info(f"\n🔧 Tool Usage Indicators:")
    tool_indicators = {
        "get_vehicle_details": ["VIN", "vehicle details", "make", "model", "year"],
        "analyze_image": ["image", "photo", "visual", "damage photo"]
    }
    
    for tool, indicators in tool_indicators.items():
        langgraph_used = any(ind.lower() in langgraph_response.lower() for ind in indicators)
        azure_used = any(ind.lower() in azure_response.lower() for ind in indicators)
        
        if langgraph_used and azure_used:
            logger.info(f"  ✅ {tool}: Likely used by both")
        elif langgraph_used:
            logger.info(f"  ⚠️  {tool}: Only LangGraph shows indicators")
        elif azure_used:
            logger.info(f"  ⚠️  {tool}: Only Azure AI shows indicators")
        else:
            logger.info(f"  ❌ {tool}: No indicators in either response")
    
    # Overall assessment
    logger.info(f"\n📋 Overall Assessment:")
    
    # Check if both have similar structure
    langgraph_lines = len(langgraph_response.split('\n'))
    azure_lines = len(azure_response.split('\n'))
    logger.info(f"  Lines: LangGraph={langgraph_lines}, Azure AI={azure_lines}")
    
    # Similarity score (rough estimate)
    common_words = set(langgraph_response.lower().split()) & set(azure_response.lower().split())
    total_words = len(set(langgraph_response.lower().split()) | set(azure_response.lower().split()))
    similarity = len(common_words) / total_words if total_words > 0 else 0
    
    logger.info(f"  Word similarity: {similarity:.1%}")
    
    if similarity > 0.6:
        logger.info("\n  ✅ Agents appear to be providing similar analyses")
    elif similarity > 0.4:
        logger.info("\n  ⚠️  Agents have moderate similarity - review differences")
    else:
        logger.info("\n  ❌ Agents may be providing significantly different analyses")
    
    # Full text comparison
    logger.info("\n" + "=" * 80)
    logger.info("📝 FULL RESPONSES")
    logger.info("=" * 80)
    
    logger.info("\n🔷 LangGraph Full Response:")
    logger.info("-" * 80)
    logger.info(langgraph_response)
    logger.info("-" * 80)
    
    logger.info("\n☁️  Azure AI Full Response:")
    logger.info("-" * 80)
    logger.info(azure_response)
    logger.info("-" * 80)


def main():
    """Run side-by-side comparison test."""
    logger.info("=" * 80)
    logger.info("🧪 SIDE-BY-SIDE AGENT COMPARISON TEST")
    logger.info("   LangGraph vs Azure AI Agent Service")
    logger.info("=" * 80)
    
    # Sample claim data with VIN for tool calling
    claim_data = {
        "claim_id": "CLM-2024-TEST-001",
        "claimant_id": "CLM-001",
        "incident_description": "Front-end collision at intersection with another vehicle. Significant damage to front bumper, hood, and headlights.",
        "incident_date": "2024-12-10",
        "incident_type": "collision",
        "estimated_damage_cost": 4500,
        "vin": "1HGBH41JXMN109186",
        "location": "Main St & Oak Ave intersection"
    }
    
    logger.info(f"\n📋 Test Claim:")
    logger.info(f"  Claim ID: {claim_data['claim_id']}")
    logger.info(f"  VIN: {claim_data['vin']}")
    logger.info(f"  Incident: {claim_data['incident_description']}")
    logger.info(f"  Estimated Damage: ${claim_data['estimated_damage_cost']:,}")
    
    try:
        # Run both agents
        langgraph_response = run_langgraph_agent(claim_data)
        azure_response = run_azure_agent(claim_data)
        
        # Compare responses
        compare_responses(langgraph_response, azure_response)
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ COMPARISON TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    try:
        success = main()
        
        # Cleanup - delete test agents
        from app.workflow.azure_agent_client import delete_agent, find_agent_by_name
        logger.info("\n🧹 Cleaning up test agents...")
        agent = find_agent_by_name("claim_assessor")
        if agent:
            delete_agent(agent.id)
            logger.info(f"✅ Deleted claim_assessor agent: {agent.id}")
        
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test execution error: {e}", exc_info=True)
        exit(1)
