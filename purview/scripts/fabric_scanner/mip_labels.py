#!/usr/bin/env python3
"""Fetch Microsoft Information Protection (MIP) sensitivity labels and map
them to columns based on data classification rules.

This module:
1. Fetches published sensitivity labels from Microsoft Graph API
2. Applies a rule engine to map column names/types → sensitivity labels
3. Returns the mapping so the classifier module can register Atlas classifications

API references:
- Graph MIP labels: https://learn.microsoft.com/en-us/graph/api/informationprotectionpolicy-list-labels
- Purview sensitivity labels for Fabric: https://learn.microsoft.com/en-us/fabric/governance/sensitivity-label-overview
- purview-api-cookbook patterns: https://github.com/mrobson1975/purview-api-cookbook

IMPORTANT: Fetching MIP labels via Graph requires the application permission
``InformationProtectionPolicy.Read.All`` or delegated ``InformationProtectionPolicy.Read``.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

from .config import Config, get_graph_token, retry

logger = logging.getLogger("fabric_scanner.mip_labels")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SensitivityLabel:
    """A Microsoft MIP sensitivity label."""
    id: str
    name: str
    description: str = ""
    tooltip: str = ""
    priority: int = 0
    is_active: bool = True
    parent_id: Optional[str] = None  # for sub-labels


# ---------------------------------------------------------------------------
# Graph API helpers
# ---------------------------------------------------------------------------

GRAPH_BASE = "https://graph.microsoft.com"

# User-Agent header required/recommended by the MIP Graph endpoints
_USER_AGENT = "InsuranceClaimsFabricScanner/1.0"


def _graph_get_no_retry(url: str) -> requests.Response:
    """Single Graph GET request (no retry — callers handle fallback)."""
    headers = {
        "Authorization": f"Bearer {get_graph_token()}",
        "Content-Type": "application/json",
        "User-Agent": _USER_AGENT,
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp


def fetch_sensitivity_labels() -> List[SensitivityLabel]:
    """Fetch all published sensitivity labels from Microsoft Graph.

    Tries endpoints in order (first success wins):
      1. v1.0 /security/dataSecurityAndGovernance/sensitivityLabels
         (newest, requires SensitivityLabel.Read or SensitivityLabels.Read.All)
      2. v1.0 /security/informationProtection/sensitivityLabels
         (requires InformationProtectionPolicy.Read.All)
      3. beta /security/informationProtection/sensitivityLabels
         (same as #2 but beta)

    Refs:
    - https://learn.microsoft.com/en-us/graph/api/tenantdatasecurityandgovernance-list-sensitivitylabels
    - https://learn.microsoft.com/en-us/graph/api/security-informationprotection-list-sensitivitylabels
    """
    labels: List[SensitivityLabel] = []

    endpoints = [
        # Newest v1.0 endpoint (SensitivityLabel.Read / SensitivityLabels.Read.All)
        f"{GRAPH_BASE}/v1.0/security/dataSecurityAndGovernance/sensitivityLabels",
        # Stable v1.0 endpoint (InformationProtectionPolicy.Read.All)
        f"{GRAPH_BASE}/v1.0/security/informationProtection/sensitivityLabels",
        # Beta variant of the above
        f"{GRAPH_BASE}/beta/security/informationProtection/sensitivityLabels",
    ]

    for endpoint in endpoints:
        try:
            resp = _graph_get_no_retry(endpoint)
            raw_labels = resp.json().get("value", [])
            for lbl in raw_labels:
                labels.append(
                    SensitivityLabel(
                        id=lbl["id"],
                        name=lbl.get("name", lbl.get("displayName", "")),
                        description=lbl.get("description", ""),
                        tooltip=lbl.get("tooltip", ""),
                        priority=lbl.get("priority", 0),
                        is_active=lbl.get("isActive", True),
                        parent_id=lbl.get("parent", {}).get("id") if isinstance(lbl.get("parent"), dict) else None,
                    )
                )
            logger.info("Fetched %d sensitivity labels from %s", len(labels), endpoint)
            return labels
        except requests.HTTPError as exc:
            logger.warning("Graph endpoint %s returned %s – trying next", endpoint, exc)
            continue

    logger.warning(
        "Could not fetch MIP labels from any Graph endpoint. "
        "Ensure app has one of: SensitivityLabels.Read.All (preferred) "
        "or InformationProtectionPolicy.Read.All. "
        "Falling back to default label set."
    )
    return _default_labels()


def _default_labels() -> List[SensitivityLabel]:
    """Return the standard Microsoft default sensitivity labels for offline use.

    These match the labels described in purview/06-sensitivity-labels.md.
    """
    return [
        SensitivityLabel(id="personal", name="Personal", priority=0),
        SensitivityLabel(id="public", name="Public", priority=1),
        SensitivityLabel(id="general", name="General", priority=2),
        SensitivityLabel(id="confidential", name="Confidential", priority=5),
        SensitivityLabel(id="highly-confidential", name="Highly Confidential", priority=9),
    ]


# ---------------------------------------------------------------------------
# Column → Sensitivity label mapping rules
# ---------------------------------------------------------------------------
# These rules are specific to the insurance-claims domain and match the
# recommended labels from purview/06-sensitivity-labels.md.
#
# Rule format: (regex_pattern_for_column_name, assigned_label_name)
# Rules are evaluated top-down; first match wins.

# Use (?:^|_) / (?:$|_) instead of \b because underscores are word-chars
# and column names like 'total_claim_amount' won't match \bamount\b.
_B = r"(?:^|(?<=_))"  # word start (beginning of string or preceded by _)
_E = r"(?:$|(?=_))"   # word end   (end of string or followed by _)

_COLUMN_RULES: List[tuple[str, str]] = [
    # PII – Highly Confidential
    (r"(?i)(?:^|_)name(?:$|_)", "Highly Confidential"),
    (r"(?i)(ssn|social_security|tax_id)", "Highly Confidential"),
    (r"(?i)(dob|date_of_birth|birth_date)", "Highly Confidential"),
    (r"(?i)(email|phone|address|zip_code)", "Highly Confidential"),
    (r"(?i)(license_plate|vin(?:$|_))", "Highly Confidential"),
    (r"(?i)(bank_account|credit_card|iban)", "Highly Confidential"),

    # Fraud / Risk – Highly Confidential
    (r"(?i)fraud", "Highly Confidential"),
    (r"(?i)risk_score", "Highly Confidential"),
    (r"(?i)(?:^|_)severity(?:$|_)", "Confidential"),
    (r"(?i)indicator", "Highly Confidential"),

    # Financial – Confidential
    (r"(?i)(amount|damage|paid|cost|premium|deductible|settlement|payment)", "Confidential"),

    # Policy / Claim identifiers – Confidential
    (r"(?i)(claim_id|claimant_id|policy_number)", "Confidential"),

    # Dates – General
    (r"(?i)(date|_date)", "General"),

    # Location (non-PII granularity) – General
    (r"(?i)(?:^|_)(state|region|location)(?:$|_)", "General"),

    # Status / metadata – General
    (r"(?i)(?:^|_)(status|type|description|format)(?:$|_)", "General"),

    # Booleans / counts – General
    (r"(?i)(police_report|photos_provided|witness_statements)", "General"),
]

# Table-level default labels (from 06-sensitivity-labels.md)
_TABLE_DEFAULTS: Dict[str, str] = {
    "claimant_profiles": "Highly Confidential",
    "claims_history": "Confidential",
    "fraud_indicators": "Highly Confidential",
    "policy_claims_summary": "Confidential",
    "regional_statistics": "General",
}


def classify_column(
    column_name: str,
    table_name: str = "",
    data_type: str = "",
) -> str:
    """Determine the sensitivity label for a column using the rule engine.

    Args:
        column_name: Name of the column.
        table_name:  Parent table name (used for table-level defaults).
        data_type:   Column data type (reserved for future rules).

    Returns:
        Sensitivity label name (e.g. "Highly Confidential", "Confidential", "General").
    """
    # Column-level rules first
    for pattern, label in _COLUMN_RULES:
        if re.search(pattern, column_name):
            return label

    # Fall back to table-level default
    if table_name in _TABLE_DEFAULTS:
        return _TABLE_DEFAULTS[table_name]

    # Ultimate fallback
    return "General"


def classify_columns_for_table(
    table_name: str,
    columns: list,
) -> Dict[str, str]:
    """Classify all columns in a table and return {column_name: label_name}.

    Args:
        table_name: Name of the table.
        columns:    List of ``ColumnInfo`` objects from the scanner.

    Returns:
        Dict mapping column name → sensitivity label name.
    """
    result = {}
    for col in columns:
        label = classify_column(col.name, table_name, col.data_type)
        col.sensitivity_label = label
        result[col.name] = label
    return result


# ---------------------------------------------------------------------------
# (C) Code snippet — fetch MIP labels via REST (standalone example)
# ---------------------------------------------------------------------------

def example_fetch_mip_labels_rest(tenant_id: str, client_id: str, client_secret: str) -> dict:
    """Standalone example: fetch MIP sensitivity labels using REST only.

    This demonstrates the raw Graph API call without pyapacheatlas, useful
    for integrating into other tools or languages.

    Usage:
        labels = example_fetch_mip_labels_rest(
            tenant_id="840a80c0-...",
            client_id="48459702-...",
            client_secret="D.58Q~Y_..."
        )
    """
    from azure.identity import ClientSecretCredential

    cred = ClientSecretCredential(tenant_id, client_id, client_secret)
    token = cred.get_token("https://graph.microsoft.com/.default").token

    # v1.0 — newest endpoint (requires SensitivityLabels.Read.All)
    resp = requests.get(
        "https://graph.microsoft.com/v1.0/security/dataSecurityAndGovernance/sensitivityLabels",
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "InsuranceClaimsFabricScanner/1.0",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
