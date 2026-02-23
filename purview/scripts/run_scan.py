#!/usr/bin/env python3
"""
run_scan.py – Orchestrator for Purview classification via Scanning Data Plane API.

Configures custom classification rules and scan rule sets in Microsoft Purview,
then triggers a re-scan of the existing Fabric data source so that
classifications are automatically applied to existing column assets.

This is the CORRECT approach per Microsoft docs:
  - Classifications are applied BY THE SCANNER during scan execution
  - Sensitivity labels are applied by auto-labeling policies (portal config)
  - We do NOT create entities – Purview's Fabric integration already did that

Usage:
    # Discover data sources and scans (find the right names)
    python run_scan.py --discover

    # Full run: create rules + rule set + update scan + trigger
    python run_scan.py

    # Dry run (no API writes, logs what would happen)
    python run_scan.py --dry-run

    # Only create classification rules (don't trigger scan)
    python run_scan.py --no-scan

    # Print auto-labeling policy guidance
    python run_scan.py --auto-label-guide

    # Override data source / scan name from CLI
    python run_scan.py --data-source "MyFabricSource" --scan-name "Scan-Fabric-Claims-Demo"

Environment:
    All configuration via .env file (purview/scripts/.env)
    or environment variables. See fabric_scanner/config.py for details.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ensure the scripts directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fabric_scanner.config import Config, load_env, logger
from fabric_scanner.classifier import (
    configure_and_run_classification,
    create_custom_classifications,
    create_scan_rule_set,
    classify_existing_columns,
    list_data_sources,
    list_scans,
    list_classification_rules,
    list_scan_rulesets,
    print_auto_labeling_guidance,
    INSURANCE_CLASSIFICATION_RULES,
    CLASSIFICATION_TO_LABEL,
)


# ---------------------------------------------------------------------------
# Discovery mode – find data source and scan names
# ---------------------------------------------------------------------------

def discover_purview_config() -> None:
    """List all data sources and their scans in Purview.

    Use this to find the correct PURVIEW_DATA_SOURCE_NAME and
    PURVIEW_SCAN_NAME values for .env.
    """
    logger.info("=== Discovering Purview Scanning Configuration ===\n")

    # List data sources
    logger.info("Registered data sources:")
    sources = list_data_sources()
    if not sources:
        logger.warning("  No data sources found (check permissions)")
        return

    for ds in sources:
        name = ds.get("name", "unknown")
        kind = ds.get("kind", "unknown")
        props = ds.get("properties", {})
        logger.info("  [%s] %s", kind, name)
        if kind == "Fabric":
            logger.info("    Workspace: %s", props.get("workspaceId", "N/A"))
        elif "endpoint" in props:
            logger.info("    Endpoint: %s", props["endpoint"])

        # List scans for this source
        scans = list_scans(name)
        for scan in scans:
            scan_name = scan.get("name", "unknown")
            scan_kind = scan.get("kind", "unknown")
            scan_props = scan.get("properties", {})
            ruleset = scan_props.get("scanRulesetName", "N/A")
            ruleset_type = scan_props.get("scanRulesetType", "N/A")
            logger.info(
                "    Scan: %s (kind=%s, ruleset=%s [%s])",
                scan_name, scan_kind, ruleset, ruleset_type,
            )

    # List existing classification rules
    logger.info("\nExisting custom classification rules:")
    rules = list_classification_rules()
    custom_rules = [r for r in rules if r.get("kind") == "Custom"]
    if custom_rules:
        for rule in custom_rules:
            logger.info("  %s -> %s", rule.get("name"), rule.get("properties", {}).get("classificationName"))
    else:
        logger.info("  (none)")

    # List existing scan rulesets
    logger.info("\nExisting custom scan rule sets:")
    rulesets = list_scan_rulesets()
    custom_rulesets = [r for r in rulesets if r.get("scanRulesetType") == "Custom"]
    if custom_rulesets:
        for rs in custom_rulesets:
            logger.info("  %s (kind=%s)", rs.get("name"), rs.get("kind"))
    else:
        logger.info("  (none)")

    logger.info("\n" + "=" * 60)
    logger.info("Set PURVIEW_DATA_SOURCE_NAME and PURVIEW_SCAN_NAME in .env")
    logger.info("based on the values above, then run: python run_scan.py")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure Purview classification rules and trigger scan",
    )
    parser.add_argument("--data-source", help="Purview data source name (overrides .env)")
    parser.add_argument("--scan-name", help="Existing Purview scan name (overrides .env)")
    parser.add_argument("--ruleset-name", default="Contoso-Insurance-Fabric-Ruleset",
                        help="Name for the custom scan rule set")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without writing to APIs")
    parser.add_argument("--no-scan", action="store_true", help="Create rules & rule set but don't trigger scan")
    parser.add_argument("--classify-columns", action="store_true",
                        help="Directly classify existing Fabric columns (required for Fabric MSI scans)")
    parser.add_argument("--wait", action="store_true", help="Wait for scan completion after triggering")
    parser.add_argument("--discover", action="store_true",
                        help="Discover data sources and scans, then exit")
    parser.add_argument("--auto-label-guide", action="store_true",
                        help="Print auto-labeling policy setup guide and exit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable DEBUG logging")
    parser.add_argument("--output-dir", default=".", help="Directory for report output files")

    args = parser.parse_args()

    # --- Logging ---
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(name)-28s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )

    # --- Load .env and populate Config ---
    load_env()
    Config.reload()
    if args.data_source:
        Config.data_source_name = args.data_source
    if args.scan_name:
        Config.scan_name = args.scan_name
    Config.dry_run = args.dry_run

    # --- Auto-labeling guide (no auth needed) ---
    if args.auto_label_guide:
        print_auto_labeling_guidance()
        return 0

    # --- Validate auth config ---
    Config.validate()

    logger.info("=" * 60)
    logger.info("Purview Classification Pipeline (Scanning Data Plane API)")
    logger.info("=" * 60)
    logger.info("  Purview account : %s", Config.purview_account)
    logger.info("  Data source     : %s", Config.data_source_name or "(will discover)")
    logger.info("  Scan name       : %s", Config.scan_name or "(will discover)")
    logger.info("  Rule set name   : %s", args.ruleset_name)
    logger.info("  Dry run         : %s", Config.dry_run)
    logger.info("  Trigger scan    : %s", not args.no_scan)
    logger.info("=" * 60)

    # --- Discovery mode ---
    if args.discover:
        discover_purview_config()
        return 0

    # --- Validate data source and scan name ---
    if not Config.data_source_name or not Config.scan_name:
        logger.error(
            "PURVIEW_DATA_SOURCE_NAME and PURVIEW_SCAN_NAME are required.\n"
            "Run 'python run_scan.py --discover' to find the correct values,\n"
            "then set them in .env or pass via --data-source / --scan-name."
        )
        return 1

    t0 = time.time()

    # --- Run the classification pipeline ---
    logger.info("")
    logger.info("Classification rules to create: %d", len(INSURANCE_CLASSIFICATION_RULES))
    for rule in INSURANCE_CLASSIFICATION_RULES:
        logger.info(
            "  %-45s -> %s",
            rule["classification_name"], rule["sensitivity_label"],
        )

    summary = configure_and_run_classification(
        data_source_name=Config.data_source_name,
        scan_name=Config.scan_name,
        rule_set_name=args.ruleset_name,
        trigger_scan=not args.no_scan,
        wait_for_completion=args.wait,
    )

    # --- Direct column classification (Fabric MSI scans) ---
    if args.classify_columns:
        logger.info("")
        logger.info("STEP 2: Directly classifying existing Fabric columns")
        logger.info("-" * 50)
        logger.info("(Fabric MSI scans don't apply classification rules at scan time)")
        classif_summary = classify_existing_columns()
        summary["direct_classification"] = classif_summary

    # --- Report ---
    elapsed = time.time() - t0
    logger.info("")
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE  (%.1fs)", elapsed)
    logger.info("  Classification rules created : %d", len(summary["classification_rules_created"]))
    logger.info("  Scan rule set created        : %s", summary["scan_rule_set_created"])
    logger.info("  Scan config updated          : %s", summary["scan_updated"])
    logger.info("  Scan triggered               : %s", summary["scan_triggered"])
    if summary.get("scan_run_id"):
        logger.info("  Scan run ID                  : %s", summary["scan_run_id"])
    if summary.get("scan_status"):
        logger.info("  Scan final status            : %s", summary["scan_status"])
    logger.info("=" * 60)

    # Write report
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "classification_report.json"
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info("Report written to %s", report_path)

    # Next steps
    if not args.no_scan and summary.get("scan_triggered"):
        logger.info("")
        logger.info("NEXT STEPS:")
        logger.info("  1. Wait for scan to complete (check in Purview portal)")
        logger.info("  2. Verify classifications on columns in Purview Data Map")
        logger.info("  3. Configure auto-labeling policies:")
        logger.info("     python run_scan.py --auto-label-guide")
    elif args.no_scan:
        logger.info("")
        logger.info("NEXT STEPS:")
        logger.info("  1. Run without --no-scan to trigger the scan")
        logger.info("  2. Or trigger manually in Purview portal")

    return 0


if __name__ == "__main__":
    sys.exit(main())