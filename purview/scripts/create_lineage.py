#!/usr/bin/env python3
"""
Create custom lineage in Microsoft Purview for Insurance Multi-Agent Application.

This script creates data lineage relationships covering the FULL data flow:

  Flow 1 — Claim Processing:
    Upload → Azure Storage → Content Understanding → AI Search (vectorized)
    → Orchestrator/Agents → Cosmos DB → Fabric Mirrored Tables

  Flow 2 — Enterprise Data:
    Excel → Lakehouse Files → Delta Tables → Semantic Model → Power BI
    Delta Tables → Fabric Data Agent (via IQ semantic layer)

  Flow 3 — Agent Orchestration:
    Supervisor → Specialist Agents (Claim Assessor, Policy Checker,
    Risk Analyst, Claims Data Analyst, Communication)
    → Agent Executions & Token Tracking → Cosmos DB → Fabric Mirrors

Usage:
    python create_lineage.py --purview-account pview-apfsipurviewdemo
    
Environment variables (can be set in .env file):
    PURVIEW_ACCOUNT - Purview account name
    FABRIC_WORKSPACE_ID - Fabric workspace ID
    FOUNDRY_PROJECT_NAME - Azure AI Foundry project ID
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, List

import requests
from azure.identity import DefaultAzureCredential

# Load environment variables from .env file if it exists
def load_env_file():
    """Load environment variables from .env file in the script directory."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_env_file()


class PurviewLineageManager:
    """Manage custom lineage in Microsoft Purview."""
    
    def __init__(self, purview_account: str, dry_run: bool = False):
        self.purview_account = purview_account
        self.base_url = f"https://{purview_account}.purview.azure.com"
        self.dry_run = dry_run
        self.headers = self._get_headers()
    
    def _get_headers(self) -> dict:
        """Get authentication headers for Purview API."""
        credential = DefaultAzureCredential()
        token = credential.get_token("https://purview.azure.net/.default")
        return {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
    
    def list_collections(self) -> List[dict]:
        """List all collections in the Purview account."""
        response = requests.get(
            f"{self.base_url}/account/collections?api-version=2019-11-01-preview",
            headers=self.headers
        )
        
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            print(f"Error listing collections: {response.status_code} - {response.text}")
            return []
    
    def create_type_definitions(self) -> bool:
        """Create custom type definitions for the application.
        
        Note: If types already exist with different supertypes, they cannot be 
        modified. You may need to delete existing entities first and recreate.
        """
        type_definitions = {
            "entityDefs": [
                {
                    "name": "azure_foundry_agent",
                    "description": "Azure AI Foundry Agent in the multi-agent system",
                    "superTypes": ["DataSet"],
                    "attributeDefs": [
                        {"name": "agentType", "typeName": "string", "isOptional": False},
                        {"name": "agentId", "typeName": "string", "isOptional": True},
                        {"name": "modelDeployment", "typeName": "string", "isOptional": True},
                        {"name": "toolsUsed", "typeName": "array<string>", "isOptional": True}
                    ]
                },
                {
                    "name": "fabric_data_agent",
                    "description": "Microsoft Fabric Data Agent powered by IQ",
                    "superTypes": ["DataSet"],
                    "attributeDefs": [
                        {"name": "projectName", "typeName": "string", "isOptional": True},
                        {"name": "lakehouseName", "typeName": "string", "isOptional": True},
                        {"name": "ontologyEntities", "typeName": "array<string>", "isOptional": True},
                        {"name": "agentInstructions", "typeName": "string", "isOptional": True}
                    ]
                },
                {
                    "name": "azure_ai_service",
                    "description": "Azure AI Service (Content Understanding)",
                    "superTypes": ["DataSet"],
                    "attributeDefs": [
                        {"name": "serviceType", "typeName": "string", "isOptional": False},
                        {"name": "endpoint", "typeName": "string", "isOptional": True},
                        {"name": "analyzerId", "typeName": "string", "isOptional": True}
                    ]
                },
                {
                    "name": "azure_ai_search_index",
                    "description": "Azure AI Search index (vectorized data store)",
                    "superTypes": ["DataSet"],
                    "attributeDefs": [
                        {"name": "searchServiceName", "typeName": "string", "isOptional": False},
                        {"name": "indexName", "typeName": "string", "isOptional": False},
                        {"name": "vectorizerType", "typeName": "string", "isOptional": True},
                        {"name": "embeddingModel", "typeName": "string", "isOptional": True}
                    ]
                }
            ]
        }
        
        if self.dry_run:
            print("  [DRY RUN] Would create custom type definitions")
            return True
        
        response = requests.post(
            f"{self.base_url}/catalog/api/atlas/v2/types/typedefs",
            headers=self.headers,
            json=type_definitions
        )
        
        if response.status_code in [200, 201]:
            print("  Created custom type definitions")
            return True
        elif response.status_code == 409:
            print("  Type definitions already exist (may have different supertypes - use --cleanup if lineage fails)")
            return True
        else:
            print(f"  Error creating type definitions: {response.status_code} - {response.text}")
            return False
    
    def create_entity(self, entity: dict, collection: str = None) -> Optional[str]:
        """Create an entity in Purview and return its GUID.
        
        Args:
            entity: The entity definition
            collection: Optional collection ID to place the entity in
        """
        if self.dry_run:
            collection_info = f" in collection '{collection}'" if collection else ""
            print(f"  [DRY RUN] Would create: {entity['attributes']['name']}{collection_info}")
            return f"dry-run-guid-{entity['attributes']['qualifiedName']}"
        
        # Build URL with collection as query parameter (per Purview API cookbook)
        url = f"{self.base_url}/datamap/api/atlas/v2/entity?api-version=2023-09-01"
        if collection:
            url += f"&collectionId={collection}"
        
        payload = {"entity": entity}
        
        response = requests.post(url, headers=self.headers, json=payload)
        
        if response.status_code in [200, 201]:
            result = response.json()
            guid = list(result.get("guidAssignments", {}).values())
            return guid[0] if guid else None
        else:
            print(f"  Error creating entity: {response.status_code} - {response.text}")
            return None
    
    def search_asset(self, search_term: str) -> Optional[str]:
        """Search for an asset by name and return its GUID."""
        if self.dry_run:
            return f"dry-run-guid-{search_term}"
        
        response = requests.post(
            f"{self.base_url}/catalog/api/search/query?api-version=2022-03-01-preview",
            headers=self.headers,
            json={"keywords": search_term, "limit": 5}
        )
        
        if response.status_code == 200:
            results = response.json().get("value", [])
            for result in results:
                if search_term.lower() in result.get("name", "").lower():
                    return result["id"]
        return None
    
    def get_entity_by_qualified_name(self, type_name: str, qualified_name: str) -> Optional[str]:
        """Get entity GUID by qualified name."""
        if self.dry_run:
            return f"dry-run-guid-{qualified_name}"
        
        response = requests.get(
            f"{self.base_url}/catalog/api/atlas/v2/entity/uniqueAttribute/type/{type_name}",
            headers=self.headers,
            params={"attr:qualifiedName": qualified_name}
        )
        
        if response.status_code == 200:
            return response.json().get("entity", {}).get("guid")
        return None
    
    def delete_entity(self, guid: str) -> bool:
        """Delete an entity by GUID."""
        if self.dry_run:
            print(f"  [DRY RUN] Would delete entity: {guid}")
            return True
        
        response = requests.delete(
            f"{self.base_url}/catalog/api/atlas/v2/entity/guid/{guid}",
            headers=self.headers
        )
        
        if response.status_code in [200, 204]:
            return True
        else:
            print(f"  Error deleting entity {guid}: {response.status_code} - {response.text}")
            return False
    
    def delete_type_definition(self, type_name: str) -> bool:
        """Delete a type definition."""
        if self.dry_run:
            print(f"  [DRY RUN] Would delete type: {type_name}")
            return True
        
        response = requests.delete(
            f"{self.base_url}/catalog/api/atlas/v2/types/typedef/name/{type_name}",
            headers=self.headers
        )
        
        if response.status_code in [200, 204]:
            print(f"  Deleted type: {type_name}")
            return True
        elif response.status_code == 404:
            return True  # Already doesn't exist
        else:
            print(f"  Error deleting type {type_name}: {response.status_code} - {response.text}")
            return False
    
    def create_process_lineage(
        self,
        name: str,
        qualified_name: str,
        description: str,
        input_guids: list,
        output_guids: list
    ) -> Optional[str]:
        """Create a process entity representing lineage."""
        # Filter out None values
        valid_inputs = [{"guid": guid} for guid in input_guids if guid]
        valid_outputs = [{"guid": guid} for guid in output_guids if guid]
        
        if not valid_inputs or not valid_outputs:
            print(f"  Skipping {name}: missing inputs or outputs")
            return None
        
        entity = {
            "typeName": "Process",
            "attributes": {
                "qualifiedName": qualified_name,
                "name": name,
                "description": description
            },
            "relationshipAttributes": {
                "inputs": valid_inputs,
                "outputs": valid_outputs
            }
        }
        return self.create_entity(entity)


def create_fabric_data_agent(manager: PurviewLineageManager, config: dict) -> Optional[str]:
    """Create Fabric Data Agent entity."""
    collection = config.get("collection")
    print(f"\nCreating Fabric Data Agent entity{' in collection: ' + collection if collection else ''}...")
    
    entity = {
        "typeName": "fabric_data_agent",
        "attributes": {
            "qualifiedName": "fabric-data-agent-claims-analyst@insurance-multi-agent",
            "name": "Claims Data Analyst (Fabric Data Agent)",
            "description": "Fabric Data Agent that queries Lakehouse via natural language using IQ",
            "projectName": config.get("project_name", ""),
            "lakehouseName": "LH_AIClaimsDemo",
            "ontologyEntities": ["ClaimEntity", "ClaimantEntity", "PolicyEntity", "FraudIndicator"],
            "agentInstructions": "You are a claims data analyst. Query the lakehouse to answer questions about claims history, claimant profiles, and fraud patterns."
        }
    }
    
    guid = manager.create_entity(entity, collection=collection)
    if guid:
        print(f"  Created: Claims Data Analyst (Fabric Data Agent)")
    return guid


def create_foundry_agent_entities(manager: PurviewLineageManager, config: dict) -> Dict[str, str]:
    """Create Azure AI Foundry Agent entities."""
    collection = config.get("collection")
    print(f"\nCreating Azure AI Foundry Agent entities{' in collection: ' + collection if collection else ''}...")
    
    agents = [
        {
            "name": "Supervisor Agent",
            "qualified_name": "foundry-supervisor-agent@insurance-multi-agent",
            "agent_type": "supervisor",
            "tools": ["handoff_to_claim_assessor", "handoff_to_policy_checker", "handoff_to_risk_analyst", "handoff_to_communication", "handoff_to_claims_data_analyst"],
            "description": "Orchestrates multi-agent workflow for claims processing"
        },
        {
            "name": "Claim Assessor Agent",
            "qualified_name": "foundry-claim-assessor-agent@insurance-multi-agent",
            "agent_type": "claim_assessor",
            "tools": ["process_claim_document", "content_understanding"],
            "description": "Analyzes claim documents using Azure AI Content Understanding"
        },
        {
            "name": "Policy Checker Agent",
            "qualified_name": "foundry-policy-checker-agent@insurance-multi-agent",
            "agent_type": "policy_checker",
            "tools": ["search_policies", "get_policy_details"],
            "description": "Verifies policy coverage and terms using AI Search"
        },
        {
            "name": "Risk Analyst Agent",
            "qualified_name": "foundry-risk-analyst-agent@insurance-multi-agent",
            "agent_type": "risk_analyst",
            "tools": ["calculate_risk_score", "check_fraud_indicators"],
            "description": "Calculates risk scores and identifies fraud patterns"
        },
        {
            "name": "Claims Data Analyst Agent",
            "qualified_name": "foundry-claims-data-analyst-agent@insurance-multi-agent",
            "agent_type": "claims_data_analyst",
            "tools": ["query_fabric_data_agent"],
            "description": "Queries historical claims data via Fabric Data Agent"
        },
        {
            "name": "Communication Agent",
            "qualified_name": "foundry-communication-agent@insurance-multi-agent",
            "agent_type": "communication",
            "tools": ["generate_letter", "send_notification"],
            "description": "Generates customer communications and notifications"
        }
    ]
    
    agent_guids = {}
    for agent in agents:
        entity = {
            "typeName": "azure_foundry_agent",
            "attributes": {
                "qualifiedName": agent["qualified_name"],
                "name": agent["name"],
                "description": agent["description"],
                "agentType": agent["agent_type"],
                "agentId": config.get(f"{agent['agent_type']}_agent_id", ""),
                "modelDeployment": "gpt-4o",
                "toolsUsed": agent["tools"]
            }
        }
        guid = manager.create_entity(entity, collection=collection)
        if guid:
            agent_guids[agent["agent_type"]] = guid
            print(f"  Created: {agent['name']}")
    
    return agent_guids


def create_ai_service_entities(manager: PurviewLineageManager, config: dict) -> Dict[str, str]:
    """Create Azure AI Service entities."""
    collection = config.get("collection")
    print(f"\nCreating Azure AI Service entities{' in collection: ' + collection if collection else ''}...")
    
    services = [
        {
            "name": "Content Understanding Analyzer",
            "qualified_name": "azure-content-understanding@insurance-multi-agent",
            "service_type": "content_understanding",
            "description": "Extracts structured data from claim documents"
        }
    ]
    
    service_guids = {}
    for service in services:
        entity = {
            "typeName": "azure_ai_service",
            "attributes": {
                "qualifiedName": service["qualified_name"],
                "name": service["name"],
                "description": service["description"],
                "serviceType": service["service_type"]
            }
        }
        guid = manager.create_entity(entity, collection=collection)
        if guid:
            service_guids[service["service_type"]] = guid
            print(f"  Created: {service['name']}")
    
    return service_guids


def create_ai_search_entity(manager: PurviewLineageManager, config: dict) -> Optional[str]:
    """Create Azure AI Search index entity for vectorized claims/policy data."""
    collection = config.get("collection")
    print(f"\nCreating Azure AI Search entity{' in collection: ' + collection if collection else ''}...")

    entity = {
        "typeName": "azure_ai_search_index",
        "attributes": {
            "qualifiedName": "azure-ai-search-policies-index@insurance-multi-agent",
            "name": "Policies Search Index (AI Search)",
            "description": "Vectorized policy and claims documents used by Policy Checker and agents via Azure AI Search",
            "searchServiceName": config.get("search_service_name", ""),
            "indexName": "policies-index",
            "vectorizerType": "Azure OpenAI",
            "embeddingModel": "text-embedding-ada-002"
        }
    }

    guid = manager.create_entity(entity, collection=collection)
    if guid:
        print(f"  Created: Policies Search Index (AI Search)")
    return guid


def find_semantic_model_assets(manager: PurviewLineageManager) -> Dict[str, str]:
    """Find Fabric Semantic Model assets (auto-discovered by Fabric scan)."""
    print("\nSearching for Fabric Semantic Model assets...")

    asset_guids = {}
    # Search for semantic models that Purview discovered via Fabric scan
    for search_term in ["Claims", "Semantic Model", "insurance"]:
        guid = manager.search_asset(search_term)
        if guid:
            asset_guids["semantic_model"] = guid
            print(f"  Found Semantic Model via search: {search_term}")
            break

    if not asset_guids:
        print("  Not found via scan - will create placeholder")
    return asset_guids


def find_powerbi_report_assets(manager: PurviewLineageManager) -> Dict[str, str]:
    """Find Power BI report assets (auto-discovered by Fabric scan)."""
    print("\nSearching for Power BI Report assets...")

    asset_guids = {}
    for search_term in ["Claims Dashboard", "Power BI", "Claims Report"]:
        guid = manager.search_asset(search_term)
        if guid:
            asset_guids["powerbi_report"] = guid
            print(f"  Found Power BI Report via search: {search_term}")
            break

    if not asset_guids:
        print("  Not found via scan - will create placeholder")
    return asset_guids


def find_cosmos_mirrored_tables(manager: PurviewLineageManager) -> Dict[str, str]:
    """Find Fabric mirrored Cosmos DB tables (created by Cosmos DB mirroring)."""
    print("\nSearching for Cosmos DB mirrored tables in Fabric...")

    tables = [
        "mirrored_agent_executions",
        "mirrored_token_tracking",
        "mirrored_evaluations"
    ]

    asset_guids = {}
    for table in tables:
        guid = manager.search_asset(table)
        if guid:
            asset_guids[table] = guid
            print(f"  Found: {table}")
        else:
            # Also search without prefix
            short_name = table.replace("mirrored_", "")
            guid = manager.search_asset(short_name)
            if guid:
                asset_guids[table] = guid
                print(f"  Found (via short name): {short_name}")
            else:
                print(f"  Not found: {table}")

    return asset_guids


def find_storage_assets(manager: PurviewLineageManager) -> Dict[str, str]:
    """Find Azure Storage container/folder GUIDs from stapfsidemoinsurance storage account."""
    print("\nSearching for Azure Storage assets...")
    
    # Use qualified name lookup for precise matching
    # Qualified name format: https://<account>.blob.core.windows.net/<container>
    storage_account = "stapfsidemoinsurance"
    base_url = f"https://{storage_account}.blob.core.windows.net"
    
    assets = [
        ("insurance_documents", "azure_blob_container", f"{base_url}/insurance-documents"),
    ]
    
    asset_guids = {}
    for key, type_name, qualified_name in assets:
        guid = manager.get_entity_by_qualified_name(type_name, qualified_name)
        if guid:
            asset_guids[key] = guid
            print(f"  Found: {qualified_name}")
        else:
            # Fallback to search by name
            guid = manager.search_asset("insurance-documents")
            if guid:
                asset_guids[key] = guid
                print(f"  Found via search: insurance-documents")
            else:
                print(f"  Not found: {qualified_name}")
    
    return asset_guids


def find_lakehouse_assets(manager: PurviewLineageManager) -> Dict[str, str]:
    """Find Fabric Lakehouse table GUIDs."""
    print("\nSearching for Lakehouse assets...")
    
    tables = [
        "claims_history",
        "claimant_profiles", 
        "fraud_indicators",
        "policy_claims_summary",
        "regional_statistics"
    ]
    
    asset_guids = {}
    for table in tables:
        guid = manager.search_asset(table)
        if guid:
            asset_guids[table] = guid
            print(f"  Found: {table}")
        else:
            print(f"  Not found: {table}")
    
    return asset_guids


def find_cosmos_assets(manager: PurviewLineageManager) -> Dict[str, str]:
    """Find Cosmos DB collection GUIDs from insurance-agents database."""
    print("\nSearching for Cosmos DB assets (insurance-agents database)...")
    
    collections = [
        "agent-definitions",
        "agent-executions",
        "evaluations",
        "token-usage"
    ]
    
    asset_guids = {}
    for collection in collections:
        guid = manager.search_asset(collection)
        if guid:
            asset_guids[collection] = guid
            print(f"  Found: {collection}")
        else:
            print(f"  Not found: {collection}")
    
    return asset_guids


def create_data_ingestion_lineage(
    manager: PurviewLineageManager,
    storage_guids: Dict[str, str],
    lakehouse_guids: Dict[str, str],
    cosmos_guids: Dict[str, str],
    cosmos_mirrored_guids: Dict[str, str],
    ai_search_guid: Optional[str],
    ai_service_guids: Dict[str, str]
):
    """Create lineage for all data ingestion paths.
    
    Covers:
      - Storage (docs) → Content Understanding → AI Search (vectorized)
      - Storage (docs) → Lakehouse tables
      - Excel → Lakehouse Files → Delta Tables (modeled as Storage → Lakehouse)
      - Cosmos DB → Fabric Mirrored Delta Tables
    """
    print("\nCreating data ingestion lineage...")
    
    # Storage (insurance-documents container) → Lakehouse
    if storage_guids.get("insurance_documents"):
        manager.create_process_lineage(
            name="Insurance Documents Ingestion",
            qualified_name="lineage-storage-to-lakehouse-claims@insurance",
            description="Fabric Pipeline ingests claim documents from Azure Storage into Lakehouse",
            input_guids=[storage_guids.get("insurance_documents")],
            output_guids=[
                lakehouse_guids.get("claims_history"),
                lakehouse_guids.get("claimant_profiles"),
                lakehouse_guids.get("policy_claims_summary")
            ]
        )
        print("  Created: Storage (insurance-documents) → Lakehouse")

    # Excel → Lakehouse (enterprise data ingestion path)
    # Excel files are uploaded to Lakehouse Files section, then converted to Delta Tables
    if lakehouse_guids:
        manager.create_process_lineage(
            name="Enterprise Data Ingestion (Excel to Lakehouse)",
            qualified_name="lineage-excel-to-lakehouse@insurance",
            description="Excel spreadsheets uploaded to Lakehouse Files section and converted to Delta Tables",
            input_guids=[storage_guids.get("insurance_documents")] if storage_guids.get("insurance_documents") else [],
            output_guids=[
                lakehouse_guids.get("claims_history"),
                lakehouse_guids.get("claimant_profiles"),
                lakehouse_guids.get("fraud_indicators"),
                lakehouse_guids.get("policy_claims_summary"),
                lakehouse_guids.get("regional_statistics")
            ]
        )
        print("  Created: Excel/Files → Lakehouse Delta Tables")

    # Storage → Content Understanding → AI Search (vectorization pipeline)
    if ai_search_guid and storage_guids.get("insurance_documents"):
        inputs = [storage_guids["insurance_documents"]]
        if ai_service_guids.get("content_understanding"):
            inputs.append(ai_service_guids["content_understanding"])
        
        manager.create_process_lineage(
            name="Document Vectorization Pipeline",
            qualified_name="lineage-storage-to-ai-search@insurance",
            description="Claim and policy documents processed by Content Understanding, vectorized and indexed in Azure AI Search",
            input_guids=inputs,
            output_guids=[ai_search_guid]
        )
        print("  Created: Storage + Content Understanding → AI Search (vectorized)")

    # Cosmos DB → Fabric Mirrored Tables (near real-time mirroring)
    cosmos_mirror_pairs = [
        ("agent-executions", "mirrored_agent_executions"),
        ("token-usage", "mirrored_token_tracking"),
        ("evaluations", "mirrored_evaluations"),
    ]
    mirror_inputs = []
    mirror_outputs = []
    for cosmos_key, mirror_key in cosmos_mirror_pairs:
        if cosmos_guids.get(cosmos_key):
            mirror_inputs.append(cosmos_guids[cosmos_key])
        if cosmos_mirrored_guids.get(mirror_key):
            mirror_outputs.append(cosmos_mirrored_guids[mirror_key])

    if mirror_inputs and mirror_outputs:
        manager.create_process_lineage(
            name="Cosmos DB Mirroring to Fabric",
            qualified_name="lineage-cosmos-to-fabric-mirror@insurance",
            description="Near real-time Cosmos DB mirroring replicates agent-executions, token-tracking, and evaluations to Fabric Delta Tables",
            input_guids=mirror_inputs,
            output_guids=mirror_outputs
        )
        print("  Created: Cosmos DB → Fabric Mirrored Tables")


def create_fabric_agent_lineage(
    manager: PurviewLineageManager,
    lakehouse_guids: Dict[str, str],
    fabric_agent_guid: str
):
    """Create lineage from Lakehouse to Fabric Data Agent."""
    print("\nCreating Fabric Data Agent lineage...")
    
    if not fabric_agent_guid:
        print("  Skipping: Fabric Data Agent not created")
        return
    
    # Lakehouse → Fabric Data Agent
    lakehouse_inputs = [
        lakehouse_guids.get("claims_history"),
        lakehouse_guids.get("claimant_profiles"),
        lakehouse_guids.get("fraud_indicators"),
        lakehouse_guids.get("policy_claims_summary")
    ]
    
    manager.create_process_lineage(
        name="Lakehouse to Fabric Data Agent",
        qualified_name="lineage-lakehouse-to-fabric-agent@insurance",
        description="Fabric Data Agent queries Lakehouse tables via IQ semantic layer",
        input_guids=lakehouse_inputs,
        output_guids=[fabric_agent_guid]
    )
    print("  Created: Lakehouse Tables → Fabric Data Agent")


def create_foundry_agent_lineage(
    manager: PurviewLineageManager,
    fabric_agent_guid: str,
    foundry_agent_guids: Dict[str, str],
    ai_service_guids: Dict[str, str],
    ai_search_guid: Optional[str],
    storage_guids: Dict[str, str],
    cosmos_guids: Dict[str, str],
    lakehouse_guids: Dict[str, str]
):
    """Create lineage for Azure AI Foundry agents."""
    print("\nCreating Foundry Agent lineage...")
    
    # Fabric Data Agent → Foundry Claims Data Analyst
    if fabric_agent_guid and foundry_agent_guids.get("claims_data_analyst"):
        manager.create_process_lineage(
            name="Fabric Data Agent to Foundry Agent",
            qualified_name="lineage-fabric-agent-to-foundry@insurance",
            description="Foundry Claims Data Analyst queries Fabric Data Agent for historical claims data",
            input_guids=[fabric_agent_guid],
            output_guids=[foundry_agent_guids["claims_data_analyst"]]
        )
        print("  Created: Fabric Data Agent → Foundry Claims Data Analyst")
    
    # Content Understanding + Storage → Claim Assessor
    if foundry_agent_guids.get("claim_assessor"):
        inputs = []
        if storage_guids.get("insurance_documents"):
            inputs.append(storage_guids["insurance_documents"])
        if ai_service_guids.get("content_understanding"):
            inputs.append(ai_service_guids["content_understanding"])
        
        if inputs:
            manager.create_process_lineage(
                name="Content Understanding to Claim Assessor",
                qualified_name="lineage-content-understanding-to-assessor@insurance",
                description="Claim Assessor uses Content Understanding to extract data from claim documents",
                input_guids=inputs,
                output_guids=[foundry_agent_guids["claim_assessor"]]
            )
            print("  Created: Content Understanding + Storage → Claim Assessor")
    
    # NOTE: fraud_indicators does NOT connect directly to Risk Analyst.
    # Fraud data is only accessed via the Fabric Data Agent → Claims Data Analyst path.
    # The Risk Analyst agent uses its own tools (calculate_risk_score, check_fraud_indicators)
    # which operate on data passed through the supervisor orchestration, not Lakehouse directly.
    
    # AI Search (vectorized data) → Policy Checker
    # This replaces the old direct Storage → Policy Checker link
    if foundry_agent_guids.get("policy_checker"):
        inputs = []
        if ai_search_guid:
            inputs.append(ai_search_guid)
        elif storage_guids.get("insurance_documents"):
            # Fallback if AI Search entity wasn't created
            inputs.append(storage_guids["insurance_documents"])

        if inputs:
            manager.create_process_lineage(
                name="AI Search to Policy Checker",
                qualified_name="lineage-ai-search-to-policy-checker@insurance",
                description="Policy Checker queries vectorized policy documents via Azure AI Search",
                input_guids=inputs,
                output_guids=[foundry_agent_guids["policy_checker"]]
            )
            print("  Created: AI Search → Policy Checker")
    
    # Specialist Agents → Supervisor
    specialist_agents = [
        foundry_agent_guids.get("claim_assessor"),
        foundry_agent_guids.get("policy_checker"),
        foundry_agent_guids.get("risk_analyst"),
        foundry_agent_guids.get("claims_data_analyst"),
        foundry_agent_guids.get("communication")
    ]
    
    if foundry_agent_guids.get("supervisor") and any(specialist_agents):
        manager.create_process_lineage(
            name="Specialist Agents to Supervisor",
            qualified_name="lineage-agents-to-supervisor@insurance",
            description="Supervisor orchestrates all specialist Foundry agents",
            input_guids=specialist_agents,
            output_guids=[foundry_agent_guids["supervisor"]]
        )
        print("  Created: Specialist Agents → Supervisor")
    
    # Supervisor → Cosmos DB (agent-executions)
    if foundry_agent_guids.get("supervisor") and cosmos_guids.get("agent-executions"):
        manager.create_process_lineage(
            name="Supervisor to Cosmos DB (Executions)",
            qualified_name="lineage-supervisor-to-cosmos@insurance",
            description="Agent execution results stored in Cosmos DB",
            input_guids=[foundry_agent_guids["supervisor"]],
            output_guids=[cosmos_guids["agent-executions"]]
        )
        print("  Created: Supervisor → Cosmos DB (agent-executions)")

    # Supervisor → Cosmos DB (token-tracking)
    if foundry_agent_guids.get("supervisor") and cosmos_guids.get("token-usage"):
        manager.create_process_lineage(
            name="Supervisor to Cosmos DB (Token Tracking)",
            qualified_name="lineage-supervisor-to-cosmos-tokens@insurance",
            description="Token usage and scale metrics written to Cosmos DB by agent orchestrator",
            input_guids=[foundry_agent_guids["supervisor"]],
            output_guids=[cosmos_guids["token-usage"]]
        )
        print("  Created: Supervisor → Cosmos DB (token-tracking)")
    
    # Agent Executions → Evaluations
    if cosmos_guids.get("agent-executions") and cosmos_guids.get("evaluations"):
        manager.create_process_lineage(
            name="Execution Evaluation Pipeline",
            qualified_name="lineage-executions-to-evaluations@insurance",
            description="Agent executions are evaluated for quality metrics using Azure AI Evaluation",
            input_guids=[cosmos_guids["agent-executions"]],
            output_guids=[cosmos_guids["evaluations"]]
        )
        print("  Created: agent-executions → evaluations")


def create_fabric_analytics_lineage(
    manager: PurviewLineageManager,
    lakehouse_guids: Dict[str, str],
    semantic_model_guids: Dict[str, str],
    powerbi_guids: Dict[str, str]
):
    """Create lineage for Fabric analytics chain: Lakehouse → Semantic Model → Power BI.
    
    These assets are typically auto-discovered by Purview's Fabric scan.
    This function creates the Process entities linking them if not already connected.
    """
    print("\nCreating Fabric analytics lineage (Lakehouse → Semantic Model → Power BI)...")

    # Lakehouse → Semantic Model
    if lakehouse_guids and semantic_model_guids.get("semantic_model"):
        lakehouse_inputs = [
            lakehouse_guids.get("claims_history"),
            lakehouse_guids.get("claimant_profiles"),
            lakehouse_guids.get("fraud_indicators"),
            lakehouse_guids.get("policy_claims_summary"),
            lakehouse_guids.get("regional_statistics")
        ]
        manager.create_process_lineage(
            name="Lakehouse to Semantic Model",
            qualified_name="lineage-lakehouse-to-semantic-model@insurance",
            description="Lakehouse Delta Tables feed the Fabric Semantic Model for claims analytics",
            input_guids=lakehouse_inputs,
            output_guids=[semantic_model_guids["semantic_model"]]
        )
        print("  Created: Lakehouse Tables → Semantic Model")
    else:
        print("  Skipped: Semantic Model not found in Purview catalog (run Fabric scan first)")

    # Semantic Model → Power BI Report
    if semantic_model_guids.get("semantic_model") and powerbi_guids.get("powerbi_report"):
        manager.create_process_lineage(
            name="Semantic Model to Power BI Report",
            qualified_name="lineage-semantic-model-to-powerbi@insurance",
            description="Power BI Claims Dashboard built on top of Fabric Semantic Model",
            input_guids=[semantic_model_guids["semantic_model"]],
            output_guids=[powerbi_guids["powerbi_report"]]
        )
        print("  Created: Semantic Model → Power BI Report")
    else:
        print("  Skipped: Semantic Model or Power BI Report not found (run Fabric scan first)")


def main():
    parser = argparse.ArgumentParser(
        description="Create custom lineage in Microsoft Purview for Insurance Multi-Agent Application"
    )
    parser.add_argument(
        "--purview-account",
        default=os.environ.get("PURVIEW_ACCOUNT", os.environ.get("purview_account", "")),
        help="Name of the Purview account (or set PURVIEW_ACCOUNT env var)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without making changes"
    )
    parser.add_argument(
        "--list-collections",
        action="store_true",
        help="List all collections and their IDs, then exit"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete previously created custom entities before recreating"
    )
    parser.add_argument(
        "--reset-types",
        action="store_true",
        help="Delete and recreate custom type definitions (use if types have wrong supertypes)"
    )
    parser.add_argument(
        "--project-name",
        default=os.environ.get("FABRIC_PROJECT_NAME", ""),
        help="Fabric project name (or set FABRIC_PROJECT_NAME env var)"
    )
    parser.add_argument(
        "--collection",
        default=os.environ.get("PURVIEW_COLLECTION", ""),
        help="Purview collection name for agent entities (or set PURVIEW_COLLECTION env var)"
    )
    parser.add_argument(
        "--search-service-name",
        default=os.environ.get("AZURE_SEARCH_SERVICE_NAME", ""),
        help="Azure AI Search service name (or set AZURE_SEARCH_SERVICE_NAME env var)"
    )
    args = parser.parse_args()
    
    # Validate required arguments
    if not args.purview_account:
        parser.error("--purview-account is required (or set PURVIEW_ACCOUNT in .env)")
    
    # Handle --list-collections
    if args.list_collections:
        print(f"Listing collections for account: {args.purview_account}")
        print(f"{'='*70}")
        manager = PurviewLineageManager(args.purview_account, dry_run=False)
        collections = manager.list_collections()
        if collections:
            print(f"\n{'Collection ID':<30} {'Friendly Name':<40}")
            print(f"{'-'*30} {'-'*40}")
            for coll in collections:
                coll_id = coll.get("name", "")
                friendly = coll.get("friendlyName", "")
                print(f"{coll_id:<30} {friendly:<40}")
            print(f"\nUse the Collection ID (left column) in your .env file as PURVIEW_COLLECTION")
        else:
            print("No collections found or error occurred.")
        sys.exit(0)
    
    config = {
        "project_name": args.project_name,
        "collection": args.collection,
        "search_service_name": args.search_service_name
    }
    
    print(f"Purview Lineage Creation for Insurance Multi-Agent Application")
    print(f"{'='*70}")
    print(f"Account: {args.purview_account}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    if args.collection:
        print(f"Collection: {args.collection}")
    if args.cleanup:
        print(f"Cleanup: Enabled - will delete existing custom entities first")
    if args.reset_types:
        print(f"Reset Types: Enabled - will delete and recreate type definitions")
    
    try:
        manager = PurviewLineageManager(args.purview_account, args.dry_run)
        
        # Step 0: Cleanup if requested
        if args.cleanup:
            print("\nStep 0: Cleaning up existing custom entities...")
            cleanup_entities = [
                ("fabric_data_agent", "fabric-data-agent-claims-analyst@insurance-multi-agent"),
                ("azure_foundry_agent", "foundry-supervisor-agent@insurance-multi-agent"),
                ("azure_foundry_agent", "foundry-claim-assessor-agent@insurance-multi-agent"),
                ("azure_foundry_agent", "foundry-policy-checker-agent@insurance-multi-agent"),
                ("azure_foundry_agent", "foundry-risk-analyst-agent@insurance-multi-agent"),
                ("azure_foundry_agent", "foundry-claims-data-analyst-agent@insurance-multi-agent"),
                ("azure_foundry_agent", "foundry-communication-agent@insurance-multi-agent"),
                ("azure_ai_service", "azure-content-understanding@insurance-multi-agent"),
                ("azure_ai_service", "azure-document-intelligence@insurance-multi-agent"),
                ("azure_ai_search_index", "azure-ai-search-policies-index@insurance-multi-agent"),
            ]
            # Also clean up old/stale Process entities from previous runs
            cleanup_processes = [
                "lineage-fraud-to-risk-analyst@insurance",
                "lineage-policies-to-policy-checker@insurance",
                "lineage-cosmos-to-lakehouse@insurance",
            ]
            for qualified_name in cleanup_processes:
                guid = manager.get_entity_by_qualified_name("Process", qualified_name)
                if guid and not guid.startswith("dry-run"):
                    manager.delete_entity(guid)
                    print(f"  Deleted process: {qualified_name}")

            for type_name, qualified_name in cleanup_entities:
                guid = manager.get_entity_by_qualified_name(type_name, qualified_name)
                if guid and not guid.startswith("dry-run"):
                    manager.delete_entity(guid)
                    print(f"  Deleted: {qualified_name}")
            
            # Also delete type definitions if --reset-types is specified
            if args.reset_types:
                print("\n  Deleting type definitions...")
                for type_name in ["fabric_data_agent", "azure_foundry_agent", "azure_ai_service", "azure_ai_search_index"]:
                    manager.delete_type_definition(type_name)
        
        # Step 1: Create custom type definitions
        print("\nStep 1: Creating custom type definitions...")
        manager.create_type_definitions()
        
        # Step 2: Find existing assets (scanned by Purview)
        storage_guids = find_storage_assets(manager)
        lakehouse_guids = find_lakehouse_assets(manager)
        cosmos_guids = find_cosmos_assets(manager)
        cosmos_mirrored_guids = find_cosmos_mirrored_tables(manager)
        semantic_model_guids = find_semantic_model_assets(manager)
        powerbi_guids = find_powerbi_report_assets(manager)
        
        # Step 3: Create custom entities (not auto-discovered)
        fabric_agent_guid = create_fabric_data_agent(manager, config)
        foundry_agent_guids = create_foundry_agent_entities(manager, config)
        ai_service_guids = create_ai_service_entities(manager, config)
        ai_search_guid = create_ai_search_entity(manager, config)
        
        # Step 4: Create data ingestion lineage
        #   Storage → Lakehouse, Excel → Lakehouse, Storage → AI Search, Cosmos → Mirrors
        create_data_ingestion_lineage(
            manager, storage_guids, lakehouse_guids, cosmos_guids,
            cosmos_mirrored_guids, ai_search_guid, ai_service_guids
        )
        
        # Step 5: Create Fabric analytics lineage
        #   Lakehouse → Semantic Model → Power BI
        create_fabric_analytics_lineage(
            manager, lakehouse_guids, semantic_model_guids, powerbi_guids
        )
        
        # Step 6: Create Fabric Data Agent lineage (Lakehouse → Fabric Agent)
        create_fabric_agent_lineage(manager, lakehouse_guids, fabric_agent_guid)
        
        # Step 7: Create Foundry Agent lineage (Fabric Agent → Foundry → Cosmos)
        create_foundry_agent_lineage(
            manager, fabric_agent_guid, foundry_agent_guids,
            ai_service_guids, ai_search_guid, storage_guids, cosmos_guids, lakehouse_guids
        )
        
        # Summary
        print(f"\n{'='*70}")
        print("Lineage creation complete!")
        print(f"  Storage assets found: {len(storage_guids)}")
        print(f"  Lakehouse assets found: {len(lakehouse_guids)}")
        print(f"  Cosmos assets found: {len(cosmos_guids)}")
        print(f"  Cosmos mirrored tables found: {len(cosmos_mirrored_guids)}")
        print(f"  Semantic Model found: {'Yes' if semantic_model_guids else 'No'}")
        print(f"  Power BI Report found: {'Yes' if powerbi_guids else 'No'}")
        print(f"  Fabric Data Agent created: {'Yes' if fabric_agent_guid else 'No'}")
        print(f"  Foundry Agents created: {len(foundry_agent_guids)}")
        print(f"  AI Services created: {len(ai_service_guids)}")
        print(f"  AI Search Index created: {'Yes' if ai_search_guid else 'No'}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
