#!/usr/bin/env python3
"""
Create and Configure Insurance Claims Data Agent using Fabric Data Agent SDK.

This script automates the creation and configuration of a Fabric Data Agent
for the Insurance Claims application using the fabric-data-agent-sdk.

Prerequisites:
- Run this script in a Microsoft Fabric notebook
- fabric-data-agent-sdk installed (%pip install -U fabric-data-agent-sdk)
- Lakehouse with claims data tables already created
- Appropriate Fabric permissions

Usage:
    Run cells in sequence in a Fabric notebook, or execute as a script.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Data Agent name
DATA_AGENT_NAME = "InsuranceClaimsDataAgent"

# Lakehouse name (must exist in your workspace with the claims data)
LAKEHOUSE_NAME = "InsuranceClaimsLakehouse"

# Schema name (default is 'dbo' for Lakehouse SQL endpoint)
SCHEMA_NAME = "dbo"

# Tables to include in the Data Agent
TABLES = [
    "claims_history",
    "claimant_profiles", 
    "fraud_indicators",
    "regional_statistics",
    "policy_claims_summary"
]

# Agent Instructions (AI Instructions in Fabric UI)
AGENT_INSTRUCTIONS = """
You are an Insurance Claims Data Analyst agent that helps users analyze historical claims data, identify patterns, assess risk, and support claim processing decisions.

## Your Role
You assist insurance professionals with:
- Analyzing historical claims data to support current claim assessments
- Identifying fraud patterns and risk indicators
- Providing benchmarking data for claim amounts by type and region
- Analyzing claimant history and risk profiles
- Generating insights about claims trends and patterns

## Query Routing Guidelines

### Use claims_history for:
- Looking up specific claims by claim_id or policy_number
- Analyzing claims by type, status, date range, or location
- Finding claims with specific characteristics (fraud_flag, police_report, photos_provided)
- Vehicle-related queries (by make, model, year, VIN)
- Calculating average claim amounts for specific claim types

### Use claimant_profiles for:
- Looking up claimant information by claimant_id
- Analyzing customer risk profiles (risk_score, credit_score, driving_record)
- Finding customers with specific claim frequencies
- Customer contact information queries

### Use fraud_indicators for:
- Finding claims with specific fraud patterns
- Analyzing fraud investigation status
- Identifying high-severity fraud indicators

### Use regional_statistics for:
- Comparing claim amounts across regions, states, or cities
- Analyzing fraud rates by geography
- Identifying seasonal claim patterns

### Use policy_claims_summary for:
- Analyzing policy-level claim history
- Identifying policies with increasing claim trends
- Finding policies with multiple fraud-flagged claims

## Important Definitions
- estimated_damage: Initial damage estimate in USD
- amount_paid: Actual amount paid for settled/approved claims
- risk_score: 0-100 scale (higher = more risky)
- fraud_flag: Boolean indicating potential fraud
- claim_frequency: very_low, low, medium, high, very_high
- credit_score: excellent, good, fair, poor
- driving_record: clean, minor_violations, major_violations
- claims_trend: INCREASING, STABLE, DECREASING, INSUFFICIENT_DATA

## Response Guidelines
1. Always provide specific numbers and statistics when available
2. Include relevant context about what the data represents
3. Flag any potential fraud indicators or risk factors
4. For amount queries, specify currency as USD
"""

# Data Source Instructions (per-datasource notes)
DATASOURCE_INSTRUCTIONS = """
When answering about claims, use the claims_history table for individual claim records.
When asked about customer risk or profiles, use the claimant_profiles table.
When asked about fraud patterns, check the fraud_indicators table.
When comparing to regional averages or benchmarks, use regional_statistics.
When analyzing policy-level trends, use policy_claims_summary.
Best selling/highest should be determined by count unless amount is specified.
Always include relevant identifiers (claim_id, policy_number, claimant_id) in responses.
"""

# Example Queries (Few-shot examples for better query generation)
EXAMPLE_QUERIES = {
    "What is the average claim amount for auto collision claims?": 
        "SELECT AVG(estimated_damage) as avg_claim_amount, COUNT(*) as total_claims FROM dbo.claims_history WHERE claim_type = 'Auto Collision'",
    
    "Show me all claims for policy POL-AUTO-001":
        "SELECT claim_id, claim_type, estimated_damage, amount_paid, claim_date, status, fraud_flag FROM dbo.claims_history WHERE policy_number = 'POL-AUTO-001' ORDER BY claim_date DESC",
    
    "What is the fraud rate in California?":
        "SELECT state, AVG(fraud_rate) as avg_fraud_rate FROM dbo.regional_statistics WHERE state = 'CA' GROUP BY state",
    
    "Find all high-risk claimants with risk score above 70":
        "SELECT claimant_id, name, risk_score, claim_frequency, credit_score, driving_record, total_claims_count FROM dbo.claimant_profiles WHERE risk_score > 70 ORDER BY risk_score DESC",
    
    "Show me all fraud indicators for claim CLM-00001":
        "SELECT indicator_id, indicator_type, severity, detected_date, pattern_description, investigation_status FROM dbo.fraud_indicators WHERE claim_id = 'CLM-00001' ORDER BY severity DESC",
    
    "Which policies have the most claims?":
        "SELECT policy_number, policy_type, total_claims, total_amount_paid, claims_trend, fraud_claims_count FROM dbo.policy_claims_summary ORDER BY total_claims DESC LIMIT 10",
    
    "What are the top fraud patterns detected?":
        "SELECT indicator_type, COUNT(*) as occurrence_count, COUNT(CASE WHEN severity = 'CRITICAL' THEN 1 END) as critical_count FROM dbo.fraud_indicators GROUP BY indicator_type ORDER BY occurrence_count DESC",
    
    "Show the risk profile for claimant CLM-001":
        "SELECT claimant_id, name, age, state, city, customer_since, total_claims_count, total_claims_amount, risk_score, claim_frequency, credit_score, driving_record, account_status FROM dbo.claimant_profiles WHERE claimant_id = 'CLM-001'",
    
    "Which cities have the highest fraud rates?":
        "SELECT city, state, fraud_rate, total_claims, avg_claim_amount FROM dbo.regional_statistics WHERE total_claims > 50 ORDER BY fraud_rate DESC LIMIT 10",
    
    "Show policies with increasing claim trends":
        "SELECT policy_number, policy_type, total_claims, total_amount_paid, avg_claim_amount, first_claim_date, last_claim_date FROM dbo.policy_claims_summary WHERE claims_trend = 'INCREASING' ORDER BY total_amount_paid DESC",
    
    "What is the average claim amount by vehicle make?":
        "SELECT vehicle_make, COUNT(*) as claim_count, AVG(estimated_damage) as avg_damage, SUM(CASE WHEN fraud_flag = true THEN 1 ELSE 0 END) as fraud_count FROM dbo.claims_history WHERE vehicle_make IS NOT NULL GROUP BY vehicle_make ORDER BY claim_count DESC LIMIT 15",
    
    "Find open fraud investigations with high severity":
        "SELECT fi.claim_id, fi.indicator_type, fi.severity, fi.detected_date, ch.claimant_name, ch.estimated_damage, ch.claim_type FROM dbo.fraud_indicators fi JOIN dbo.claims_history ch ON fi.claim_id = ch.claim_id WHERE fi.investigation_status = 'OPEN' AND fi.severity IN ('HIGH', 'CRITICAL') ORDER BY fi.detected_date DESC",
}


# ---------------------------------------------------------------------------
# Main Script Functions
# ---------------------------------------------------------------------------

def create_or_get_data_agent(agent_name: str):
    """Create a new Data Agent or get an existing one."""
    from fabric.dataagent.client import (
        FabricDataAgentManagement,
        create_data_agent,
    )
    
    try:
        # Try to create new agent
        print(f"Creating new Data Agent: {agent_name}")
        data_agent = create_data_agent(agent_name)
        print(f"✅ Created new Data Agent: {agent_name}")
    except Exception as e:
        if "conflict" in str(e).lower() or "already exists" in str(e).lower():
            # Agent already exists, connect to it
            print(f"Data Agent '{agent_name}' already exists, connecting...")
            data_agent = FabricDataAgentManagement(agent_name)
            print(f"✅ Connected to existing Data Agent: {agent_name}")
        else:
            raise e
    
    return data_agent


def configure_agent_instructions(data_agent, instructions: str):
    """Set the AI instructions for the Data Agent."""
    print("Setting agent instructions...")
    data_agent.update_configuration(instructions=instructions)
    config = data_agent.get_configuration()
    print(f"✅ Agent instructions set ({len(instructions)} characters)")
    return config


def add_lakehouse_datasource(data_agent, lakehouse_name: str):
    """Add a Lakehouse as a data source to the Data Agent."""
    print(f"Adding Lakehouse datasource: {lakehouse_name}")
    datasource = data_agent.add_datasource(lakehouse_name, type="lakehouse")
    print(f"✅ Added Lakehouse: {lakehouse_name}")
    return datasource


def select_tables(datasource, schema: str, tables: list):
    """Select specific tables from the datasource."""
    print(f"Selecting tables from schema '{schema}':")
    for table in tables:
        datasource.select(schema, table)
        print(f"   ✅ Selected: {table}")
    print(f"✅ Selected {len(tables)} tables")


def set_datasource_instructions(datasource, instructions: str):
    """Set additional instructions for the datasource."""
    print("Setting datasource instructions...")
    datasource.update_configuration(instructions=instructions)
    print(f"✅ Datasource instructions set ({len(instructions)} characters)")


def add_example_queries(datasource, examples: dict):
    """Add few-shot example queries to improve query generation."""
    print(f"Adding {len(examples)} example queries...")
    datasource.add_fewshots(examples)
    print(f"✅ Added {len(examples)} example queries")
    
    # Verify
    fewshots = datasource.get_fewshots()
    print(f"   Total few-shots in datasource: {len(fewshots)}")


def publish_data_agent(data_agent):
    """Publish the Data Agent to make it available."""
    print("Publishing Data Agent...")
    data_agent.publish()
    print("✅ Data Agent published successfully!")


def print_summary(data_agent, datasource):
    """Print a summary of the configured Data Agent."""
    print("\n" + "=" * 60)
    print("📊 DATA AGENT CONFIGURATION SUMMARY")
    print("=" * 60)
    
    config = data_agent.get_configuration()
    print(f"\nAgent Name: {DATA_AGENT_NAME}")
    print(f"Instructions Length: {len(config.instructions or '')} characters")
    
    datasources = data_agent.get_datasources()
    print(f"\nData Sources: {len(datasources)}")
    
    print("\nSelected Tables:")
    datasource.pretty_print()
    
    fewshots = datasource.get_fewshots()
    print(f"\nExample Queries: {len(fewshots)}")
    
    print("\n" + "=" * 60)


# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------

def main():
    """Main function to create and configure the Data Agent."""
    print("🚀 Insurance Claims Data Agent Setup")
    print("=" * 60)
    print()
    
    # Step 1: Create or connect to Data Agent
    data_agent = create_or_get_data_agent(DATA_AGENT_NAME)
    print()
    
    # Step 2: Set agent instructions
    configure_agent_instructions(data_agent, AGENT_INSTRUCTIONS)
    print()
    
    # Step 3: Add Lakehouse as datasource
    datasource = add_lakehouse_datasource(data_agent, LAKEHOUSE_NAME)
    print()
    
    # Step 4: Select tables
    select_tables(datasource, SCHEMA_NAME, TABLES)
    print()
    
    # Step 5: Set datasource instructions
    set_datasource_instructions(datasource, DATASOURCE_INSTRUCTIONS)
    print()
    
    # Step 6: Add example queries
    add_example_queries(datasource, EXAMPLE_QUERIES)
    print()
    
    # Step 7: Publish
    publish_data_agent(data_agent)
    print()
    
    # Print summary
    print_summary(data_agent, datasource)
    
    print("\n✅ Data Agent setup complete!")
    print("\nNext steps:")
    print("1. Test the Data Agent in Fabric UI")
    print("2. Create a connection in Azure AI Foundry")
    print("3. Set USE_FABRIC_DATA_AGENT=true in your .env file")
    
    return data_agent, datasource


# Run if executed directly (in notebook, run cells individually)
if __name__ == "__main__":
    data_agent, datasource = main()
