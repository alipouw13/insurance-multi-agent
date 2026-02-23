#!/usr/bin/env python3
"""Quick verification script – queries Purview Atlas v2 API to confirm
entities and classifications were registered by the scanner."""

import json
import sys
import requests

# Force UTF-8 output even when piped on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from fabric_scanner.config import Config, load_env, get_purview_token

load_env()
Config.reload()

BASE = f"https://{Config.purview_account}.purview.azure.com/catalog/api/atlas/v2"
SEARCH_URL = f"https://{Config.purview_account}.purview.azure.com/catalog/api/search/query?api-version=2022-08-01-preview"
TOKEN = get_purview_token()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

WS = Config.fabric_workspace_id
LAKEHOUSES = ["LH_fsidemoInsurance", "LH_fsidemoInsurance_Silver", "LH_fsidemoInsurance_Gold"]
TABLES = ["claims_history", "claimant_profiles", "fraud_indicators", "policy_claims_summary", "regional_statistics"]


def search(query: str, type_name: str | None = None, limit: int = 50):
    """Search via Purview catalog with optional type filter."""
    body: dict = {"keywords": query, "limit": limit}
    if type_name:
        body["filter"] = {"typeName": type_name}
    resp = requests.post(SEARCH_URL, headers=HEADERS, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_entity_by_guid(guid: str):
    resp = requests.get(f"{BASE}/entity/guid/{guid}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_entity_by_qn(qn: str, type_name: str):
    """Look up an entity by qualifiedName via Atlas v2."""
    params = {"attr:qualifiedName": qn, "typeName": type_name}
    resp = requests.get(f"{BASE}/entity/uniqueAttribute/type/{type_name}",
                        headers=HEADERS, params=params, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


# ============================================================
print("=" * 60)
print("VERIFICATION: Purview entities from Fabric Scanner")
print("=" * 60)
errors = 0

# ── 1) Check custom type definitions exist ──
print("\n1. Type definitions:")
for tname in ["fabric_column", "fabric_lakehouse_table", "fabric_warehouse_table"]:
    try:
        resp = requests.get(f"{BASE}/types/typedef/name/{tname}", headers=HEADERS, timeout=30)
        if resp.ok:
            td = resp.json()
            print(f"   ✓ {tname} (category={td.get('category')})")
        else:
            print(f"   ✗ {tname} – HTTP {resp.status_code}")
            errors += 1
    except Exception as e:
        print(f"   ✗ {tname} – {e}")
        errors += 1

for cname in ["MIP_Highly_Confidential", "MIP_Confidential", "MIP_General", "MIP_Public", "MIP_Personal"]:
    try:
        resp = requests.get(f"{BASE}/types/typedef/name/{cname}", headers=HEADERS, timeout=30)
        if resp.ok:
            print(f"   ✓ {cname} (classification)")
        else:
            print(f"   ✗ {cname} – HTTP {resp.status_code}")
            errors += 1
    except Exception as e:
        print(f"   ✗ {cname} – {e}")
        errors += 1

# ── 2) Check table entities by qualifiedName ──
print(f"\n2. Table entities (expect {len(LAKEHOUSES) * len(TABLES)} = {len(LAKEHOUSES)}×{len(TABLES)}):")
tbl_found = 0
for lh in LAKEHOUSES:
    for tbl in TABLES:
        qn = f"fabric://{WS}/{lh}/{tbl}"
        ent = get_entity_by_qn(qn, "fabric_lakehouse_table")
        if ent:
            tbl_found += 1
            guid = ent.get("entity", {}).get("guid", "?")
            print(f"   ✓ {lh}/{tbl}  guid={guid[:12]}…")
        else:
            print(f"   ✗ {lh}/{tbl}  NOT FOUND")
            errors += 1
print(f"   → {tbl_found}/15 table entities found")

# ── 3) Spot-check column entities + classifications ──
print("\n3. Column spot-check (first lakehouse):")
spot_checks = [
    ("claims_history",    "claim_id",       "MIP_Confidential"),
    ("claims_history",    "claimant_name",  "MIP_Highly_Confidential"),
    ("claims_history",    "fraud_flag",     "MIP_Highly_Confidential"),
    ("claimant_profiles", "risk_score",     "MIP_Highly_Confidential"),
    ("fraud_indicators",  "indicator_type", "MIP_Highly_Confidential"),
    ("regional_statistics","fraud_rate",    "MIP_Highly_Confidential"),
]
col_ok = 0
for tbl, col, expected_cls in spot_checks:
    qn = f"fabric://{WS}/{LAKEHOUSES[0]}/{tbl}#{col}"
    ent = get_entity_by_qn(qn, "fabric_column")
    if ent:
        classifs = [c["typeName"] for c in ent.get("entity", {}).get("classifications", [])]
        has_expected = expected_cls in classifs
        tag = "✓" if has_expected else "⚠"
        if has_expected:
            col_ok += 1
        else:
            errors += 1
        print(f"   {tag} {tbl}.{col}  class={classifs}  (expected {expected_cls})")
    else:
        print(f"   ✗ {tbl}.{col}  NOT FOUND")
        errors += 1
print(f"   → {col_ok}/{len(spot_checks)} columns with correct classification")

# ── 4) Search-based counts ──
print("\n4. Classification distribution (search):")
for classif in ["MIP_Highly_Confidential", "MIP_Confidential", "MIP_General", "MIP_Public", "MIP_Personal"]:
    result = search(classif, limit=200)
    count = len(result.get("value", []))
    print(f"   {classif:30s} → {count} search hits")

# ── Summary ──
print("\n" + "=" * 60)
if errors == 0:
    print("RESULT: ALL CHECKS PASSED ✓")
else:
    print(f"RESULT: {errors} issue(s) found — see details above")
print()
print("Manual verification in the Purview portal:")
print(f"  https://purview.microsoft.com/datacatalog")
print(f"  → Search for 'claims_history' or 'claimant_name'")
print(f"  → Data Map → Collections → {Config.purview_collection}")
print("=" * 60)
sys.exit(0 if errors == 0 else 1)
