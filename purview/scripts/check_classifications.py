#!/usr/bin/env python3
"""Quick check: see if classifications were applied to claims_history columns."""
import logging, requests, json, sys
from pathlib import Path

logging.getLogger('azure').setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)-28s %(levelname)-7s %(message)s', datefmt='%H:%M:%S', force=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fabric_scanner.config import Config, load_env, get_purview_token

load_env()
Config.reload()

hdrs = {"Authorization": f"Bearer {get_purview_token()}", "Content-Type": "application/json"}

# Search for claims_history
url = f"https://{Config.purview_account}.purview.azure.com/catalog/api/search/query?api-version=2022-08-01-preview"
payload = {"keywords": "claims_history", "limit": 10}
resp = requests.post(url, headers=hdrs, json=payload, timeout=30)
data = resp.json()
print(f"Search results: {len(data.get('value', []))}")

for item in data.get("value", [])[:5]:
    name = item.get("name", "")
    qn = item.get("qualifiedName", "")[:120]
    etype = item.get("entityType", "")
    classifs = item.get("classification", [])
    print(f"\n  [{etype}] {name}")
    print(f"    QN: {qn}")
    print(f"    Classifications: {classifs}")
    guid = item.get("id", "")

    # If it's a table, get full entity to see column classifications
    if "table" in etype.lower() or "Table" in etype:
        ent_url = f"https://{Config.purview_account}.purview.azure.com/catalog/api/atlas/v2/entity/guid/{guid}?api-version=2022-03-01"
        ent_resp = requests.get(ent_url, headers=hdrs, timeout=30)
        if ent_resp.status_code == 200:
            ent = ent_resp.json()
            entity = ent.get("entity", {})
            # Check for column relationships
            rel_attrs = entity.get("relationshipAttributes", {})
            columns = rel_attrs.get("columns", rel_attrs.get("tabular_schema", []))
            if columns:
                print(f"    Columns ({len(columns)}):")
                for col in columns[:5]:
                    col_name = col.get("displayText", col.get("guid", ""))
                    col_guid = col.get("guid", "")
                    print(f"      - {col_name} (guid: {col_guid[:10]}...)")

                # Check a specific column for classifications
                if columns:
                    first_col_guid = columns[0].get("guid", "")
                    col_url = f"https://{Config.purview_account}.purview.azure.com/catalog/api/atlas/v2/entity/guid/{first_col_guid}?api-version=2022-03-01"
                    col_resp = requests.get(col_url, headers=hdrs, timeout=30)
                    if col_resp.status_code == 200:
                        col_ent = col_resp.json().get("entity", {})
                        col_classifs = col_ent.get("classifications", [])
                        col_name_ = col_ent.get("attributes", {}).get("name", "")
                        print(f"\n    Checking first column '{col_name_}' classifications:")
                        if col_classifs:
                            for c in col_classifs:
                                print(f"      - {c.get('typeName', 'unknown')}")
                        else:
                            print(f"      (none)")
