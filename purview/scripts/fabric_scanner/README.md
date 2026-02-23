# Fabric Scanner — Automated Metadata Discovery & Purview Classification

## Purpose

The `fabric_scanner` package automates the end-to-end process of **discovering metadata in a Microsoft Fabric workspace** and **registering it in Microsoft Purview with column-level sensitivity classifications**. This bridges the gap between Fabric's built-in governance and Purview's unified data catalog, ensuring that every lakehouse table, warehouse table, and column is:

1. **Discovered** via the Fabric REST API
2. **Classified** with sensitivity labels (mapped from Microsoft Information Protection)
3. **Registered** in Purview's Data Map with custom Atlas entity types and classifications

This is particularly important for the Insurance Claims Multi-Agent application, where tables contain PII (names, license plates, SSNs), financial data (claim amounts, settlements), and fraud indicators — all of which require proper governance labeling.

---

## Architecture

```
┌────────────────────────────┐
│     run_scan.py            │   ← CLI orchestrator (entry point)
│     (purview/scripts/)     │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────┐
│                    fabric_scanner package                       │
├────────────────┬───────────────┬───────────────┬───────────────┤
│  config.py     │  scanner.py   │ mip_labels.py │ classifier.py │
│                │               │               │               │
│ • .env loader  │ • Fabric REST │ • Graph API   │ • Atlas v2    │
│ • AAD auth     │   API calls   │   MIP label   │   type defs   │
│ • Token helper │ • Lakehouse & │   fetching    │ • Entity      │
│ • Retry logic  │   Warehouse   │ • Rule engine │   registration│
│ • Purview      │   discovery   │   for column  │ • Column-level│
│   client       │ • Table &     │   → label     │   classifi-   │
│                │   column      │   mapping     │   cation      │
│                │   schemas     │               │               │
└────────────────┴───────────────┴───────────────┴───────────────┘
```

### Module Responsibilities

| Module | Description |
|--------|-------------|
| **config.py** | Shared configuration, `.env` loading, AAD token acquisition (Fabric, Purview, Graph APIs), `PurviewClient` factory, exponential-backoff retry decorator |
| **scanner.py** | Queries the Fabric REST API to list lakehouses, warehouses, tables, and column schemas; includes fallback to known schemas for the insurance-claims domain |
| **mip_labels.py** | Fetches Microsoft Information Protection (MIP) sensitivity labels from Microsoft Graph and applies a rule engine that maps column names to sensitivity labels based on insurance-domain patterns |
| **classifier.py** | Creates custom Atlas type definitions (entity types + classification types) in Purview and registers Fabric tables/columns as entities with column-level sensitivity classifications via `pyapacheatlas` |

---

## How It Works

### Step 1 — Scan Fabric Workspace
The scanner queries the Fabric REST API to discover all lakehouses and warehouses in the configured workspace. For each lakehouse, it retrieves table metadata and column schemas (via SQL analytics endpoint or known-schema fallback).

### Step 2 — Classify Columns
Each column is run through a rule engine (`mip_labels.py`) that pattern-matches column names against insurance-domain rules:

| Pattern | Label |
|---------|-------|
| `name`, `ssn`, `dob`, `email`, `license_plate` | **Highly Confidential** |
| `fraud`, `risk_score`, `indicator` | **Highly Confidential** |
| `amount`, `cost`, `premium`, `claim_id` | **Confidential** |
| `date`, `status`, `state`, `description` | **General** |

Table-level defaults are also applied (e.g., `claimant_profiles` → Highly Confidential).

### Step 3 — Register in Purview
Custom Atlas entity types (`fabric_lakehouse_table`, `fabric_warehouse_table`, `fabric_column`) and classification types (`MIP_Personal`, `MIP_Confidential`, `MIP_Highly_Confidential`, etc.) are registered idempotently in Purview. Each discovered table and column is then uploaded as an entity with the appropriate classifications attached.

---

## Prerequisites

- **Python 3.10+**
- **Azure Service Principal** with permissions for:
  - Fabric REST API (`https://api.fabric.microsoft.com/.default`)
  - Purview Data Map (`https://purview.azure.net/.default`)
  - Microsoft Graph (`InformationProtectionPolicy.Read.All`) — for MIP labels
- **Microsoft Purview** account with Data Map enabled
- **Microsoft Fabric** workspace with lakehouses/warehouses

### Python Dependencies

- `azure-identity`
- `pyapacheatlas`
- `requests`
- `pyodbc` (optional — for direct SQL analytics endpoint queries)

---

## Configuration

All settings are loaded from `purview/scripts/.env` (see `.env.example`):

```dotenv
# Required
PURVIEW_ACCOUNT=your-purview-account-name
PURVIEW_COLLECTION=your-collection-id
FABRIC_WORKSPACE_ID=your-fabric-workspace-guid
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

# Optional
DRY_RUN=false
ATLAS_BATCH_SIZE=25
```

---

## Usage

Run from the `purview/scripts/` directory:

```bash
# Full scan → classify → register in Purview
python run_scan.py

# Dry run — logs all actions without making API writes
python run_scan.py --dry-run

# Offline mode — skip Fabric API calls, use known schemas only
python run_scan.py --offline

# Override workspace or Purview account from the CLI
python run_scan.py --workspace-id <guid> --purview-account <name>

# Verbose output
python run_scan.py --dry-run --verbose
```

---

## Insurance-Domain Classification Rules

The rule engine in `mip_labels.py` encodes domain-specific patterns for the five lakehouse tables used by the Claims Multi-Agent system:

| Table | Default Label | Key Sensitive Columns |
|-------|---------------|----------------------|
| `claims_history` | Confidential | `claimant_name` (HC), `license_plate` (HC), `fraud_flag` (HC), `estimated_damage` (C) |
| `claimant_profiles` | Highly Confidential | `name` (HC), `risk_score` (HC), `policy_number` (C) |
| `fraud_indicators` | Highly Confidential | `indicator_type` (HC), `severity` (C) |
| `policy_claims_summary` | Confidential | `total_amount` (C), `policy_number` (C) |
| `regional_statistics` | General | `fraud_rate` (HC), `avg_claim_amount` (C) |

*HC = Highly Confidential, C = Confidential*

---

## Custom Atlas Types Created

### Entity Types
- `fabric_lakehouse_table` — extends `DataSet`, adds `format`, `lakehouseId`, `tableType`, `location`
- `fabric_warehouse_table` — extends `DataSet`, adds `warehouseId`, `tableType`
- `fabric_column` — extends `DataSet`, adds `data_type`, `ordinal_position`, `is_nullable`

### Classification Types
- `MIP_Personal` — Non-business data
- `MIP_Public` — Approved for public sharing
- `MIP_General` — Standard business data
- `MIP_Confidential` — Sensitive business data
- `MIP_Highly_Confidential` — PII, fraud data, strictest controls

### Relationships
- `fabric_table_columns` — Composition relationship linking tables to their columns

---

## Related Documentation

- [Purview Governance Setup](../../README.md) — parent guide for all Purview configuration
- [Sensitivity Labels](../../06-sensitivity-labels.md) — label definitions and publishing policies
- [DLP Policies](../../07-dlp-policies.md) — Data Loss Prevention for Fabric
- [Lineage REST API](../../08-lineage-rest-api.md) — custom lineage via Atlas API
- [Fabric Metadata Scanning](https://github.com/microsoft/Fabric-metadata-scanning) — Microsoft reference implementation
- [pyapacheatlas](https://github.com/wjohnson/pyapacheatlas) — Python SDK for Apache Atlas / Purview
