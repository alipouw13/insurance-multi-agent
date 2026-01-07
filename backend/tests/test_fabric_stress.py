"""Stress test for Fabric Data Agent to identify failure patterns.

This test validates Fabric Data Agent connectivity and performance under
various load conditions including sequential, parallel, and rapid-fire queries.

Requirements:
- Fabric capacity must be running (not paused)
- USE_FABRIC_DATA_AGENT=true in environment
- Valid FABRIC_CONNECTION_NAME configured
- claims_data_analyst_v2 agent registered

Usage:
    uv run python -m pytest tests/test_fabric_stress.py -v -s
    uv run python tests/test_fabric_stress.py  # standalone
"""
import os
import sys
import time
import json
import pytest
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import RunStatus

# Add parent to path for standalone execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import get_settings

# Test configuration
NUM_SEQUENTIAL_TESTS = 5
NUM_PARALLEL_TESTS = 3
DELAY_BETWEEN_TESTS = 1  # seconds

# Test queries of varying complexity
TEST_QUERIES = [
    # Simple queries
    "How many claims are in the claims_history table?",
    "What tables are available?",
    "Show me 5 recent claims",
    
    # Medium complexity
    "What is the fraud rate in California?",
    "What are the top 5 claim types by amount?",
    
    # Complex queries
    "Compare fraud rates across all states and show the top 3 highest",
    "What is the average claim amount by claim type?",
]


def get_fabric_agent_id() -> str:
    """Get the claims_data_analyst_v2 agent ID dynamically."""
    settings = get_settings()
    cred = DefaultAzureCredential()
    client = AIProjectClient(endpoint=settings.project_endpoint, credential=cred)
    
    agents = client.agents.list_agents()
    for agent in agents:
        if hasattr(agent, 'name') and agent.name == "claims_data_analyst_v2":
            return agent.id
    
    raise ValueError("Agent 'claims_data_analyst_v2' not found. Run register_agents.py first.")


def create_client():
    """Create a new client for each test."""
    settings = get_settings()
    cred = DefaultAzureCredential()
    return AIProjectClient(endpoint=settings.project_endpoint, credential=cred)


def run_single_query(query: str, test_id: int, agent_id: str) -> dict:
    """Run a single query and collect metrics."""
    client = create_client()
    result = {
        "test_id": test_id,
        "query": query[:50] + "..." if len(query) > 50 else query,
        "start_time": datetime.now().isoformat(),
        "status": None,
        "duration_seconds": None,
        "response_length": None,
        "error": None,
        "error_type": None,
        "run_status": None,
        "has_connectivity_error": False,
        "response_preview": None
    }
    
    start_time = time.time()
    
    try:
        # Create thread and message
        thread = client.agents.threads.create()
        client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=query
        )
        
        # Run with Fabric tool
        run = client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent_id,
            tool_choice={"type": "fabric_dataagent"}
        )
        
        result["run_status"] = str(run.status)
        result["duration_seconds"] = round(time.time() - start_time, 2)
        
        if run.status == RunStatus.COMPLETED:
            result["status"] = "success"
            
            # Get response
            messages = client.agents.messages.list(thread_id=thread.id)
            for msg in messages:
                if msg.role == "assistant":
                    content = ""
                    if isinstance(msg.content, list):
                        for item in msg.content:
                            if hasattr(item, 'text') and hasattr(item.text, 'value'):
                                content = item.text.value
                                break
                    
                    result["response_length"] = len(content)
                    result["response_preview"] = content[:100] + "..." if len(content) > 100 else content
                    
                    # Check for soft errors in response
                    error_phrases = [
                        "connectivity issue", "technical difficulties", "unable to retrieve",
                        "cannot access", "failed to connect", "encountered an issue",
                        "issue retrieving", "will retry", "please try again",
                        "i will now query", "currently unable", "facing difficulty"
                    ]
                    if any(phrase in content.lower() for phrase in error_phrases):
                        result["has_connectivity_error"] = True
                        result["status"] = "soft_error"
                        result["error_type"] = "connectivity_in_response"
                    break
                    
        elif run.status == RunStatus.FAILED:
            result["status"] = "failed"
            error_info = getattr(run, 'last_error', {})
            if isinstance(error_info, dict):
                result["error"] = error_info.get('message', str(error_info))
                result["error_type"] = error_info.get('code', 'unknown')
            else:
                result["error"] = str(error_info)
                result["error_type"] = "run_failed"
        else:
            result["status"] = "unexpected"
            result["error"] = f"Unexpected status: {run.status}"
            
        # Clean up
        try:
            client.agents.threads.delete(thread.id)
        except:
            pass
            
    except Exception as e:
        result["status"] = "exception"
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["duration_seconds"] = round(time.time() - start_time, 2)
    
    return result


class TestFabricStress:
    """Stress tests for Fabric Data Agent."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures."""
        settings = get_settings()
        if not settings.use_fabric_data_agent:
            pytest.skip("USE_FABRIC_DATA_AGENT is not enabled")
        
        self.agent_id = get_fabric_agent_id()
    
    def test_sequential_queries(self):
        """Run queries sequentially to test sustained load."""
        results = []
        success_count = 0
        
        for i in range(NUM_SEQUENTIAL_TESTS):
            query = TEST_QUERIES[i % len(TEST_QUERIES)]
            result = run_single_query(query, i + 1, self.agent_id)
            results.append(result)
            
            if result["status"] == "success":
                success_count += 1
            
            if i < NUM_SEQUENTIAL_TESTS - 1:
                time.sleep(DELAY_BETWEEN_TESTS)
        
        success_rate = success_count / NUM_SEQUENTIAL_TESTS
        assert success_rate >= 0.6, f"Sequential success rate too low: {success_rate:.1%}"
    
    def test_parallel_queries(self):
        """Run queries in parallel to test concurrent load."""
        results = []
        queries = TEST_QUERIES[:NUM_PARALLEL_TESTS]
        
        with ThreadPoolExecutor(max_workers=NUM_PARALLEL_TESTS) as executor:
            futures = {
                executor.submit(run_single_query, query, i + 100, self.agent_id): query 
                for i, query in enumerate(queries)
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({"status": "exception", "error": str(e)})
        
        success_count = sum(1 for r in results if r["status"] == "success")
        success_rate = success_count / NUM_PARALLEL_TESTS
        assert success_rate >= 0.5, f"Parallel success rate too low: {success_rate:.1%}"
    
    def test_single_query_basic(self):
        """Test a single basic query works."""
        result = run_single_query(
            "How many claims are in the claims_history table?",
            1,
            self.agent_id
        )
        assert result["status"] in ["success", "soft_error"], f"Query failed: {result.get('error')}"


def run_standalone_stress_test():
    """Run stress test standalone (not via pytest)."""
    print("=" * 70)
    print("FABRIC DATA AGENT STRESS TEST")
    print(f"Started at: {datetime.now().isoformat()}")
    print("=" * 70)
    
    settings = get_settings()
    if not settings.use_fabric_data_agent:
        print("ERROR: USE_FABRIC_DATA_AGENT is not enabled")
        return
    
    agent_id = get_fabric_agent_id()
    print(f"Agent ID: {agent_id}")
    
    all_results = []
    
    # Sequential tests
    print(f"\n--- Sequential Tests ({NUM_SEQUENTIAL_TESTS} queries) ---")
    for i in range(NUM_SEQUENTIAL_TESTS):
        query = TEST_QUERIES[i % len(TEST_QUERIES)]
        print(f"[{i+1}/{NUM_SEQUENTIAL_TESTS}] {query[:40]}...")
        
        result = run_single_query(query, i + 1, agent_id)
        all_results.append(result)
        
        status_emoji = "✅" if result["status"] == "success" else ("⚠️" if result["status"] == "soft_error" else "❌")
        print(f"  {status_emoji} {result['status']} ({result['duration_seconds']}s)")
        
        if i < NUM_SEQUENTIAL_TESTS - 1:
            time.sleep(DELAY_BETWEEN_TESTS)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total = len(all_results)
    success = sum(1 for r in all_results if r["status"] == "success")
    soft_errors = sum(1 for r in all_results if r["status"] == "soft_error")
    failures = total - success - soft_errors
    
    print(f"\nTotal Tests: {total}")
    print(f"  ✅ Success: {success} ({success/total*100:.1f}%)")
    print(f"  ⚠️  Soft Errors: {soft_errors} ({soft_errors/total*100:.1f}%)")
    print(f"  ❌ Hard Failures: {failures} ({failures/total*100:.1f}%)")
    
    durations = [r["duration_seconds"] for r in all_results if r["duration_seconds"]]
    if durations:
        print(f"\nTiming: Avg {sum(durations)/len(durations):.1f}s | Min {min(durations):.1f}s | Max {max(durations):.1f}s")


if __name__ == "__main__":
    run_standalone_stress_test()
