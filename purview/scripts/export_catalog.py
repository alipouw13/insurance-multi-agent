#!/usr/bin/env python3
"""
Export Purview Unified Catalog to JSON for backup and analysis.

Usage:
    python export_catalog.py --purview-account <account-name> --output catalog_export.json
"""

import argparse
import json
import sys
from datetime import datetime
from typing import List, Optional

import requests
from azure.identity import DefaultAzureCredential


class CatalogExporter:
    """Export Purview catalog assets."""
    
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
    
    def search_all_assets(self, keywords: str = "*", limit: int = 1000) -> List[dict]:
        """Search for all assets matching criteria."""
        all_results = []
        offset = 0
        page_size = 100
        
        while offset < limit:
            response = requests.post(
                f"{self.base_url}/catalog/api/search/query?api-version=2022-03-01-preview",
                headers=self.headers,
                json={
                    "keywords": keywords,
                    "limit": min(page_size, limit - offset),
                    "offset": offset
                }
            )
            
            if response.status_code != 200:
                break
            
            results = response.json().get("value", [])
            if not results:
                break
            
            all_results.extend(results)
            offset += len(results)
            
            if len(results) < page_size:
                break
        
        return all_results
    
    def get_entity_details(self, guid: str) -> Optional[dict]:
        """Get full entity details."""
        response = requests.get(
            f"{self.base_url}/catalog/api/atlas/v2/entity/guid/{guid}",
            headers=self.headers
        )
        
        if response.status_code == 200:
            return response.json().get("entity")
        return None
    
    def get_lineage(self, guid: str) -> dict:
        """Get lineage for an entity."""
        response = requests.get(
            f"{self.base_url}/catalog/api/atlas/v2/lineage/{guid}",
            headers=self.headers,
            params={"direction": "BOTH", "depth": 3}
        )
        
        if response.status_code == 200:
            return response.json()
        return {}
    
    def export_catalog(self, filter_keywords: Optional[str] = None, include_lineage: bool = True) -> dict:
        """Export full catalog with optional lineage."""
        export_data = {
            "export_metadata": {
                "purview_account": self.purview_account,
                "export_date": datetime.utcnow().isoformat(),
                "include_lineage": include_lineage
            },
            "assets": [],
            "lineage_relationships": []
        }
        
        # Search for assets
        keywords = filter_keywords if filter_keywords else "*"
        assets = self.search_all_assets(keywords)
        
        print(f"Found {len(assets)} assets")
        
        # Get details for each asset
        for i, asset in enumerate(assets):
            guid = asset.get("id")
            print(f"  Processing {i+1}/{len(assets)}: {asset.get('name', 'Unknown')}")
            
            details = self.get_entity_details(guid)
            if details:
                asset_export = {
                    "guid": guid,
                    "name": details.get("attributes", {}).get("name"),
                    "qualified_name": details.get("attributes", {}).get("qualifiedName"),
                    "type": details.get("typeName"),
                    "attributes": details.get("attributes", {}),
                    "classifications": [c.get("typeName") for c in details.get("classifications", [])],
                    "labels": details.get("labels", [])
                }
                export_data["assets"].append(asset_export)
                
                # Get lineage if requested
                if include_lineage:
                    lineage = self.get_lineage(guid)
                    if lineage.get("relations"):
                        for relation in lineage["relations"]:
                            rel_export = {
                                "from_entity": relation.get("fromEntityId"),
                                "to_entity": relation.get("toEntityId"),
                                "relationship_type": relation.get("relationshipType")
                            }
                            if rel_export not in export_data["lineage_relationships"]:
                                export_data["lineage_relationships"].append(rel_export)
        
        export_data["summary"] = {
            "total_assets": len(export_data["assets"]),
            "total_lineage_relationships": len(export_data["lineage_relationships"]),
            "asset_types": list(set(a["type"] for a in export_data["assets"]))
        }
        
        return export_data


def main():
    parser = argparse.ArgumentParser(description="Export Purview catalog to JSON")
    parser.add_argument("--purview-account", required=True, help="Purview account name")
    parser.add_argument("--output", default="catalog_export.json", help="Output file path")
    parser.add_argument("--filter", help="Filter keywords for assets")
    parser.add_argument("--no-lineage", action="store_true", help="Skip lineage export")
    args = parser.parse_args()
    
    print(f"Purview Catalog Export")
    print(f"{'='*60}")
    print(f"Account: {args.purview_account}")
    print(f"Output: {args.output}")
    
    try:
        exporter = CatalogExporter(args.purview_account)
        
        export_data = exporter.export_catalog(
            filter_keywords=args.filter,
            include_lineage=not args.no_lineage
        )
        
        # Write to file
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)
        
        print(f"\n{'='*60}")
        print(f"Export complete!")
        print(f"  Assets exported: {export_data['summary']['total_assets']}")
        print(f"  Lineage relationships: {export_data['summary']['total_lineage_relationships']}")
        print(f"  Asset types: {', '.join(export_data['summary']['asset_types'])}")
        print(f"  Output file: {args.output}")
        
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
