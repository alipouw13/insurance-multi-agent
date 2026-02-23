#!/usr/bin/env python3
"""Purview Scanning Data Plane API client for column-level classification.

Correct approach per Microsoft docs:
  1. Create custom classifications (insurance-specific data types)
  2. Create custom classification rules (column-pattern + data-pattern matching)
  3. Create a custom scan rule set that includes system + custom rules
  4. Update the existing Fabric scan to use the custom scan rule set
  5. Trigger a re-scan → classifications applied to existing column assets
  6. Auto-labeling policies (configured in Purview portal) map classifications → sensitivity labels

This does NOT create new entity types or register new entities.
The Fabric-Purview native integration has already discovered the tables and
columns (e.g. claims_history with 23 columns). We only configure HOW
those existing columns should be classified.

References:
- Classification rules API: https://learn.microsoft.com/en-us/rest/api/purview/scanningdataplane/classification-rules
- Scan rule sets API:       https://learn.microsoft.com/en-us/rest/api/purview/scanningdataplane/scan-rulesets
- Scans API:                https://learn.microsoft.com/en-us/rest/api/purview/scanningdataplane/scans
- Auto-classification docs: https://learn.microsoft.com/en-us/purview/data-map-classification-apply-auto
- Auto-labeling docs:       https://learn.microsoft.com/en-us/purview/data-map-sensitivity-labels-apply
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from .config import Config, get_purview_token, retry, logger

logger = logging.getLogger("fabric_scanner.classifier")

# Scanning Data Plane API version
SCAN_API_VERSION = "2023-09-01"


# ---------------------------------------------------------------------------
# Custom classification definitions for the insurance domain
# ---------------------------------------------------------------------------
# Each entry defines:
#   - classification_name: Purview classification (NAMESPACE.NAME format)
#   - rule_name: Classification rule name (alphanumeric + hyphens only)
#   - description: Human-readable purpose
#   - column_patterns: Regex patterns matching column names
#   - data_patterns: (optional) Regex patterns matching actual data values
#   - sensitivity_label: Which MIP sensitivity label should be applied
#                        (via auto-labeling policy, not set directly)

INSURANCE_CLASSIFICATION_RULES: List[Dict[str, Any]] = [
    # --- PII / Highly Confidential ---
    {
        "classification_name": "CONTOSO.INSURANCE.CLAIMANT_NAME",
        "rule_name": "Contoso-Insurance-Claimant-Name",
        "description": "Insurance claimant personal names (PII)",
        "column_patterns": [r"^claimant_name$", r"^name$"],
        "sensitivity_label": "Highly Confidential",
    },
    {
        "classification_name": "CONTOSO.INSURANCE.LICENSE_PLATE",
        "rule_name": "Contoso-Insurance-License-Plate",
        "description": "Vehicle license plate numbers (PII)",
        "column_patterns": [r"^license_plate$", r"^vin$"],
        "sensitivity_label": "Highly Confidential",
    },
    {
        "classification_name": "CONTOSO.INSURANCE.VEHICLE_INFO",
        "rule_name": "Contoso-Insurance-Vehicle-Info",
        "description": "Vehicle identification information",
        "column_patterns": [r"^vehicle_info$"],
        "sensitivity_label": "Highly Confidential",
    },
    {
        "classification_name": "CONTOSO.INSURANCE.RISK_SCORE",
        "rule_name": "Contoso-Insurance-Risk-Score",
        "description": "Claimant risk scores (sensitive analytics)",
        "column_patterns": [r"^risk_score$"],
        "sensitivity_label": "Highly Confidential",
    },
    # --- Fraud / Highly Confidential ---
    {
        "classification_name": "CONTOSO.INSURANCE.FRAUD_INDICATOR",
        "rule_name": "Contoso-Insurance-Fraud-Indicator",
        "description": "Fraud flags and indicators",
        "column_patterns": [r"^fraud_flag$", r"^fraud_rate$", r"^indicator_type$", r"^indicator_id$"],
        "sensitivity_label": "Highly Confidential",
    },
    {
        "classification_name": "CONTOSO.INSURANCE.FRAUD_SEVERITY",
        "rule_name": "Contoso-Insurance-Fraud-Severity",
        "description": "Fraud severity classification",
        "column_patterns": [r"^severity$"],
        "sensitivity_label": "Confidential",
    },
    # --- Financial / Confidential ---
    {
        "classification_name": "CONTOSO.INSURANCE.FINANCIAL_AMOUNT",
        "rule_name": "Contoso-Insurance-Financial-Amount",
        "description": "Monetary amounts (damages, payouts, premiums)",
        "column_patterns": [
            r"^estimated_damage$", r"^amount_paid$", r"^total_amount$",
            r"^avg_amount$", r"^avg_claim_amount$",
        ],
        "sensitivity_label": "Confidential",
    },
    # --- Identifiers / Confidential ---
    {
        "classification_name": "CONTOSO.INSURANCE.CLAIM_ID",
        "rule_name": "Contoso-Insurance-Claim-Id",
        "description": "Insurance claim identifiers",
        "column_patterns": [r"^claim_id$"],
        "sensitivity_label": "Confidential",
    },
    {
        "classification_name": "CONTOSO.INSURANCE.CLAIMANT_ID",
        "rule_name": "Contoso-Insurance-Claimant-Id",
        "description": "Insurance claimant identifiers",
        "column_patterns": [r"^claimant_id$"],
        "sensitivity_label": "Confidential",
    },
    {
        "classification_name": "CONTOSO.INSURANCE.POLICY_NUMBER",
        "rule_name": "Contoso-Insurance-Policy-Number",
        "description": "Insurance policy numbers",
        "column_patterns": [r"^policy_number$"],
        "sensitivity_label": "Confidential",
    },
    # --- General business data ---
    {
        "classification_name": "CONTOSO.INSURANCE.CLAIM_METADATA",
        "rule_name": "Contoso-Insurance-Claim-Metadata",
        "description": "Claim metadata (type, status, dates, location)",
        "column_patterns": [
            r"^claim_type$", r"^status$", r"^claim_date$", r"^incident_date$",
            r"^settlement_date$", r"^flagged_date$", r"^last_claim_date$",
            r"^location$", r"^state$", r"^region$", r"^description$",
            r"^total_claims$", r"^age$",
        ],
        "sensitivity_label": "General",
    },
    {
        "classification_name": "CONTOSO.INSURANCE.EVIDENCE_FLAGS",
        "rule_name": "Contoso-Insurance-Evidence-Flags",
        "description": "Claim evidence indicators (police report, photos, witnesses)",
        "column_patterns": [
            r"^police_report$", r"^photos_provided$", r"^witness_statements$",
        ],
        "sensitivity_label": "General",
    },
]

# System classifications to keep when building scan rule sets.
# These are Purview built-in classifications that may match insurance data.
# By default, all system classifications are active. We only list ones to
# EXCLUDE if needed (see EXCLUDED_SYSTEM_CLASSIFICATIONS).
EXCLUDED_SYSTEM_CLASSIFICATIONS: List[str] = []


# Mapping: classification_name → recommended sensitivity label (for auto-labeling documentation)
CLASSIFICATION_TO_LABEL: Dict[str, str] = {
    rule["classification_name"]: rule["sensitivity_label"]
    for rule in INSURANCE_CLASSIFICATION_RULES
}


# ---------------------------------------------------------------------------
# Scanning Data Plane API helpers
# ---------------------------------------------------------------------------

def _scan_url(path: str) -> str:
    """Build a Scanning Data Plane API URL."""
    return (
        f"https://{Config.purview_account}.purview.azure.com"
        f"/scan/{path}?api-version={SCAN_API_VERSION}"
    )


def _scan_headers() -> Dict[str, str]:
    """Auth headers for the Scanning Data Plane API."""
    return {
        "Authorization": f"Bearer {get_purview_token()}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Step 1: Create custom classifications
# ---------------------------------------------------------------------------

def create_custom_classifications() -> List[str]:
    """Create custom classification types in Purview for insurance-specific data.

    Uses the Scanning Data Plane API: PUT /scan/classificationrules/{name}
    Each classification rule defines column name patterns (regex) that the
    scanner uses to auto-classify columns during a scan.

    Returns list of created/updated classification rule names.
    """
    logger.info("=== Step 1: Creating custom classification rules ===")
    created: List[str] = []
    errors: List[str] = []

    for rule_def in INSURANCE_CLASSIFICATION_RULES:
        rule_name = rule_def["rule_name"]
        classification_name = rule_def["classification_name"]

        # First, ensure the custom classification TYPE exists
        _ensure_classification_type(classification_name, rule_def["description"])

        # Then create the classification RULE (column pattern matching)
        column_patterns = [
            {"kind": "Regex", "pattern": pat}
            for pat in rule_def.get("column_patterns", [])
        ]
        data_patterns = [
            {"kind": "Regex", "pattern": pat}
            for pat in rule_def.get("data_patterns", [])
        ]

        payload = {
            "kind": "Custom",
            "properties": {
                "description": rule_def["description"],
                "classificationName": classification_name,
                "ruleStatus": "Enabled",
                "columnPatterns": column_patterns,
            },
        }
        if data_patterns:
            payload["properties"]["dataPatterns"] = data_patterns
            payload["properties"]["minimumPercentageMatch"] = 60

        if Config.dry_run:
            logger.info("  [DRY RUN] Would create rule: %s -> %s", rule_name, classification_name)
            created.append(rule_name)
            continue

        url = _scan_url(f"classificationrules/{rule_name}")
        resp = requests.put(url, headers=_scan_headers(), json=payload, timeout=30)

        if resp.status_code in (200, 201):
            logger.info("  Created/updated rule: %s -> %s", rule_name, classification_name)
            created.append(rule_name)
        else:
            logger.error(
                "  Failed to create rule '%s': %s %s",
                rule_name, resp.status_code, resp.text[:300],
            )
            errors.append(rule_name)

    logger.info(
        "Classification rules: %d created/updated, %d errors",
        len(created), len(errors),
    )
    return created


def _ensure_classification_type(classification_name: str, description: str) -> None:
    """Ensure a custom classification type exists in the Purview catalog.

    The Scanning Data Plane uses a separate endpoint for classification types:
        PUT {endpoint}/scan/classificationrules/{name} with kind=Custom
    requires that the classification NAME already exists as a custom classification.

    Custom classifications are created via the catalog API:
        POST {endpoint}/catalog/api/atlas/v2/types/typedefs
    """
    url = (
        f"https://{Config.purview_account}.purview.azure.com"
        f"/catalog/api/atlas/v2/types/typedefs"
    )
    headers = {
        "Authorization": f"Bearer {get_purview_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "classificationDefs": [
            {
                "name": classification_name,
                "description": description,
                "superTypes": [],
                "attributeDefs": [],
            }
        ]
    }

    if Config.dry_run:
        return

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code in (200, 201):
        logger.debug("  Classification type '%s' ensured", classification_name)
    elif resp.status_code == 409 or "already exists" in resp.text.lower():
        logger.debug("  Classification type '%s' already exists", classification_name)
    else:
        # Try PUT (update) if POST fails
        resp2 = requests.put(url, headers=headers, json=payload, timeout=30)
        if resp2.status_code in (200, 201):
            logger.debug("  Classification type '%s' updated", classification_name)
        else:
            logger.warning(
                "  Could not create classification type '%s': %s %s",
                classification_name, resp.status_code, resp.text[:200],
            )


# ---------------------------------------------------------------------------
# Step 2: Create custom scan rule set
# ---------------------------------------------------------------------------

def create_scan_rule_set(
    rule_set_name: str = "Contoso-Insurance-Fabric-Ruleset",
) -> bool:
    """Create a custom scan rule set that includes our classification rules.

    The scan rule set tells the Purview scanner WHICH classification rules
    to evaluate when scanning columns. It includes:
    - All system classifications (200+ built-in) minus any exclusions
    - Our custom insurance classification rules

    Uses: PUT /scan/scanrulesets/{name}
    """
    logger.info("=== Step 2: Creating custom scan rule set '%s' ===", rule_set_name)

    custom_rule_names = [r["rule_name"] for r in INSURANCE_CLASSIFICATION_RULES]

    payload = {
        "kind": "Fabric",
        "scanRulesetType": "Custom",
        "properties": {
            "description": "Insurance claims classification rules for Fabric lakehouse tables",
            "excludedSystemClassifications": EXCLUDED_SYSTEM_CLASSIFICATIONS,
            "includedCustomClassificationRuleNames": custom_rule_names,
        },
    }

    if Config.dry_run:
        logger.info("  [DRY RUN] Would create scan rule set with %d custom rules", len(custom_rule_names))
        return True

    url = _scan_url(f"scanrulesets/{rule_set_name}")
    resp = requests.put(url, headers=_scan_headers(), json=payload, timeout=30)

    if resp.status_code in (200, 201):
        logger.info("  Scan rule set created/updated: %s", rule_set_name)
        logger.info("  Custom rules included: %s", custom_rule_names)
        return True
    else:
        logger.error(
            "  Failed to create scan rule set: %s %s",
            resp.status_code, resp.text[:500],
        )
        return False


# ---------------------------------------------------------------------------
# Step 3: Update existing scan to use our rule set
# ---------------------------------------------------------------------------

def update_scan_rule_set_on_scan(
    data_source_name: str,
    scan_name: str,
    rule_set_name: str = "Contoso-Insurance-Fabric-Ruleset",
) -> bool:
    """Update an existing Purview scan to use our custom scan rule set.

    The scan was already configured by the Fabric-Purview native integration
    (e.g. 'Scan-Fabric-Claims-Demo'). We update it to use our custom rule set
    instead of the default system rule set.

    Uses: PUT /scan/datasources/{name}/scans/{name}
    """
    logger.info(
        "=== Step 3: Updating scan '%s' on data source '%s' to use rule set '%s' ===",
        scan_name, data_source_name, rule_set_name,
    )

    # First GET the existing scan configuration
    get_url = _scan_url(f"datasources/{data_source_name}/scans/{scan_name}")
    resp = requests.get(get_url, headers=_scan_headers(), timeout=30)

    if resp.status_code != 200:
        logger.error(
            "  Could not retrieve scan '%s': %s %s",
            scan_name, resp.status_code, resp.text[:300],
        )
        return False

    scan_config = resp.json()
    logger.info("  Current scan kind: %s", scan_config.get("kind"))
    logger.info(
        "  Current scan rule set: %s (type: %s)",
        scan_config.get("properties", {}).get("scanRulesetName"),
        scan_config.get("properties", {}).get("scanRulesetType"),
    )

    # Update the scan rule set reference
    if "properties" not in scan_config:
        scan_config["properties"] = {}
    scan_config["properties"]["scanRulesetName"] = rule_set_name
    scan_config["properties"]["scanRulesetType"] = "Custom"

    if Config.dry_run:
        logger.info("  [DRY RUN] Would update scan to use rule set '%s'", rule_set_name)
        return True

    # PUT the updated scan
    resp = requests.put(get_url, headers=_scan_headers(), json=scan_config, timeout=30)

    if resp.status_code in (200, 201):
        logger.info("  Scan updated to use custom rule set '%s'", rule_set_name)
        return True
    else:
        logger.error(
            "  Failed to update scan: %s %s",
            resp.status_code, resp.text[:500],
        )
        return False


# ---------------------------------------------------------------------------
# Step 4: Trigger a scan run
# ---------------------------------------------------------------------------

def trigger_scan_run(
    data_source_name: str,
    scan_name: str,
    scan_level: str = "Full",
) -> Optional[str]:
    """Trigger an on-demand scan run.

    Uses: POST {endpoint}/scan/datasources/{name}/scans/{name}:run
          ?runId={guid}&scanLevel=Full&api-version=2023-09-01

    The runId and scanLevel are query parameters (not path segments).

    Returns the run ID if successful, None otherwise.
    """
    import uuid

    run_id = str(uuid.uuid4())
    logger.info(
        "=== Step 4: Triggering %s scan run '%s' ===",
        scan_level, run_id,
    )

    if Config.dry_run:
        logger.info("  [DRY RUN] Would trigger scan run")
        return "dry-run-id"

    # Build URL with :run action suffix and query params
    url = (
        f"https://{Config.purview_account}.purview.azure.com"
        f"/scan/datasources/{data_source_name}/scans/{scan_name}:run"
        f"?runId={run_id}&scanLevel={scan_level}&api-version={SCAN_API_VERSION}"
    )
    resp = requests.post(url, headers=_scan_headers(), timeout=30)

    if resp.status_code in (200, 201, 202):
        logger.info("  Scan run triggered: %s", run_id)
        return run_id
    else:
        logger.error(
            "  Failed to trigger scan: %s %s",
            resp.status_code, resp.text[:500],
        )
        return None


def wait_for_scan_completion(
    data_source_name: str,
    scan_name: str,
    run_id: str,
    timeout_minutes: int = 30,
    poll_interval_seconds: int = 30,
) -> str:
    """Poll scan status until completion or timeout.

    Returns final status: 'Succeeded', 'Failed', 'Canceled', or 'Timeout'.
    """
    logger.info("  Waiting for scan completion (timeout: %d min)...", timeout_minutes)
    deadline = time.time() + timeout_minutes * 60

    while time.time() < deadline:
        url = _scan_url(
            f"datasources/{data_source_name}/scans/{scan_name}/runs/{run_id}"
        )
        resp = requests.get(url, headers=_scan_headers(), timeout=30)

        if resp.status_code != 200:
            logger.warning("  Could not check scan status: %s", resp.status_code)
            time.sleep(poll_interval_seconds)
            continue

        run_data = resp.json()
        status = run_data.get("status", "Unknown")
        logger.info("  Scan status: %s", status)

        if status in ("Succeeded", "Failed", "Canceled"):
            return status

        time.sleep(poll_interval_seconds)

    logger.warning("  Scan timed out after %d minutes", timeout_minutes)
    return "Timeout"


# ---------------------------------------------------------------------------
# Step 5: List existing data sources and scans (discovery)
# ---------------------------------------------------------------------------

def list_data_sources() -> List[Dict[str, Any]]:
    """List all registered data sources in Purview."""
    url = _scan_url("datasources")
    resp = requests.get(url, headers=_scan_headers(), timeout=30)
    if resp.status_code != 200:
        logger.error("Failed to list data sources: %s %s", resp.status_code, resp.text[:300])
        return []
    return resp.json().get("value", [])


def list_scans(data_source_name: str) -> List[Dict[str, Any]]:
    """List all scans for a data source."""
    url = _scan_url(f"datasources/{data_source_name}/scans")
    resp = requests.get(url, headers=_scan_headers(), timeout=30)
    if resp.status_code != 200:
        logger.error("Failed to list scans: %s %s", resp.status_code, resp.text[:300])
        return []
    return resp.json().get("value", [])


def list_classification_rules() -> List[Dict[str, Any]]:
    """List all classification rules (system + custom)."""
    url = _scan_url("classificationrules")
    resp = requests.get(url, headers=_scan_headers(), timeout=30)
    if resp.status_code != 200:
        logger.error("Failed to list classification rules: %s %s", resp.status_code, resp.text[:300])
        return []
    return resp.json().get("value", [])


def list_scan_rulesets() -> List[Dict[str, Any]]:
    """List all scan rule sets (system + custom)."""
    url = _scan_url("scanrulesets")
    resp = requests.get(url, headers=_scan_headers(), timeout=30)
    if resp.status_code != 200:
        logger.error("Failed to list scan rulesets: %s %s", resp.status_code, resp.text[:300])
        return []
    return resp.json().get("value", [])


# ---------------------------------------------------------------------------
# High-level orchestration
# ---------------------------------------------------------------------------

def configure_and_run_classification(
    data_source_name: str,
    scan_name: str,
    rule_set_name: str = "Contoso-Insurance-Fabric-Ruleset",
    trigger_scan: bool = True,
    wait_for_completion: bool = False,
) -> Dict[str, Any]:
    """Full pipeline: create classification rules, scan rule set, update scan, trigger.

    This is the correct approach per Microsoft docs:
    1. Classifications are applied by the scanner during scan execution
    2. Sensitivity labels are applied by auto-labeling policies
       (configured separately in Information Protection portal)

    Args:
        data_source_name: Purview data source name (e.g. the Fabric workspace)
        scan_name: Existing scan name (e.g. 'Scan-Fabric-Claims-Demo')
        rule_set_name: Name for the custom scan rule set
        trigger_scan: Whether to trigger a scan after configuration
        wait_for_completion: Whether to poll until scan completes

    Returns:
        Summary dict with results of each step.
    """
    summary: Dict[str, Any] = {
        "classification_rules_created": [],
        "scan_rule_set_created": False,
        "scan_updated": False,
        "scan_triggered": False,
        "scan_run_id": None,
        "scan_status": None,
    }

    # Step 1: Create custom classification rules
    created_rules = create_custom_classifications()
    summary["classification_rules_created"] = created_rules

    # Step 2: Create custom scan rule set
    summary["scan_rule_set_created"] = create_scan_rule_set(rule_set_name)

    # Step 3: Update existing scan to use our rule set
    summary["scan_updated"] = update_scan_rule_set_on_scan(
        data_source_name, scan_name, rule_set_name,
    )

    # Step 4: Trigger scan (optional)
    if trigger_scan and summary["scan_updated"]:
        run_id = trigger_scan_run(data_source_name, scan_name)
        summary["scan_run_id"] = run_id
        summary["scan_triggered"] = run_id is not None

        if wait_for_completion and run_id:
            status = wait_for_scan_completion(data_source_name, scan_name, run_id)
            summary["scan_status"] = status

    return summary


# ---------------------------------------------------------------------------
# Step 5 (Fabric-specific): Direct classification of existing column entities
# ---------------------------------------------------------------------------
# Fabric MSI scans discover schema but do NOT apply classification rules
# at scan time (unlike Azure SQL, ADLS, etc.). For Fabric, we must apply
# classifications directly to the existing column entities via Atlas v2 API.

def _catalog_url(path: str, api_version: str = "2022-03-01") -> str:
    """Build an Atlas v2 Catalog API URL."""
    return (
        f"https://{Config.purview_account}.purview.azure.com"
        f"/catalog/api/atlas/v2/{path}?api-version={api_version}"
    )


def _catalog_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {get_purview_token()}",
        "Content-Type": "application/json",
    }


def _build_column_classification_map() -> Dict[str, str]:
    """Build a mapping of column_name_regex → classification_name from rules.

    Returns dict of {regex_pattern: classification_name} for all rules.
    """
    import re
    mapping: Dict[str, str] = {}
    for rule in INSURANCE_CLASSIFICATION_RULES:
        for pattern in rule.get("column_patterns", []):
            mapping[pattern] = rule["classification_name"]
    return mapping


def _match_column_to_classification(
    column_name: str,
    pattern_map: Dict[str, str],
) -> Optional[str]:
    """Match a column name against classification rules.

    Returns the classification name if matched, None otherwise.
    """
    import re
    for pattern, classif_name in pattern_map.items():
        if re.match(pattern, column_name, re.IGNORECASE):
            return classif_name
    return None


def search_fabric_tables(
    data_source_name: str,
    table_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Search Purview data map for Fabric lakehouse tables.

    Returns list of table entities with their GUIDs and column info.
    Filters to only natively-discovered tables (QN starts with https://app.fabric.microsoft.com).
    """
    logger.info("Searching for Fabric lakehouse tables...")

    url = (
        f"https://{Config.purview_account}.purview.azure.com"
        f"/catalog/api/search/query?api-version=2022-08-01-preview"
    )
    payload = {
        "keywords": "*",
        "filter": {
            "and": [
                {"objectType": "Tables"},
                {"entityType": "fabric_lakehouse_table"},
            ]
        },
        "limit": 100,
    }
    resp = requests.post(url, headers=_catalog_headers(), json=payload, timeout=60)
    if resp.status_code != 200:
        logger.error("Search failed: %s %s", resp.status_code, resp.text[:300])
        return []

    results = resp.json().get("value", [])

    # Filter to only native Fabric-discovered tables (not our old duplicates)
    native_tables = []
    for item in results:
        qn = item.get("qualifiedName", "")
        name = item.get("name", "")

        # Native Fabric scan creates QNs like:
        # https://app.fabric.microsoft.com/groups/{groupId}/lakehouses/{lhId}/...
        if qn.startswith("https://app.fabric.microsoft.com"):
            if table_names is None or name in table_names:
                native_tables.append(item)

    logger.info("Found %d native Fabric tables (out of %d total)", len(native_tables), len(results))
    return native_tables


def get_table_columns(table_guid: str) -> List[Dict[str, Any]]:
    """Get all column entities for a table via its GUID.

    Returns list of column dicts with guid, name, and existing classifications.
    """
    url = _catalog_url(f"entity/guid/{table_guid}")
    resp = requests.get(url, headers=_catalog_headers(), timeout=30)
    if resp.status_code != 200:
        logger.error("Could not get table entity %s: %s", table_guid, resp.status_code)
        return []

    entity = resp.json().get("entity", {})
    rel_attrs = entity.get("relationshipAttributes", {})
    # Fabric tables have columns under 'columns' or 'tabular_schema'
    columns_ref = rel_attrs.get("columns", rel_attrs.get("tabular_schema", []))

    columns = []
    for col_ref in columns_ref:
        col_guid = col_ref.get("guid", "")
        col_name = col_ref.get("displayText", "")
        if col_guid:
            columns.append({
                "guid": col_guid,
                "name": col_name,
            })

    return columns


def get_column_classifications(column_guid: str) -> List[str]:
    """Get existing classification type names for a column entity."""
    url = _catalog_url(f"entity/guid/{column_guid}/classifications")
    resp = requests.get(url, headers=_catalog_headers(), timeout=30)
    if resp.status_code == 200:
        classifs = resp.json().get("list", [])
        return [c.get("typeName", "") for c in classifs]
    return []


def apply_classification_to_entity(
    entity_guid: str,
    classification_name: str,
) -> bool:
    """Apply a classification to an existing entity via Atlas v2 API.

    Uses: POST /catalog/api/atlas/v2/entity/guid/{guid}/classifications
    """
    url = _catalog_url(f"entity/guid/{entity_guid}/classifications")
    payload = [
        {
            "typeName": classification_name,
            "attributes": {},
        }
    ]
    resp = requests.post(url, headers=_catalog_headers(), json=payload, timeout=30)

    if resp.status_code in (200, 201, 204):
        return True
    elif resp.status_code == 409 or "already" in resp.text.lower():
        # Classification already exists on this entity
        return True
    else:
        logger.error(
            "Failed to classify entity %s with '%s': %s %s",
            entity_guid, classification_name, resp.status_code, resp.text[:200],
        )
        return False


def classify_existing_columns(
    table_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Apply classifications directly to existing Fabric column entities.

    This is the Fabric-specific approach since Fabric MSI scans don't
    apply classification rules during scanning.

    Steps:
      1. Ensure custom classification type definitions exist
      2. Search for existing Fabric tables in Purview data map
      3. Get column entities for each table
      4. Match column names against classification rules
      5. Apply classifications directly via Atlas API

    Args:
        table_names: Optional filter - only classify columns in these tables.
                     If None, all discovered tables are processed.

    Returns:
        Summary dict with counts and details.
    """
    logger.info("=== Classifying existing Fabric column entities ===")

    # Ensure classification type definitions exist
    logger.info("Step 1: Ensuring classification type definitions...")
    create_custom_classifications()

    # Build column name → classification mapping
    pattern_map = _build_column_classification_map()

    # Find tables
    logger.info("Step 2: Searching for existing Fabric tables...")
    tables = search_fabric_tables(Config.data_source_name, table_names)

    results: List[Dict[str, Any]] = []
    total_classified = 0
    total_skipped = 0
    total_errors = 0
    total_already = 0

    for table in tables:
        table_name = table.get("name", "unknown")
        table_guid = table.get("id", "")

        logger.info("Processing table: %s (guid=%s)", table_name, table_guid[:12])

        # Get column entities
        columns = get_table_columns(table_guid)
        logger.info("  Found %d columns", len(columns))

        for col in columns:
            col_name = col["name"]
            col_guid = col["guid"]

            # Match against classification rules
            classif_name = _match_column_to_classification(col_name, pattern_map)
            if not classif_name:
                total_skipped += 1
                continue

            if Config.dry_run:
                logger.info("    [DRY RUN] Would classify %s.%-25s as %s", table_name, col_name, classif_name)
                results.append({
                    "table": table_name,
                    "column": col_name,
                    "classification": classif_name,
                    "status": "dry_run",
                })
                total_classified += 1
                continue

            # Check if already classified (skip this expensive check in dry-run)
            existing = get_column_classifications(col_guid)
            if classif_name in existing:
                logger.info("    %s.%-25s already has %s", table_name, col_name, classif_name)
                total_already += 1
                results.append({
                    "table": table_name,
                    "column": col_name,
                    "classification": classif_name,
                    "status": "already_exists",
                })
                continue

            # Apply classification
            success = apply_classification_to_entity(col_guid, classif_name)
            if success:
                logger.info("    %s.%-25s -> %s", table_name, col_name, classif_name)
                total_classified += 1
                results.append({
                    "table": table_name,
                    "column": col_name,
                    "classification": classif_name,
                    "guid": col_guid,
                    "status": "applied",
                })
            else:
                total_errors += 1
                results.append({
                    "table": table_name,
                    "column": col_name,
                    "classification": classif_name,
                    "guid": col_guid,
                    "status": "error",
                })

    logger.info("")
    logger.info("Classification results:")
    logger.info("  Applied: %d", total_classified)
    logger.info("  Already existed: %d", total_already)
    logger.info("  Skipped (no rule match): %d", total_skipped)
    logger.info("  Errors: %d", total_errors)

    return {
        "classified": total_classified,
        "already_existed": total_already,
        "skipped": total_skipped,
        "errors": total_errors,
        "details": results,
    }


# ---------------------------------------------------------------------------
# Auto-labeling policy guidance (documentation helper)
# ---------------------------------------------------------------------------

def print_auto_labeling_guidance() -> None:
    """Print guidance for setting up auto-labeling policies.

    Auto-labeling policies map classifications -> sensitivity labels.
    These MUST be configured in the Microsoft Purview portal (Information
    Protection), not via the Scanning Data Plane API.
    """
    print("\n" + "=" * 70)
    print("AUTO-LABELING POLICY SETUP GUIDE")
    print("=" * 70)
    print("""
After classifications are applied to columns by the scan, you need to
create auto-labeling policies in the Purview portal to automatically
apply sensitivity labels based on detected classifications.

Steps:
  1. Go to Microsoft Purview portal → Information Protection → Policies
     → Auto-labeling policies
  2. Click '+ Create auto-labeling policy'
  3. For each sensitivity label, create a policy:

Recommended policies:
""")
    # Group by sensitivity label
    from collections import defaultdict
    label_groups: Dict[str, List[str]] = defaultdict(list)
    for rule in INSURANCE_CLASSIFICATION_RULES:
        label_groups[rule["sensitivity_label"]].append(rule["classification_name"])

    for label, classifs in sorted(label_groups.items()):
        print(f"  Policy: 'Auto-label {label}'")
        print(f"    Sensitivity Label: {label}")
        print(f"    Conditions (any of these classifications found):")
        for c in classifs:
            print(f"      - {c}")
        print()

    print("""  4. Scope each policy to your Fabric data source location
  5. Set 'Run policy in simulation mode' first to preview
  6. After 7 days (or manually), turn on the policy
  7. Wait 15 minutes after policy creation, then run a scan

Reference: https://learn.microsoft.com/en-us/purview/data-map-sensitivity-labels-apply
""")
    print("=" * 70)
