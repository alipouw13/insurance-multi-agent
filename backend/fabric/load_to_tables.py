#!/usr/bin/env python3
"""
Load Parquet Files as Delta Tables in Microsoft Fabric Lakehouse.

This script uses the Fabric REST API to load parquet files from the Files
section into managed Delta tables in the Tables section.

Prerequisites:
- Azure CLI authenticated (az login)
- Parquet files uploaded to Lakehouse Files section
- Fabric workspace with appropriate permissions

Environment Variables:
- FABRIC_WORKSPACE_ID: Your Fabric workspace GUID
- FABRIC_LAKEHOUSE_ID: Your Lakehouse GUID

Usage:
    python load_to_tables.py [--folder claims_data]
"""

import argparse
import os
import sys
import time
import requests
from typing import Optional

try:
    from azure.identity import DefaultAzureCredential
except ImportError:
    print("Missing required package: azure-identity")
    print("Install with: pip install azure-identity")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"
CLAIMS_DATA_FOLDER = "claims_data"

# Tables to load with their configurations
TABLES_CONFIG = [
    {
        "file_name": "claims_history.parquet",
        "table_name": "claims_history",
        "description": "Historical insurance claim records including amounts, dates, status, and fraud flags"
    },
    {
        "file_name": "claimant_profiles.parquet",
        "table_name": "claimant_profiles",
        "description": "Customer profiles with demographics, risk scores, and claim history summaries"
    },
    {
        "file_name": "fraud_indicators.parquet",
        "table_name": "fraud_indicators",
        "description": "Fraud detection records linking claims to specific fraud patterns"
    },
    {
        "file_name": "regional_statistics.parquet",
        "table_name": "regional_statistics",
        "description": "Geographic claims analysis including fraud rates and seasonal patterns"
    },
    {
        "file_name": "policy_claims_summary.parquet",
        "table_name": "policy_claims_summary",
        "description": "Aggregated claims data per policy including total payouts and trends"
    }
]


# ---------------------------------------------------------------------------
# Fabric API Functions
# ---------------------------------------------------------------------------

def get_access_token() -> str:
    """Get an access token for Fabric API using DefaultAzureCredential."""
    credential = DefaultAzureCredential()
    token = credential.get_token("https://api.fabric.microsoft.com/.default")
    return token.token


def get_headers() -> dict:
    """Get headers for Fabric API requests."""
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }


def load_table_from_file(
    workspace_id: str,
    lakehouse_id: str,
    file_path: str,
    table_name: str,
    mode: str = "Overwrite"
) -> dict:
    """
    Load a parquet file as a Delta table using Fabric's Load Table API.
    
    Args:
        workspace_id: Fabric workspace GUID
        lakehouse_id: Lakehouse GUID
        file_path: Relative path to the parquet file in Files section
        table_name: Name for the target table
        mode: Load mode - "Overwrite" or "Append"
        
    Returns:
        API response dict
    """
    url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables/{table_name}/load"
    
    payload = {
        "relativePath": file_path,
        "pathType": "File",
        "mode": mode,
        "formatOptions": {
            "format": "Parquet"
        }
    }
    
    response = requests.post(url, headers=get_headers(), json=payload)
    
    if response.status_code == 202:
        # Async operation - get operation ID from Location header
        operation_location = response.headers.get("Location")
        return {
            "status": "accepted",
            "operation_location": operation_location,
            "operation_id": response.headers.get("x-ms-operation-id")
        }
    elif response.status_code == 200:
        return {"status": "completed", "data": response.json()}
    else:
        return {
            "status": "error",
            "status_code": response.status_code,
            "error": response.text
        }


def check_operation_status(operation_location: str) -> dict:
    """Check the status of an async operation."""
    response = requests.get(operation_location, headers=get_headers())
    
    if response.status_code == 200:
        return response.json()
    else:
        return {"status": "error", "error": response.text}


def wait_for_operation(
    operation_location: str,
    timeout_seconds: int = 300,
    poll_interval: int = 5
) -> dict:
    """Wait for an async operation to complete."""
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        result = check_operation_status(operation_location)
        status = result.get("status", "").lower()
        
        if status in ["succeeded", "completed"]:
            return {"status": "completed", "result": result}
        elif status in ["failed", "error"]:
            return {"status": "failed", "result": result}
        
        time.sleep(poll_interval)
    
    return {"status": "timeout"}


def list_lakehouse_tables(workspace_id: str, lakehouse_id: str) -> list:
    """List all tables in a Lakehouse."""
    url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables"
    
    response = requests.get(url, headers=get_headers())
    
    if response.status_code == 200:
        return response.json().get("data", [])
    else:
        print(f"Warning: Could not list tables: {response.text}")
        return []


# ---------------------------------------------------------------------------
# Alternative: Using Spark/SQL to load tables
# ---------------------------------------------------------------------------

def generate_spark_load_script(folder_name: str = CLAIMS_DATA_FOLDER) -> str:
    """
    Generate a PySpark script that can be run in a Fabric notebook
    to load the parquet files as Delta tables.
    
    This is an alternative if the REST API approach doesn't work.
    """
    script = f'''# PySpark script to load parquet files as Delta tables
# Run this in a Fabric notebook attached to your Lakehouse

from pyspark.sql import SparkSession

# Files are in the Files section under {folder_name}/
base_path = "Files/{folder_name}"

tables = [
    ("claims_history", "claims_history.parquet"),
    ("claimant_profiles", "claimant_profiles.parquet"),
    ("fraud_indicators", "fraud_indicators.parquet"),
    ("regional_statistics", "regional_statistics.parquet"),
    ("policy_claims_summary", "policy_claims_summary.parquet"),
]

for table_name, file_name in tables:
    print(f"Loading {{table_name}}...")
    
    # Read parquet file
    df = spark.read.parquet(f"{{base_path}}/{{file_name}}")
    
    # Write as Delta table (overwrites if exists)
    df.write.format("delta").mode("overwrite").saveAsTable(table_name)
    
    print(f"  ✅ Loaded {{df.count()}} rows into {{table_name}}")

print("\\n✅ All tables loaded successfully!")
'''
    return script


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Load parquet files as Delta tables in Fabric Lakehouse"
    )
    parser.add_argument(
        "--folder",
        type=str,
        default=CLAIMS_DATA_FOLDER,
        help=f"Folder name in Files section (default: {CLAIMS_DATA_FOLDER})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually loading"
    )
    parser.add_argument(
        "--generate-notebook",
        action="store_true",
        help="Generate a PySpark notebook script instead of using REST API"
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        default=True,
        help="Wait for each load operation to complete (default: True)"
    )
    
    args = parser.parse_args()
    
    # Get environment variables
    workspace_id = os.environ.get("FABRIC_WORKSPACE_ID")
    lakehouse_id = os.environ.get("FABRIC_LAKEHOUSE_ID")
    
    if not workspace_id or not lakehouse_id:
        print("❌ Error: Required environment variables not set.")
        print()
        print("Please set:")
        print("  FABRIC_WORKSPACE_ID  - Your Fabric workspace GUID")
        print("  FABRIC_LAKEHOUSE_ID  - Your Lakehouse GUID")
        sys.exit(1)
    
    # Generate notebook script option
    if args.generate_notebook:
        print("📓 PySpark Notebook Script")
        print("=" * 60)
        print("Copy this script and run it in a Fabric notebook:")
        print("=" * 60)
        print()
        print(generate_spark_load_script(args.folder))
        return
    
    print(f"🔄 Loading parquet files as Delta tables")
    print(f"   Workspace ID: {workspace_id}")
    print(f"   Lakehouse ID: {lakehouse_id}")
    print(f"   Source folder: Files/{args.folder}/")
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN - No tables will be loaded")
        print()
        for config in TABLES_CONFIG:
            print(f"   Would load: Files/{args.folder}/{config['file_name']} → Tables/{config['table_name']}")
        return
    
    # Load each table
    success_count = 0
    failed_tables = []
    
    for config in TABLES_CONFIG:
        file_path = f"Files/{args.folder}/{config['file_name']}"
        table_name = config["table_name"]
        
        print(f"📥 Loading {table_name}...")
        print(f"   Source: {file_path}")
        
        try:
            result = load_table_from_file(
                workspace_id=workspace_id,
                lakehouse_id=lakehouse_id,
                file_path=file_path,
                table_name=table_name,
                mode="Overwrite"
            )
            
            if result["status"] == "accepted" and args.wait:
                print(f"   ⏳ Waiting for operation to complete...")
                operation_result = wait_for_operation(
                    result["operation_location"],
                    timeout_seconds=300
                )
                
                if operation_result["status"] == "completed":
                    print(f"   ✅ Successfully loaded {table_name}")
                    success_count += 1
                else:
                    print(f"   ❌ Failed: {operation_result}")
                    failed_tables.append(table_name)
                    
            elif result["status"] == "completed":
                print(f"   ✅ Successfully loaded {table_name}")
                success_count += 1
                
            elif result["status"] == "accepted":
                print(f"   ⏳ Load started (not waiting for completion)")
                success_count += 1
                
            else:
                print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
                failed_tables.append(table_name)
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed_tables.append(table_name)
    
    print()
    print("=" * 60)
    print(f"✅ Load complete: {success_count}/{len(TABLES_CONFIG)} tables")
    
    if failed_tables:
        print(f"❌ Failed tables: {', '.join(failed_tables)}")
        print()
        print("💡 TIP: If the REST API fails, try the notebook approach:")
        print("   python load_to_tables.py --generate-notebook")
    
    print("=" * 60)
    print()
    
    # List tables to verify
    print("📋 Verifying tables in Lakehouse...")
    try:
        tables = list_lakehouse_tables(workspace_id, lakehouse_id)
        if tables:
            print(f"   Found {len(tables)} tables:")
            for table in tables:
                print(f"      - {table.get('name', 'unknown')}")
        else:
            print("   No tables found (this may take a moment to update)")
    except Exception as e:
        print(f"   Could not verify tables: {e}")
    
    print()
    print("Next steps:")
    print("   1. Open Lakehouse in Fabric and verify tables")
    print("   2. Open SQL Analytics Endpoint")
    print("   3. Create a Data Agent and select the tables")
    print("   4. Publish the Data Agent")
    print("   5. Create a connection in Azure AI Foundry")


if __name__ == "__main__":
    main()
