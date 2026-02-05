#!/usr/bin/env python3
"""
Verify lineage relationships exist in Microsoft Purview.

Usage:
    python verify_lineage.py --purview-account <account-name>
"""

import argparse
import sys
from typing import Optional

import requests
from azure.identity import DefaultAzureCredential


class LineageVerifier:
    """Verify lineage in Microsoft Purview."""
    
    def __init__(self, purview_account: str):
        self.purview_account = purview_account
        self.base_url = f"https://{purview_account}.purview.azure.com"
        self.headers = self._get_headers()
    
    def _get_headers(self) -> dict:
        """Get authentication headers for Purview API."""
        credential = DefaultAzureCredential()
        token = credential.get_token("https://purview.azure.net/.default")
        return {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
    
    def search_asset(self, search_term: str) -> Optional[dict]:
        """Search for an asset by name."""
        response = requests.post(
            f"{self.base_url}/catalog/api/search/query?api-version=2022-03-01-preview",
            headers=self.headers,
            json={"keywords": search_term, "limit": 5}
        )
        
        if response.status_code == 200:
            results = response.json().get("value", [])
            for result in results:
                if search_term.lower() in result.get("name", "").lower():
                    return {
                        "guid": result["id"],
                        "name": result.get("name"),
                        "type": result.get("entityType")
                    }
        return None
    
    def get_lineage(self, guid: str, direction: str = "BOTH", depth: int = 3) -> dict:
        """Get lineage for an entity."""
        response = requests.get(
            f"{self.base_url}/catalog/api/atlas/v2/lineage/{guid}",
            headers=self.headers,
            params={"direction": direction, "depth": depth}
        )
        
        if response.status_code == 200:
            return response.json()
        return {}
    
    def verify_asset_lineage(self, asset_name: str) -> dict:
        """Verify lineage exists for an asset."""
        result = {
            "asset": asset_name,
            "found": False,
            "has_upstream": False,
            "has_downstream": False,
            "upstream_count": 0,
            "downstream_count": 0,
            "details": {}
        }
        
        asset = self.search_asset(asset_name)
        if not asset:
            return result
        
        result["found"] = True
        result["details"]["guid"] = asset["guid"]
        result["details"]["type"] = asset["type"]
        
        lineage = self.get_lineage(asset["guid"])
        
        if lineage:
            relations = lineage.get("relations", [])
            entity_map = lineage.get("guidEntityMap", {})
            
            upstream = [r for r in relations if r.get("toEntityId") == asset["guid"]]
            downstream = [r for r in relations if r.get("fromEntityId") == asset["guid"]]
            
            result["has_upstream"] = len(upstream) > 0
            result["has_downstream"] = len(downstream) > 0
            result["upstream_count"] = len(upstream)
            result["downstream_count"] = len(downstream)
            
            # Get names of connected entities
            result["details"]["upstream_entities"] = []
            result["details"]["downstream_entities"] = []
            
            for rel in upstream:
                from_guid = rel.get("fromEntityId")
                if from_guid in entity_map:
                    result["details"]["upstream_entities"].append(
                        entity_map[from_guid].get("attributes", {}).get("name", from_guid)
                    )
            
            for rel in downstream:
                to_guid = rel.get("toEntityId")
                if to_guid in entity_map:
                    result["details"]["downstream_entities"].append(
                        entity_map[to_guid].get("attributes", {}).get("name", to_guid)
                    )
        
        return result


def main():
    parser = argparse.ArgumentParser(description="Verify lineage in Microsoft Purview")
    parser.add_argument("--purview-account", required=True, help="Purview account name")
    args = parser.parse_args()
    
    print(f"Lineage Verification for Insurance Multi-Agent Application")
    print(f"{'='*60}")
    print(f"Account: {args.purview_account}")
    
    try:
        verifier = LineageVerifier(args.purview_account)
        
        # Assets to verify
        assets = [
            # Lakehouse tables
            "claims_history",
            "claimant_profiles",
            "fraud_indicators",
            "policy_claims_summary",
            "regional_statistics",
            # Cosmos collections
            "agent-executions",
            "evaluations",
            # Agents
            "Supervisor Agent",
            "Claim Assessor Agent",
            "Claims Data Analyst Agent",
            "Risk Analyst Agent"
        ]
        
        print(f"\nVerifying {len(assets)} assets...\n")
        
        all_results = []
        for asset in assets:
            result = verifier.verify_asset_lineage(asset)
            all_results.append(result)
            
            status = "FOUND" if result["found"] else "NOT FOUND"
            lineage_status = ""
            if result["found"]:
                lineage_status = f" | Upstream: {result['upstream_count']} | Downstream: {result['downstream_count']}"
            
            print(f"  [{status}] {asset}{lineage_status}")
            
            if result["details"].get("upstream_entities"):
                for entity in result["details"]["upstream_entities"]:
                    print(f"           ^ {entity}")
            if result["details"].get("downstream_entities"):
                for entity in result["details"]["downstream_entities"]:
                    print(f"           v {entity}")
        
        # Summary
        found_count = sum(1 for r in all_results if r["found"])
        with_lineage = sum(1 for r in all_results if r["has_upstream"] or r["has_downstream"])
        
        print(f"\n{'='*60}")
        print(f"Summary:")
        print(f"  Assets found: {found_count}/{len(assets)}")
        print(f"  Assets with lineage: {with_lineage}")
        
        if found_count < len(assets):
            print(f"\nMissing assets may need to be scanned or created.")
            print(f"Run 'python create_lineage.py' to create agent entities and lineage.")
        
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
