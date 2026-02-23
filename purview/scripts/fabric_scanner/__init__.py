"""Fabric Lakehouse/Warehouse scanner with Purview column-level classification.

Uses the Purview Scanning Data Plane API (correct approach):
  - Classifications are applied BY THE SCANNER via classification rules
  - Sensitivity labels are applied by auto-labeling policies (portal config)
  - No new entities created – uses Purview's native Fabric integration

Modules:
    config       – Shared configuration & auth helpers
    scanner      – Fabric REST API metadata discovery (tables, columns)
    mip_labels   – Microsoft Information Protection sensitivity label fetcher
    classifier   – Scanning Data Plane API: classification rules, scan rule sets
"""
