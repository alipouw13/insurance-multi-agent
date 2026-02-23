#!/usr/bin/env python3
"""Clean up duplicate entities created by the old (incorrect) pipeline.

The previous approach registered ~135 custom entities (tables + columns)
using custom type definitions (fabric_lakehouse_table, fabric_column, etc.)
with qualifiedName pattern: fabric://{workspace_id}/{lakehouse}/{table}[#{column}]

These are DUPLICATES of the entities that Purview's native Fabric scan
already discovered (e.g. claims_history, claimant_profiles, etc.).

This script:
  1. Finds all entities with qualifiedName starting with "fabric://"
  2. Deletes them via Atlas v2 API
  3. Optionally cleans up the custom type definitions (MIP_*, fabric_*)

Usage:
    python cleanup_duplicates.py                   # Preview (dry run)
    python cleanup_duplicates.py --execute          # Actually delete
    python cleanup_duplicates.py --execute --types  # Also remove custom type defs
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fabric_scanner.config import Config, load_env, get_purview_token, logger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-28s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

import requests

# Custom entity type names from the old approach
OLD_ENTITY_TYPES = [
    "fabric_lakehouse_table",
    "fabric_warehouse_table",
    "fabric_column",
]

# Custom classification names from the old approach
OLD_CLASSIFICATION_TYPES = [
    "MIP_Personal",
    "MIP_Public",
    "MIP_General",
    "MIP_Confidential",
    "MIP_Highly_Confidential",
]

# Relationship type from old approach
OLD_RELATIONSHIP_TYPES = [
    "fabric_table_columns",
]


def _catalog_url(path: str) -> str:
    return f"https://{Config.purview_account}.purview.azure.com/catalog/api/atlas/v2/{path}"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_purview_token()}",
        "Content-Type": "application/json",
    }


def find_duplicate_entities() -> list[dict]:
    """Search for entities created by the old pipeline using DSL query."""
    all_entities = []

    for type_name in OLD_ENTITY_TYPES:
        logger.info("Searching for entities of type '%s'...", type_name)

        # Use basic search to find entities by type
        url = (
            f"https://{Config.purview_account}.purview.azure.com"
            f"/catalog/api/search/query?api-version=2022-08-01-preview"
        )
        payload = {
            "keywords": "*",
            "filter": {
                "and": [
                    {"entityType": type_name},
                ]
            },
            "limit": 1000,
        }

        # Try the search/query endpoint first
        resp = requests.post(url, headers=_headers(), json=payload, timeout=60)

        if resp.status_code == 200:
            data = resp.json()
            entities = data.get("value", [])
            logger.info("  Found %d entities of type '%s'", len(entities), type_name)
            all_entities.extend(entities)
        else:
            logger.warning(
                "  Search returned %d: %s", resp.status_code, resp.text[:200]
            )

            # Fallback: try DSL query
            dsl_url = (
                f"https://{Config.purview_account}.purview.azure.com"
                f"/catalog/api/search/query?api-version=2022-08-01-preview"
            )
            dsl_payload = {
                "keywords": f"fabric://",
                "filter": {"entityType": type_name},
                "limit": 1000,
            }
            resp2 = requests.post(dsl_url, headers=_headers(), json=dsl_payload, timeout=60)
            if resp2.status_code == 200:
                entities = resp2.json().get("value", [])
                logger.info("  Found %d entities via DSL", len(entities))
                all_entities.extend(entities)

    # Filter to only entities with fabric:// QN (old pipeline duplicates)
    # Native Fabric entities have QNs starting with https://app.fabric.microsoft.com
    duplicates = [
        e for e in all_entities
        if e.get("qualifiedName", "").startswith("fabric://")
    ]
    logger.info(
        "Found %d duplicate entities (fabric:// QN) out of %d total",
        len(duplicates), len(all_entities),
    )
    return duplicates


def delete_entities(entities: list[dict], execute: bool = False) -> dict:
    """Delete entities by GUID."""
    stats = {"deleted": 0, "errors": 0, "skipped": 0}

    # Delete columns first (children), then tables (parents)
    columns = [e for e in entities if e.get("entityType") in ("fabric_column",)]
    tables = [e for e in entities if e.get("entityType") not in ("fabric_column",)]

    for entity in columns + tables:
        guid = entity.get("id") or entity.get("guid")
        name = entity.get("name", entity.get("qualifiedName", "unknown"))
        entity_type = entity.get("entityType", "unknown")

        if not guid:
            logger.warning("  No GUID for entity: %s", name)
            stats["skipped"] += 1
            continue

        if not execute:
            logger.info("  [DRY RUN] Would delete %s '%s' (guid=%s)", entity_type, name, guid)
            stats["deleted"] += 1
            continue

        url = _catalog_url(f"entity/guid/{guid}")
        resp = requests.delete(url, headers=_headers(), timeout=30)

        if resp.status_code in (200, 204):
            logger.info("  Deleted %s '%s' (guid=%s)", entity_type, name, guid)
            stats["deleted"] += 1
        elif resp.status_code == 404:
            logger.info("  Already gone: %s '%s'", entity_type, name)
            stats["skipped"] += 1
        else:
            logger.error(
                "  Failed to delete %s '%s': %s %s",
                entity_type, name, resp.status_code, resp.text[:200],
            )
            stats["errors"] += 1

        # Rate limiting
        time.sleep(0.2)

    return stats


def delete_type_definitions(execute: bool = False) -> dict:
    """Remove the custom type definitions created by the old pipeline."""
    stats = {"deleted": 0, "errors": 0, "skipped": 0}

    # Delete relationship types first, then entity types, then classification types
    for rel_name in OLD_RELATIONSHIP_TYPES:
        _delete_one_typedef("relationshipDefs", rel_name, execute, stats)

    for et_name in OLD_ENTITY_TYPES:
        _delete_one_typedef("entityDefs", et_name, execute, stats)

    for ct_name in OLD_CLASSIFICATION_TYPES:
        _delete_one_typedef("classificationDefs", ct_name, execute, stats)

    return stats


def _delete_one_typedef(
    def_category: str, type_name: str, execute: bool, stats: dict
) -> None:
    """Delete a single type definition."""
    if not execute:
        logger.info("  [DRY RUN] Would delete %s/%s", def_category, type_name)
        stats["deleted"] += 1
        return

    # Get current typedefs to find the one we want
    url = _catalog_url(f"types/typedef/name/{type_name}")
    resp = requests.get(url, headers=_headers(), timeout=30)

    if resp.status_code == 404:
        logger.info("  Type '%s' not found (already removed)", type_name)
        stats["skipped"] += 1
        return

    if resp.status_code != 200:
        logger.warning("  Could not look up type '%s': %s", type_name, resp.status_code)
        stats["errors"] += 1
        return

    # Delete the type definition
    del_url = _catalog_url("types/typedefs")
    type_def = resp.json()

    # Build the delete payload based on category
    if def_category == "classificationDefs":
        payload = {"classificationDefs": [type_def]}
    elif def_category == "entityDefs":
        payload = {"entityDefs": [type_def]}
    elif def_category == "relationshipDefs":
        payload = {"relationshipDefs": [type_def]}
    else:
        stats["errors"] += 1
        return

    resp = requests.delete(del_url, headers=_headers(), json=payload, timeout=30)

    if resp.status_code in (200, 204):
        logger.info("  Deleted type '%s'", type_name)
        stats["deleted"] += 1
    else:
        logger.error(
            "  Failed to delete type '%s': %s %s",
            type_name, resp.status_code, resp.text[:200],
        )
        stats["errors"] += 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean up duplicate entities from the old Purview pipeline"
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually delete entities (default is dry-run preview)",
    )
    parser.add_argument(
        "--types", action="store_true",
        help="Also delete custom type definitions (MIP_*, fabric_*)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    load_env()
    Config.reload()
    Config.validate()

    logger.info("=" * 60)
    logger.info("Cleanup: Remove duplicate entities from old pipeline")
    logger.info("=" * 60)
    logger.info("  Purview account: %s", Config.purview_account)
    logger.info("  Mode: %s", "EXECUTE (will delete!)" if args.execute else "DRY RUN (preview only)")
    logger.info("=" * 60)

    if args.execute:
        logger.warning("⚠  EXECUTE mode – entities WILL be deleted!")
        logger.warning("Press Ctrl+C within 5 seconds to abort...")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Aborted.")
            return 0

    # Step 1: Find duplicate entities
    logger.info("\nStep 1: Searching for duplicate entities...")
    entities = find_duplicate_entities()
    logger.info("Found %d entities to clean up", len(entities))

    if not entities:
        logger.info("Nothing to clean up!")
        if not args.types:
            return 0

    # Step 2: Delete entities
    if entities:
        logger.info("\nStep 2: Deleting entities...")
        entity_stats = delete_entities(entities, execute=args.execute)
        logger.info(
            "Entity cleanup: %d deleted, %d errors, %d skipped",
            entity_stats["deleted"], entity_stats["errors"], entity_stats["skipped"],
        )

    # Step 3: Optionally delete type definitions
    if args.types:
        logger.info("\nStep 3: Deleting custom type definitions...")
        logger.info("  (Will fail if any entities of these types still exist)")
        type_stats = delete_type_definitions(execute=args.execute)
        logger.info(
            "Type cleanup: %d deleted, %d errors, %d skipped",
            type_stats["deleted"], type_stats["errors"], type_stats["skipped"],
        )

    logger.info("\n" + "=" * 60)
    if not args.execute:
        logger.info("DRY RUN complete. Rerun with --execute to actually delete.")
    else:
        logger.info("Cleanup complete.")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
