#!/usr/bin/env python3
"""
Upload Sample Data to Microsoft Fabric Lakehouse.

This script uploads the generated CSV data to a Microsoft Fabric Lakehouse
as Parquet files. The data will be accessible through the Fabric Data Agent.

Prerequisites:
- Azure CLI authenticated (az login)
- Generated CSV files from generate_sample_data.py
- Fabric workspace with a Lakehouse created

Environment Variables:
- FABRIC_WORKSPACE_NAME: Your Fabric workspace name (e.g., "MyWorkspace")
- FABRIC_LAKEHOUSE_NAME: Your Lakehouse name (e.g., "LH_AIClaimsDemo")

OneLake Endpoint:
  The script uses the fixed OneLake endpoint: https://onelake.dfs.fabric.microsoft.com
  Files are uploaded to: {workspace_name}/{lakehouse_name}.Lakehouse/Files/claims_data/

Usage:
    python upload_to_fabric.py [--data-dir ./data]
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import pandas as pd
    from azure.identity import DefaultAzureCredential
    from azure.storage.filedatalake import DataLakeServiceClient
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install pandas azure-identity azure-storage-file-datalake")
    sys.exit(1)

# Optional: Delta Lake support
try:
    from deltalake import write_deltalake, DeltaTable
    DELTA_AVAILABLE = True
except ImportError:
    DELTA_AVAILABLE = False
    print("⚠️  deltalake package not installed - will upload as Parquet files")
    print("   Install with: pip install deltalake")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Table schemas for type casting
TABLE_SCHEMAS = {
    "claims_history": {
        "claim_id": "string",
        "policy_number": "string",
        "claimant_id": "string",
        "claimant_name": "string",
        "claim_type": "string",
        "estimated_damage": "float64",
        "amount_paid": "float64",
        "claim_date": "string",
        "incident_date": "string",
        "settlement_date": "string",
        "status": "string",
        "location": "string",
        "state": "string",
        "description": "string",
        "police_report": "bool",
        "photos_provided": "bool",
        "witness_statements": "string",
        "vehicle_vin": "string",
        "vehicle_make": "string",
        "vehicle_model": "string",
        "vehicle_year": "int32",
        "license_plate": "string",
        "fraud_flag": "bool"
    },
    "claimant_profiles": {
        "claimant_id": "string",
        "name": "string",
        "age": "int32",
        "state": "string",
        "city": "string",
        "address": "string",
        "phone": "string",
        "email": "string",
        "customer_since": "string",
        "total_claims_count": "int32",
        "total_claims_amount": "float64",
        "average_claim_amount": "float64",
        "risk_score": "float64",
        "claim_frequency": "string",
        "credit_score": "string",
        "driving_record": "string",
        "policy_count": "int32",
        "account_status": "string"
    },
    "fraud_indicators": {
        "indicator_id": "string",
        "claim_id": "string",
        "indicator_type": "string",
        "severity": "string",
        "detected_date": "string",
        "pattern_description": "string",
        "investigation_status": "string"
    },
    "regional_statistics": {
        "region": "string",
        "state": "string",
        "city": "string",
        "avg_claim_amount": "float64",
        "claim_frequency": "float64",
        "fraud_rate": "float64",
        "most_common_claim_type": "string",
        "seasonal_peak": "string",
        "total_claims": "int32",
        "year": "int32"
    },
    "policy_claims_summary": {
        "policy_number": "string",
        "total_claims": "int32",
        "total_amount_paid": "float64",
        "avg_claim_amount": "float64",
        "last_claim_date": "string",
        "first_claim_date": "string",
        "claims_trend": "string",
        "policy_type": "string",
        "fraud_claims_count": "int32"
    }
}


# ---------------------------------------------------------------------------
# Upload Functions
# ---------------------------------------------------------------------------

def get_datalake_client() -> DataLakeServiceClient:
    """Create a DataLake service client using DefaultAzureCredential.
    
    OneLake uses a fixed endpoint: https://onelake.dfs.fabric.microsoft.com
    No storage account configuration is needed.
    """
    # OneLake uses the fixed onelake.dfs.fabric.microsoft.com endpoint
    account_url = "https://onelake.dfs.fabric.microsoft.com"
    
    # Use DefaultAzureCredential with the Storage scope for OneLake
    credential = DefaultAzureCredential(
        exclude_shared_token_cache_credential=True
    )
    
    return DataLakeServiceClient(
        account_url=account_url,
        credential=credential
    )


# Default folder name for claims data in the Files section
CLAIMS_DATA_FOLDER = "claims_data"


def upload_to_onelake(
    df: pd.DataFrame,
    table_name: str,
    workspace_name: str,
    lakehouse_name: str,
    datalake_client: DataLakeServiceClient,
    folder_name: str = CLAIMS_DATA_FOLDER
) -> str:
    """Upload a DataFrame to OneLake Files section as a Parquet file.
    
    Args:
        df: DataFrame to upload
        table_name: Name of the file (without extension)
        workspace_name: Fabric workspace name
        lakehouse_name: Lakehouse name
        datalake_client: DataLake service client
        folder_name: Folder name under Files section (default: claims_data)
        
    Returns:
        Path to uploaded file
    """
    # OneLake path structure: workspace_name/lakehouse_name.Lakehouse/Files/folder_name
    # The workspace name is used as the file system (container)
    file_system_name = workspace_name
    
    # Get filesystem client for the workspace
    filesystem_client = datalake_client.get_file_system_client(file_system_name)
    
    # Create the Files directory path with a dedicated folder
    files_path = f"{lakehouse_name}.Lakehouse/Files/{folder_name}"
    
    # Create directory if it doesn't exist
    try:
        directory_client = filesystem_client.get_directory_client(files_path)
        directory_client.create_directory()
        print(f"   Created directory: Files/{folder_name}")
    except Exception as e:
        # Directory might already exist
        pass
    
    # Convert DataFrame to Parquet bytes
    import io
    parquet_buffer = io.BytesIO()
    df.to_parquet(parquet_buffer, index=False, engine='pyarrow')
    parquet_buffer.seek(0)
    
    # Upload the file with a clean name
    file_name = f"{table_name}.parquet"
    file_path = f"{files_path}/{file_name}"
    
    file_client = filesystem_client.get_file_client(file_path)
    file_client.upload_data(parquet_buffer.getvalue(), overwrite=True)
    
    return file_path


def upload_as_delta(
    df: pd.DataFrame,
    table_name: str,
    workspace_name: str,
    lakehouse_name: str,
    folder_name: str = CLAIMS_DATA_FOLDER
) -> str:
    """Upload a DataFrame as a Delta table using deltalake library.
    
    Args:
        df: DataFrame to upload
        table_name: Name of the table
        workspace_name: Fabric workspace name
        lakehouse_name: Lakehouse name
        folder_name: Folder name under Files section (default: claims_data)
        
    Returns:
        Path to Delta table
    """
    if not DELTA_AVAILABLE:
        raise ImportError("deltalake package not installed")
    
    # OneLake abfss path for Files section
    storage_options = {
        "account_name": "onelake",
        "use_fabric_endpoint": "true"
    }
    
    delta_path = f"abfss://{workspace_name}@onelake.dfs.fabric.microsoft.com/{lakehouse_name}.Lakehouse/Files/{folder_name}/{table_name}"
    
    write_deltalake(
        delta_path,
        df,
        mode="overwrite",
        storage_options=storage_options
    )
    
    return delta_path


def process_csv_file(csv_path: Path, table_name: str) -> pd.DataFrame:
    """Load and process a CSV file with proper type casting.
    
    Args:
        csv_path: Path to CSV file
        table_name: Name of the table for schema lookup
        
    Returns:
        Processed DataFrame
    """
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Apply schema if available
    schema = TABLE_SCHEMAS.get(table_name)
    if schema:
        for col, dtype in schema.items():
            if col in df.columns:
                try:
                    if dtype == "bool":
                        df[col] = df[col].astype(bool)
                    elif dtype in ["int32", "int64"]:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(dtype)
                    elif dtype in ["float32", "float64"]:
                        df[col] = pd.to_numeric(df[col], errors='coerce').astype(dtype)
                    else:
                        df[col] = df[col].astype(str).replace('nan', '')
                except Exception as e:
                    print(f"   ⚠️  Warning: Could not cast {col} to {dtype}: {e}")
    
    return df


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Upload sample data to Microsoft Fabric Lakehouse"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./sample_data",
        help="Directory containing CSV files to upload"
    )
    parser.add_argument(
        "--use-delta",
        action="store_true",
        help="Upload as Delta tables (requires deltalake package)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually uploading"
    )
    
    args = parser.parse_args()
    
    # Get environment variables - use names, not GUIDs
    workspace_name = os.environ.get("FABRIC_WORKSPACE_NAME")
    lakehouse_name = os.environ.get("FABRIC_LAKEHOUSE_NAME")
    
    if not workspace_name or not lakehouse_name:
        print("❌ Error: Required environment variables not set.")
        print()
        print("Please set the following environment variables:")
        print("  FABRIC_WORKSPACE_NAME  - Your Fabric workspace name")
        print("  FABRIC_LAKEHOUSE_NAME  - Your Lakehouse name")
        print()
        print("Example:")
        print('  $env:FABRIC_WORKSPACE_NAME="MyWorkspace"')
        print('  $env:FABRIC_LAKEHOUSE_NAME="LH_AIClaimsDemo"')
        print()
        print("Files will be uploaded to:")
        print(f"  https://onelake.dfs.fabric.microsoft.com/{{workspace_name}}/{{lakehouse_name}}.Lakehouse/Files/{CLAIMS_DATA_FOLDER}/")
        sys.exit(1)
    
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"❌ Error: Data directory not found: {data_dir}")
        print("Run 'python generate_sample_data.py' first to generate the data.")
        sys.exit(1)
    
    # Find CSV files
    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        print(f"❌ Error: No CSV files found in {data_dir}")
        sys.exit(1)
    
    print(f"🚀 Uploading data to Microsoft Fabric Lakehouse")
    print(f"   Workspace: {workspace_name}")
    print(f"   Lakehouse: {lakehouse_name}")
    print(f"   Target folder: Files/{CLAIMS_DATA_FOLDER}/")
    print(f"   Data directory: {data_dir.absolute()}")
    print(f"   Upload method: {'Delta' if args.use_delta and DELTA_AVAILABLE else 'Parquet'}")
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN - No files will be uploaded")
        print()
    
    # Initialize client
    if not args.dry_run:
        try:
            datalake_client = get_datalake_client()
            print("✅ Connected to OneLake")
        except Exception as e:
            print(f"❌ Failed to connect to OneLake: {e}")
            print()
            print("Make sure you're authenticated:")
            print("  az login")
            print()
            print("And have the required permissions on the Fabric workspace.")
            sys.exit(1)
    
    # Upload each CSV
    success_count = 0
    for csv_file in csv_files:
        table_name = csv_file.stem  # Filename without extension
        print(f"📤 Uploading {table_name}...")
        
        try:
            # Load and process CSV
            df = process_csv_file(csv_file, table_name)
            print(f"   Loaded {len(df)} rows, {len(df.columns)} columns")
            
            if args.dry_run:
                print(f"   Would upload to: Files/{CLAIMS_DATA_FOLDER}/{table_name}.parquet")
                success_count += 1
                continue
            
            # Upload
            if args.use_delta and DELTA_AVAILABLE:
                path = upload_as_delta(df, table_name, workspace_name, lakehouse_name)
            else:
                path = upload_to_onelake(
                    df, table_name, workspace_name, lakehouse_name, datalake_client
                )
            
            print(f"   ✅ Uploaded to: {path}")
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
    
    print()
    print("=" * 60)
    print(f"✅ Upload complete: {success_count}/{len(csv_files)} files")
    print("=" * 60)
    print()
    print("Next steps:")
    print("   1. Run 'python load_to_tables.py' to create Delta tables")
    print("      OR manually: Open Lakehouse > right-click folder > Load to Tables")
    print("   2. Open SQL Analytics Endpoint")
    print("   3. Create a Data Agent and select the tables")
    print("   4. Publish the Data Agent")
    print("   5. Create a connection in Azure AI Foundry")


if __name__ == "__main__":
    main()
