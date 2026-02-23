#!/usr/bin/env python3
"""
test_fabric_scanner.py – Tests and example payloads for the Fabric Scanner.

Covers:
    (A) Entity + classification registration logic
    (B) Example Atlas v2 API payloads (snapshot assertions)
    (C) MIP label fetch code snippets (mocked)
    (D) Incremental scanning / idempotent upsert patterns
    (E) End-to-end offline pipeline test

Run:
    cd purview/scripts
    python -m pytest test_fabric_scanner.py -v
    # or
    python test_fabric_scanner.py
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

# Ensure parent dir is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fabric_scanner.config import Config
from fabric_scanner.scanner import ColumnInfo, FabricItem, TableInfo, _KNOWN_SCHEMAS
from fabric_scanner.mip_labels import (
    classify_column,
    classify_columns_for_table,
)
from fabric_scanner.classifier import (
    CLASSIFICATION_PREFIX,
    FABRIC_COLUMN_TYPE,
    LAKEHOUSE_TABLE_TYPE,
    LABEL_TO_CLASSIFICATION,
    apply_column_classifications,
    create_classification_types,
    create_entity_types,
    get_classification_typedef_payload,
    get_entity_typedef_payload,
    incremental_scan_and_classify,
    register_tables_and_columns,
    _qualified_name,
)


# ---------------------------------------------------------------------------
# Helpers – build sample FabricItems from known schemas
# ---------------------------------------------------------------------------

def _build_sample_items() -> List[FabricItem]:
    """Create FabricItems from the known schemas for testing."""
    tables = []
    for tbl_name, schema in _KNOWN_SCHEMAS.items():
        columns = [
            ColumnInfo(
                name=col["name"],
                data_type=col["data_type"],
                ordinal_position=col.get("ordinal", i + 1),
            )
            for i, col in enumerate(schema)
        ]
        tables.append(
            TableInfo(
                name=tbl_name,
                table_type="Managed",
                format="delta",
                location=None,
                item_id="test-lakehouse-id",
                columns=columns,
            )
        )

    return [
        FabricItem(
            id="test-lakehouse-id",
            display_name="InsuranceLakehouse",
            item_type="Lakehouse",
            tables=tables,
        )
    ]


# ============================================================================
# (B) Test: Atlas v2 API Payload Structure
# ============================================================================

class TestAtlasPayloads(unittest.TestCase):
    """Verify the raw Atlas v2 JSON payloads have the expected shape."""

    def test_classification_typedefs_payload(self):
        payload = get_classification_typedef_payload()
        self.assertIn("classificationDefs", payload)
        cdefs = payload["classificationDefs"]
        self.assertEqual(len(cdefs), 5)

        names = {c["name"] for c in cdefs}
        self.assertIn(f"{CLASSIFICATION_PREFIX}Confidential", names)
        self.assertIn(f"{CLASSIFICATION_PREFIX}Highly_Confidential", names)
        self.assertIn(f"{CLASSIFICATION_PREFIX}General", names)
        self.assertIn(f"{CLASSIFICATION_PREFIX}Public", names)
        self.assertIn(f"{CLASSIFICATION_PREFIX}Personal", names)

        # Each should target DataSet
        for cdef in cdefs:
            self.assertIn("DataSet", cdef["entityTypes"])

    def test_entity_typedefs_payload(self):
        payload = get_entity_typedef_payload()

        self.assertIn("entityDefs", payload)
        self.assertIn("relationshipDefs", payload)

        entity_names = {e["name"] for e in payload["entityDefs"]}
        self.assertIn(LAKEHOUSE_TABLE_TYPE, entity_names)
        self.assertIn(FABRIC_COLUMN_TYPE, entity_names)

        # Relationship
        rel = payload["relationshipDefs"][0]
        self.assertEqual(rel["relationshipCategory"], "COMPOSITION")
        self.assertEqual(rel["endDef2"]["type"], FABRIC_COLUMN_TYPE)

    def test_payload_serializable(self):
        """Payloads should be JSON-serializable (could be POSTed via REST)."""
        json.dumps(get_classification_typedef_payload())
        json.dumps(get_entity_typedef_payload())


# ============================================================================
# (C) Test: MIP Sensitivity Label Classification Rules
# ============================================================================

class TestMIPClassification(unittest.TestCase):
    """Test the column-level sensitivity classification rules engine."""

    def test_pii_columns_highly_confidential(self):
        """PII columns (SSN, email, phone, etc.) → Highly Confidential"""
        pii_names = ["ssn", "social_security_number", "email", "email_address",
                      "phone_number", "date_of_birth"]
        for col_name in pii_names:
            label = classify_column(col_name, "any_table", "string")
            self.assertEqual(label, "Highly Confidential",
                             f"Expected 'Highly Confidential' for {col_name}, got {label}")

    def test_financial_columns_confidential(self):
        """Financial columns (claim_amount, payment, etc.) → Confidential"""
        fin_names = ["total_claim_amount", "payment_amount", "premium", "settlement_value"]
        for col_name in fin_names:
            label = classify_column(col_name, "any_table", "double")
            self.assertEqual(label, "Confidential",
                             f"Expected 'Confidential' for {col_name}, got {label}")

    def test_id_columns_confidential(self):
        """ID columns (claim_id, policy_number) → Confidential"""
        id_names = ["claim_id", "policy_number", "claimant_id"]
        for col_name in id_names:
            label = classify_column(col_name, "any_table", "string")
            self.assertEqual(label, "Confidential",
                             f"Expected 'Confidential' for {col_name}, got {label}")

    def test_general_columns(self):
        """Non-sensitive columns should get ≤ General"""
        harmless = ["region", "state"]
        for col_name in harmless:
            label = classify_column(col_name, "regional_statistics", "string")
            self.assertEqual(label, "General",
                             f"Expected 'General' for {col_name}, got {label}")

    def test_table_level_fallback(self):
        """Unmatched columns should inherit table-level default."""
        # claimant_profiles table → Highly Confidential default
        label = classify_column("some_unknown_field", "claimant_profiles", "string")
        self.assertEqual(label, "Highly Confidential")

        # regional_statistics → General default
        label = classify_column("some_unknown_field", "regional_statistics", "string")
        self.assertEqual(label, "General")

    def test_classify_columns_for_table(self):
        """Bulk classification should set sensitivity_label on each ColumnInfo."""
        columns = [
            ColumnInfo(name="email", data_type="string"),
            ColumnInfo(name="claim_amount", data_type="double"),
            ColumnInfo(name="region", data_type="string"),
        ]
        classify_columns_for_table("claims_history", columns)

        # email → Highly Confidential
        self.assertEqual(columns[0].sensitivity_label, "Highly Confidential")
        # claim_amount → Confidential
        self.assertEqual(columns[1].sensitivity_label, "Confidential")
        # region → General or Confidential (table default is Confidential)
        self.assertIn(columns[2].sensitivity_label, ["General", "Confidential"])


# ============================================================================
# (A) Test: Entity Registration (dry-run)
# ============================================================================

class TestEntityRegistration(unittest.TestCase):
    """Test entity creation logic using dry-run mode."""

    def setUp(self):
        Config.dry_run = True
        Config.fabric_workspace_id = "test-workspace-123"
        Config.purview_account = "test-purview"

    def test_qualified_name_table(self):
        qn = _qualified_name("ws-1", "MyLakehouse", "claims_history")
        self.assertEqual(qn, "fabric://ws-1/MyLakehouse/claims_history")

    def test_qualified_name_column(self):
        qn = _qualified_name("ws-1", "MyLakehouse", "claims_history", "claim_id")
        self.assertEqual(qn, "fabric://ws-1/MyLakehouse/claims_history#claim_id")

    def test_qualified_names_unique(self):
        """All qualified names across all tables/columns should be unique."""
        items = _build_sample_items()
        qns = set()
        for item in items:
            for table in item.tables:
                tqn = _qualified_name("ws", item.display_name, table.name)
                self.assertNotIn(tqn, qns, f"Duplicate qn: {tqn}")
                qns.add(tqn)
                for col in table.columns:
                    cqn = _qualified_name("ws", item.display_name, table.name, col.name)
                    self.assertNotIn(cqn, qns, f"Duplicate qn: {cqn}")
                    qns.add(cqn)

    @patch("fabric_scanner.classifier.get_purview_client")
    def test_register_dry_run(self, mock_client_factory):
        """Dry-run registration should return guid_map without API calls."""
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client

        items = _build_sample_items()
        guid_map = register_tables_and_columns(mock_client, items)

        # Should have entries for tables + columns
        self.assertGreater(len(guid_map), 0)

        # Table entries
        table_qns = [k for k in guid_map if "#" not in k]
        self.assertEqual(len(table_qns), len(_KNOWN_SCHEMAS))

        # No API calls in dry-run
        mock_client.upload_entities.assert_not_called()


# ============================================================================
# (D) Test: Incremental / Idempotent Scanning
# ============================================================================

class TestIncrementalScanning(unittest.TestCase):
    """Verify that the scan pipeline is idempotent (safe to re-run)."""

    def setUp(self):
        Config.dry_run = True
        Config.fabric_workspace_id = "test-workspace-123"
        Config.purview_account = "test-purview"

    @patch("fabric_scanner.classifier.get_purview_token", return_value="fake-token")
    @patch("fabric_scanner.classifier._create_relationship_typedef_rest")
    def test_incremental_scan_idempotent(self, mock_rel_rest, mock_token):
        """Running incremental_scan_and_classify twice should produce the
        same output (idempotent)."""
        mock_client = MagicMock()

        items = _build_sample_items()
        for item in items:
            for table in item.tables:
                classify_columns_for_table(table.name, table.columns)

        result1 = incremental_scan_and_classify(mock_client, items)
        result2 = incremental_scan_and_classify(mock_client, items)

        self.assertEqual(result1["entities_registered"], result2["entities_registered"])
        self.assertEqual(
            result1["classifications_applied"],
            result2["classifications_applied"],
        )

    def test_qualified_names_deterministic(self):
        """Same input should always produce same qualified names."""
        items1 = _build_sample_items()
        items2 = _build_sample_items()

        qns1 = set()
        qns2 = set()
        for items, qns in [(items1, qns1), (items2, qns2)]:
            for item in items:
                for table in item.tables:
                    qns.add(_qualified_name("ws", item.display_name, table.name))
                    for col in table.columns:
                        qns.add(_qualified_name("ws", item.display_name, table.name, col.name))

        self.assertEqual(qns1, qns2)


# ============================================================================
# (E) Test: End-to-end offline pipeline
# ============================================================================

class TestEndToEndOffline(unittest.TestCase):
    """Full pipeline test in offline + dry-run mode."""

    def setUp(self):
        Config.dry_run = True
        Config.fabric_workspace_id = "test-workspace-e2e"
        Config.purview_account = "test-purview-e2e"

    @patch("fabric_scanner.classifier.get_purview_token", return_value="fake-token")
    @patch("fabric_scanner.classifier._create_relationship_typedef_rest")
    def test_full_pipeline_offline_dry_run(self, mock_rel_rest, mock_token):
        """Run the full pipeline: scan → classify → register (all dry-run)."""
        mock_client = MagicMock()

        # Step 1: Build items from known schemas (offline)
        items = _build_sample_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0].tables), 5)

        # Step 2: Apply column classification rules
        for item in items:
            for table in item.tables:
                classify_columns_for_table(table.name, table.columns)

        # Verify some known classifications
        claims_table = next(t for t in items[0].tables if t.name == "claims_history")
        email_col = next((c for c in claims_table.columns if c.name == "email"), None)
        if email_col:
            self.assertEqual(email_col.sensitivity_label, "Highly Confidential")

        claim_amount_col = next(
            (c for c in claims_table.columns if c.name == "total_claim_amount"), None
        )
        if claim_amount_col:
            self.assertEqual(claim_amount_col.sensitivity_label, "Confidential")

        # Step 3: Register in Purview (dry-run)
        summary = incremental_scan_and_classify(mock_client, items)

        # Should have registered entities for all tables + columns
        total_tables = sum(len(it.tables) for it in items)
        total_cols = sum(len(t.columns) for it in items for t in it.tables)
        self.assertEqual(summary["entities_registered"], total_tables + total_cols)

        # Classification errors should be 0 (dry-run doesn't fail)
        self.assertEqual(summary["classification_errors"], 0)

    def test_all_known_schema_columns_are_classified(self):
        """Every column in every known schema table should receive a
        sensitivity classification."""
        items = _build_sample_items()
        for item in items:
            for table in item.tables:
                classify_columns_for_table(table.name, table.columns)
                for col in table.columns:
                    self.assertIsNotNone(
                        col.sensitivity_label,
                        f"Column {table.name}.{col.name} has no sensitivity label",
                    )
                    self.assertIn(
                        col.sensitivity_label,
                        LABEL_TO_CLASSIFICATION,
                        f"Unknown label '{col.sensitivity_label}' for {table.name}.{col.name}",
                    )


# ============================================================================
# (B) Bonus: Print example Atlas v2 payloads
# ============================================================================

class TestPrintExamplePayloads(unittest.TestCase):
    """Print example API payloads for documentation (deliverable B)."""

    def test_print_classification_payload(self):
        """Print the classification typedef payload."""
        payload = get_classification_typedef_payload()
        print("\n=== Atlas v2 Classification TypeDefs Payload ===")
        print(json.dumps(payload, indent=2))

    def test_print_entity_payload(self):
        """Print the entity typedef payload."""
        payload = get_entity_typedef_payload()
        print("\n=== Atlas v2 Entity TypeDefs Payload ===")
        print(json.dumps(payload, indent=2))

    def test_print_entity_upload_payload(self):
        """Print a sample entity upload payload (single table + 2 columns)."""
        payload = {
            "entities": [
                {
                    "typeName": LAKEHOUSE_TABLE_TYPE,
                    "attributes": {
                        "qualifiedName": "fabric://ws-123/InsuranceLakehouse/claims_history",
                        "name": "claims_history",
                        "format": "delta",
                        "tableType": "Managed",
                    },
                    "guid": "-1",
                },
                {
                    "typeName": FABRIC_COLUMN_TYPE,
                    "attributes": {
                        "qualifiedName": "fabric://ws-123/InsuranceLakehouse/claims_history#claim_id",
                        "name": "claim_id",
                        "data_type": "string",
                        "ordinal_position": 1,
                    },
                    "guid": "-2",
                    "relationshipAttributes": {
                        "table": {"guid": "-1", "typeName": LAKEHOUSE_TABLE_TYPE},
                    },
                    "classifications": [
                        {"typeName": f"{CLASSIFICATION_PREFIX}Confidential"}
                    ],
                },
                {
                    "typeName": FABRIC_COLUMN_TYPE,
                    "attributes": {
                        "qualifiedName": "fabric://ws-123/InsuranceLakehouse/claims_history#email",
                        "name": "email",
                        "data_type": "string",
                        "ordinal_position": 2,
                    },
                    "guid": "-3",
                    "relationshipAttributes": {
                        "table": {"guid": "-1", "typeName": LAKEHOUSE_TABLE_TYPE},
                    },
                    "classifications": [
                        {"typeName": f"{CLASSIFICATION_PREFIX}Highly_Confidential"}
                    ],
                },
            ]
        }
        print("\n=== Atlas v2 Entity Bulk Upload Payload (example) ===")
        print(json.dumps(payload, indent=2))

    def test_print_classify_entity_payload(self):
        """Print the payload for the classify_entity REST call:
        POST /catalog/api/atlas/v2/entity/guid/{guid}/classifications
        """
        payload = {
            "url": "POST https://{purview}.purview.azure.com/catalog/api/atlas/v2/entity/guid/{column_guid}/classifications",
            "body": [
                {
                    "typeName": f"{CLASSIFICATION_PREFIX}Highly_Confidential",
                    "attributes": {
                        "mip_label_id": "a5b6c7d8-e9f0-1234-abcd-ef0123456789",
                    },
                }
            ],
        }
        print("\n=== Atlas v2 Classify Entity Payload (column-level) ===")
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
