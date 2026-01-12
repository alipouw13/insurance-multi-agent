"""Diagnostic script to troubleshoot Fabric Data Agent connection.

This script checks:
1. Connection retrieval and format
2. FabricTool initialization
3. Agent creation with Fabric tool
4. Basic query execution

Run with: uv run python diagnose_fabric.py
"""
import os
import sys
import time
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_environment():
    """Check required environment variables."""
    print("\n" + "="*60)
    print("1. ENVIRONMENT VARIABLES CHECK")
    print("="*60)
    
    required_vars = [
        "PROJECT_ENDPOINT",
        "FABRIC_CONNECTION_NAME",
        "USE_FABRIC_DATA_AGENT",
    ]
    
    optional_vars = [
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_RESOURCE_GROUP",
        "AZURE_AI_PROJECT_NAME",
    ]
    
    all_ok = True
    for var in required_vars:
        value = os.environ.get(var, "")
        if value:
            # Mask sensitive parts
            display = value[:20] + "..." if len(value) > 20 else value
            print(f"  ✅ {var}: {display}")
        else:
            print(f"  ❌ {var}: NOT SET")
            all_ok = False
    
    print("\nOptional:")
    for var in optional_vars:
        value = os.environ.get(var, "")
        if value:
            display = value[:20] + "..." if len(value) > 20 else value
            print(f"  ℹ️  {var}: {display}")
        else:
            print(f"  ⚪ {var}: not set")
    
    return all_ok


def check_sdk_imports():
    """Check if required SDK components are available."""
    print("\n" + "="*60)
    print("2. SDK IMPORTS CHECK")
    print("="*60)
    
    try:
        from azure.ai.projects import AIProjectClient
        print("  ✅ AIProjectClient imported successfully")
    except ImportError as e:
        print(f"  ❌ AIProjectClient import failed: {e}")
        return False
    
    try:
        from azure.ai.agents.models import FabricTool
        print("  ✅ FabricTool imported successfully")
    except ImportError as e:
        print(f"  ❌ FabricTool import failed: {e}")
        print("     This may require a preview SDK version. Try:")
        print("     pip install azure-ai-agents --pre")
        return False
    
    try:
        from azure.identity import DefaultAzureCredential, AzureCliCredential
        print("  ✅ Azure Identity imported successfully")
    except ImportError as e:
        print(f"  ❌ Azure Identity import failed: {e}")
        return False
    
    return True


def check_authentication():
    """Check Azure authentication."""
    print("\n" + "="*60)
    print("3. AUTHENTICATION CHECK")
    print("="*60)
    
    from azure.identity import AzureCliCredential, DefaultAzureCredential
    
    # Try AzureCliCredential first (user identity)
    try:
        cli_cred = AzureCliCredential()
        token = cli_cred.get_token("https://management.azure.com/.default")
        print("  ✅ AzureCliCredential: Working")
        print(f"     Token expires: {token.expires_on}")
        return cli_cred
    except Exception as e:
        print(f"  ⚠️  AzureCliCredential failed: {e}")
        print("     Run 'az login' to authenticate with your user account")
    
    # Fallback to DefaultAzureCredential
    try:
        default_cred = DefaultAzureCredential()
        token = default_cred.get_token("https://management.azure.com/.default")
        print("  ✅ DefaultAzureCredential: Working")
        return default_cred
    except Exception as e:
        print(f"  ❌ DefaultAzureCredential failed: {e}")
        return None


def check_project_connection(credential):
    """Check AIProjectClient connection."""
    print("\n" + "="*60)
    print("4. AI PROJECT CLIENT CHECK")
    print("="*60)
    
    from azure.ai.projects import AIProjectClient
    from app.core.config import get_settings
    
    settings = get_settings()
    
    try:
        client = AIProjectClient(
            endpoint=settings.project_endpoint,
            credential=credential
        )
        print(f"  ✅ AIProjectClient created")
        print(f"     Endpoint: {settings.project_endpoint}")
        return client
    except Exception as e:
        print(f"  ❌ AIProjectClient creation failed: {e}")
        return None


def check_fabric_connection(client, connection_name: str):
    """Check Fabric connection details."""
    print("\n" + "="*60)
    print("5. FABRIC CONNECTION CHECK")
    print("="*60)
    
    try:
        # Get the connection
        connection = client.connections.get(connection_name)
        print(f"  ✅ Connection found: {connection_name}")
        print(f"\n  Connection Details:")
        print(f"     ID: {connection.id}")
        print(f"     Name: {getattr(connection, 'name', 'N/A')}")
        print(f"     Type: {getattr(connection, 'connection_type', 'N/A')}")
        
        # Check if ID is in ARM format
        if connection.id.startswith("/subscriptions/"):
            print(f"\n  ✅ Connection ID is in ARM resource format (correct)")
        else:
            print(f"\n  ⚠️  Connection ID may not be in expected ARM format")
            print(f"     Expected format: /subscriptions/.../connections/<name>")
        
        # Check connection properties/metadata
        if hasattr(connection, 'properties'):
            print(f"\n  Connection Properties:")
            for key, value in vars(connection).items():
                if not key.startswith('_'):
                    print(f"     {key}: {value}")
        
        return connection
    except Exception as e:
        print(f"  ❌ Failed to get connection '{connection_name}': {e}")
        
        # Try to list all connections
        print("\n  Available connections:")
        try:
            connections = client.connections.list()
            for conn in connections:
                conn_name = getattr(conn, 'name', 'unnamed')
                conn_type = getattr(conn, 'connection_type', 'unknown')
                print(f"     - {conn_name} ({conn_type})")
        except Exception as e2:
            print(f"     Could not list connections: {e2}")
        
        return None


def check_fabric_tool(connection_id: str):
    """Check FabricTool initialization."""
    print("\n" + "="*60)
    print("6. FABRIC TOOL CHECK")
    print("="*60)
    
    try:
        from azure.ai.agents.models import FabricTool
        
        fabric_tool = FabricTool(connection_id=connection_id)
        print(f"  ✅ FabricTool created successfully")
        print(f"     Connection ID: {connection_id[:50]}...")
        
        # Check tool definitions
        if hasattr(fabric_tool, 'definitions'):
            print(f"\n  Tool Definitions:")
            for i, defn in enumerate(fabric_tool.definitions):
                print(f"     [{i}] Type: {getattr(defn, 'type', 'unknown')}")
                if hasattr(defn, 'fabric'):
                    print(f"         Fabric config: {defn.fabric}")
        
        return fabric_tool
    except Exception as e:
        print(f"  ❌ FabricTool creation failed: {e}")
        return None


def test_agent_creation(client, fabric_tool, model_name: str = "gpt-4.1-mini"):
    """Test creating an agent with Fabric tool."""
    print("\n" + "="*60)
    print("7. AGENT CREATION TEST")
    print("="*60)
    
    try:
        agent = client.agents.create_agent(
            model=model_name,
            name="fabric_diagnostic_test",
            instructions="You are a test agent for Fabric connectivity diagnostics.",
            tools=fabric_tool.definitions,
            headers={"x-ms-enable-preview": "true"},
        )
        print(f"  ✅ Agent created successfully")
        print(f"     Agent ID: {agent.id}")
        print(f"     Model: {model_name}")
        print(f"     Tools: {len(agent.tools) if agent.tools else 0}")
        
        # List tool types
        if agent.tools:
            for tool in agent.tools:
                tool_type = getattr(tool, 'type', 'unknown')
                print(f"       - {tool_type}")
        
        return agent
    except Exception as e:
        print(f"  ❌ Agent creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_simple_query(client, agent_id: str):
    """Test a simple query to the Fabric agent."""
    print("\n" + "="*60)
    print("8. QUERY EXECUTION TEST")
    print("="*60)
    
    try:
        # Create thread (using correct SDK API)
        thread = client.agents.threads.create()
        print(f"  ✅ Thread created: {thread.id}")
        
        # Create message
        test_query = "What tables or data sources do you have access to? Please use the Fabric tool to check."
        message = client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=test_query
        )
        print(f"  ✅ Message created: {message.id}")
        print(f"     Query: {test_query}")
        
        # Run the agent
        print("\n  Running agent (this may take 30-60 seconds)...")
        start_time = time.time()
        
        run = client.agents.create_and_process_run(
            thread_id=thread.id,
            assistant_id=agent_id
        )
        
        elapsed = time.time() - start_time
        print(f"\n  Run completed in {elapsed:.1f} seconds")
        print(f"     Status: {run.status}")
        
        if run.status == "failed":
            print(f"  ❌ Run failed!")
            print(f"     Error: {run.last_error}")
            
            # Check for specific error patterns
            error_str = str(run.last_error) if run.last_error else ""
            if "fabric" in error_str.lower():
                print("\n  💡 Fabric-related error detected. Check:")
                print("     1. Is your Fabric capacity running (not paused)?")
                print("     2. Is the Fabric Data Agent published?")
                print("     3. Does the connection have correct workspace-id and artifact-id?")
            elif "connection" in error_str.lower():
                print("\n  💡 Connection error detected. Verify connection settings.")
            elif "authentication" in error_str.lower() or "authorization" in error_str.lower():
                print("\n  💡 Auth error. Ensure user has Fabric access and run 'az login'.")
            
            return False
        
        # Get response messages
        messages = client.agents.list_messages(thread_id=thread.id)
        print("\n  Response:")
        for msg in messages.data:
            if msg.role == "assistant":
                for content in msg.content:
                    if hasattr(content, 'text'):
                        response_text = content.text.value
                        # Print first 500 chars
                        preview = response_text[:500] + "..." if len(response_text) > 500 else response_text
                        print(f"     {preview}")
        
        # Cleanup
        try:
            client.agents.threads.delete(thread.id)
        except:
            pass
        
        return True
        
    except Exception as e:
        print(f"  ❌ Query execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_agent(client, agent_id: str):
    """Clean up the test agent."""
    print("\n" + "="*60)
    print("9. CLEANUP")
    print("="*60)
    
    try:
        client.agents.delete_agent(agent_id)
        print(f"  ✅ Test agent deleted: {agent_id}")
    except Exception as e:
        print(f"  ⚠️  Could not delete agent: {e}")


def main():
    """Run all diagnostic checks."""
    print("\n" + "="*60)
    print("  FABRIC DATA AGENT DIAGNOSTIC")
    print("="*60)
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    from app.core.config import get_settings
    settings = get_settings()
    
    # Run checks
    if not check_environment():
        print("\n❌ Environment check failed. Please set required variables.")
        return
    
    if not check_sdk_imports():
        print("\n❌ SDK import check failed. Please install required packages.")
        return
    
    credential = check_authentication()
    if not credential:
        print("\n❌ Authentication failed. Run 'az login' first.")
        return
    
    client = check_project_connection(credential)
    if not client:
        print("\n❌ Project connection failed.")
        return
    
    connection = check_fabric_connection(client, settings.fabric_connection_name)
    if not connection:
        print("\n❌ Fabric connection not found.")
        return
    
    fabric_tool = check_fabric_tool(connection.id)
    if not fabric_tool:
        print("\n❌ FabricTool creation failed.")
        return
    
    model = settings.azure_openai_deployment_name or "gpt-4.1-mini"
    agent = test_agent_creation(client, fabric_tool, model)
    if not agent:
        print("\n❌ Agent creation failed.")
        return
    
    success = test_simple_query(client, agent.id)
    
    cleanup_test_agent(client, agent.id)
    
    print("\n" + "="*60)
    print("  DIAGNOSTIC SUMMARY")
    print("="*60)
    
    if success:
        print("  ✅ All checks passed! Fabric Data Agent is working.")
    else:
        print("  ⚠️  Some checks failed. Review the output above for details.")
        print("\n  Common issues:")
        print("  1. Fabric capacity paused - Resume in Azure portal")
        print("  2. Data Agent not published - Publish from Fabric portal")
        print("  3. Wrong connection settings - Check workspace-id and artifact-id")
        print("  4. User auth required - Run 'az login' with Fabric access")
        print("  5. SDK version - Try: pip install azure-ai-agents --pre")


if __name__ == "__main__":
    main()
