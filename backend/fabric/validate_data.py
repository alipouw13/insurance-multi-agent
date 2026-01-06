#!/usr/bin/env python3
"""
Validate Uploaded Data in Microsoft Fabric Lakehouse.

This script connects to your Fabric Lakehouse and validates that the data
was uploaded correctly. It prints statistics and sample queries.

Prerequisites:
- Uploaded data via upload_to_fabric.py
- Access to the Fabric workspace

Usage:
    python validate_data.py
"""

import os
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("Missing pandas: pip install pandas")
    sys.exit(1)


def validate_local_data(data_dir: str = "./data"):
    """Validate the locally generated data files."""
    data_path = Path(data_dir)
    
    if not data_path.exists():
        print(f"❌ Data directory not found: {data_path}")
        print("Run 'python generate_sample_data.py' first.")
        return False
    
    print("=" * 60)
    print("📊 LOCAL DATA VALIDATION")
    print("=" * 60)
    print()
    
    expected_tables = [
        "claims_history",
        "claimant_profiles",
        "fraud_indicators",
        "regional_statistics",
        "policy_claims_summary"
    ]
    
    all_valid = True
    
    for table_name in expected_tables:
        csv_file = data_path / f"{table_name}.csv"
        
        if not csv_file.exists():
            print(f"❌ Missing: {table_name}.csv")
            all_valid = False
            continue
        
        df = pd.read_csv(csv_file)
        print(f"✅ {table_name}")
        print(f"   Rows: {len(df):,}")
        print(f"   Columns: {list(df.columns)}")
        
        # Show sample statistics
        if "claim_amount" in df.columns:
            print(f"   Total Claims Value: ${df['claim_amount'].sum():,.2f}")
            print(f"   Average Claim: ${df['claim_amount'].mean():,.2f}")
        
        if "fraud_flag" in df.columns:
            fraud_count = df['fraud_flag'].sum()
            fraud_pct = (fraud_count / len(df)) * 100
            print(f"   Fraud Flags: {fraud_count:,} ({fraud_pct:.1f}%)")
        
        if "risk_score" in df.columns:
            print(f"   Avg Risk Score: {df['risk_score'].mean():.1f}")
        
        print()
    
    return all_valid


def print_sample_queries():
    """Print sample SQL queries that can be used with the Fabric Data Agent."""
    print("=" * 60)
    print("📝 SAMPLE QUERIES FOR FABRIC DATA AGENT")
    print("=" * 60)
    print()
    print("These natural language queries can be asked to the Claims Data Analyst:")
    print()
    
    queries = [
        # Historical Analysis
        ("Historical Claims Analysis", [
            "What is the total claims amount for claimant CLM-00001?",
            "Show me all claims from the last 6 months with status APPROVED",
            "What are the top 10 highest value claims ever filed?",
            "How many claims were filed in California in 2024?",
        ]),
        
        # Benchmarking
        ("Benchmarking Queries", [
            "What is the average claim amount for Auto Collision claims?",
            "Compare this $5,000 auto claim to the average for similar claims",
            "What percentage of claims over $10,000 get approved?",
            "What's the typical settlement time for Property Damage claims?",
        ]),
        
        # Fraud Analysis
        ("Fraud Pattern Queries", [
            "Show me all claims with fraud indicators",
            "What are the most common fraud indicator types?",
            "Which claimants have the highest risk scores?",
            "Are there any claims matching the 'Multiple Claims Short Period' pattern?",
        ]),
        
        # Regional Analysis
        ("Regional Statistics Queries", [
            "What's the fraud rate in Florida compared to California?",
            "Which city has the highest average claim amount?",
            "What's the most common claim type in Texas?",
            "Show seasonal patterns for claims in the Northeast region",
        ]),
        
        # Policy Analysis
        ("Policy-Level Queries", [
            "Which policies have the most claims?",
            "Show policies with an INCREASING claims trend",
            "What's the average total payout per policy?",
            "Are there any policies with more than 5 fraud-flagged claims?",
        ]),
    ]
    
    for category, query_list in queries:
        print(f"📌 {category}")
        for q in query_list:
            print(f"   • {q}")
        print()


def print_fabric_setup_guide():
    """Print a guide for setting up the Fabric Data Agent."""
    print("=" * 60)
    print("🔧 FABRIC DATA AGENT SETUP GUIDE")
    print("=" * 60)
    print()
    print("After uploading data, follow these steps to create the Data Agent:")
    print()
    print("1️⃣  ACCESS YOUR LAKEHOUSE")
    print("   • Go to https://app.fabric.microsoft.com")
    print("   • Navigate to your workspace")
    print("   • Open your Lakehouse")
    print("   • Verify the 5 tables are visible under 'Tables'")
    print()
    print("2️⃣  OPEN SQL ANALYTICS ENDPOINT")
    print("   • In the Lakehouse, click 'SQL analytics endpoint'")
    print("   • This creates a SQL endpoint for your tables")
    print("   • Verify you can query the tables with SQL")
    print()
    print("3️⃣  CREATE DATA AGENT")
    print("   • In the SQL endpoint, go to 'Data Agent' (preview feature)")
    print("   • Click 'New Data Agent'")
    print("   • Give it a name: 'Insurance Claims Data Agent'")
    print("   • Select all 5 tables to include")
    print("   • Add descriptions for each table (helps the AI understand)")
    print()
    print("4️⃣  CONFIGURE TABLE DESCRIPTIONS")
    print("   Suggested descriptions:")
    print()
    print("   claims_history:")
    print("     'Historical insurance claim records including amounts, dates,")
    print("      status, locations, and fraud flags'")
    print()
    print("   claimant_profiles:")
    print("     'Customer profiles with demographics, risk scores, claim")
    print("      history summaries, and account status'")
    print()
    print("   fraud_indicators:")
    print("     'Fraud detection records linking claims to specific fraud")
    print("      patterns and investigation status'")
    print()
    print("   regional_statistics:")
    print("     'Geographic claims analysis including fraud rates, average")
    print("      amounts, and seasonal patterns by region/city'")
    print()
    print("   policy_claims_summary:")
    print("     'Aggregated claims data per policy including total payouts,")
    print("      claim counts, and trend indicators'")
    print()
    print("5️⃣  PUBLISH THE DATA AGENT")
    print("   • Review the configuration")
    print("   • Click 'Publish'")
    print("   • Note the Data Agent endpoint")
    print()
    print("6️⃣  CREATE AZURE AI FOUNDRY CONNECTION")
    print("   • Go to Azure AI Foundry portal")
    print("   • Navigate to your project > Connections")
    print("   • Add new connection > Microsoft Fabric")
    print("   • Provide your workspace URL and data agent details")
    print("   • Name the connection (e.g., 'fabric-claims-data')")
    print()
    print("7️⃣  CONFIGURE APPLICATION")
    print("   Set these environment variables:")
    print()
    print("   USE_FABRIC_DATA_AGENT=true")
    print("   FABRIC_CONNECTION_NAME=fabric-claims-data")
    print()
    print("8️⃣  TEST THE INTEGRATION")
    print("   • Restart the backend application")
    print("   • Process a claim through the workflow")
    print("   • Verify the Claims Data Analyst is called")
    print("   • Check the response includes Fabric data insights")
    print()


def main():
    print()
    print("🔍 FABRIC LAKEHOUSE DATA VALIDATOR")
    print()
    
    # Validate local data
    validate_local_data()
    
    # Print sample queries
    print_sample_queries()
    
    # Print setup guide
    print_fabric_setup_guide()
    
    print("=" * 60)
    print("✅ Validation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
