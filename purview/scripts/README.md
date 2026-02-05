# Purview Scripts

Python scripts for managing Microsoft Purview data governance for the Insurance Claims Multi-Agent application.

## Scripts

| Script | Description |
|--------|-------------|
| [create_lineage.py](create_lineage.py) | Creates complete lineage: Storage/Cosmos → Lakehouse → Fabric Data Agent → Foundry Agents → Cosmos DB |
| [verify_lineage.py](verify_lineage.py) | Verifies lineage relationships exist |
| [export_catalog.py](export_catalog.py) | Exports Unified Catalog to JSON for backup |

## Lineage Created

The `create_lineage.py` script creates the following lineage:

```
DATA INGESTION LAYER
├── Azure Storage (insurance-documents/) → Lakehouse (claims_history, claimant_profiles, policy_claims_summary)
└── Cosmos DB (token-usage) → Lakehouse (claimant_profiles)

FABRIC DATA AGENT LAYER
└── Lakehouse Tables → Fabric Data Agent (Claims Data Analyst)

FOUNDRY AGENT LAYER
├── Fabric Data Agent → Foundry Claims Data Analyst Agent
├── Content Understanding + Storage → Foundry Claim Assessor Agent
├── Lakehouse (fraud_indicators) → Foundry Risk Analyst Agent
├── Storage → Foundry Policy Checker Agent
├── Specialist Agents → Foundry Supervisor Agent
└── Supervisor Agent → Cosmos DB (agent-executions)

EVALUATION LAYER
└── Cosmos DB (agent-executions) → Cosmos DB (evaluations)
```

### Custom Entity Types Created

| Type | Description |
|------|-------------|
| `fabric_data_agent` | Microsoft Fabric Data Agent powered by IQ |
| `azure_foundry_agent` | Azure AI Foundry Agent in the multi-agent system |
| `azure_ai_service` | Azure AI Service (Content Understanding) |

## Prerequisites

```bash
pip install azure-identity requests
```

## Configuration

### Option 1: Environment File (Recommended)

Copy the example file and fill in your values:

```bash
cp .env.example .env
# Edit .env with your configuration
```

**Important**: The `PURVIEW_COLLECTION` must be the **Collection ID** (e.g., `8idoto`), not the friendly name.

To find your collection ID:
```bash
python create_lineage.py --list-collections
```

### Option 2: Command-Line Arguments

Pass configuration directly via command-line arguments (see Usage below).

## Authentication

Scripts use `DefaultAzureCredential` which supports:
- Azure CLI (`az login`)
- Environment variables (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET)
- Managed Identity
- Visual Studio Code

## Usage

### List Collections (to find collection ID)

```bash
python create_lineage.py --list-collections
```

### Create Lineage

```bash
# Using .env file (recommended)
python create_lineage.py --dry-run  # Dry run first
python create_lineage.py            # Create for real

# Using command-line arguments
python create_lineage.py \
    --purview-account pview-apfsipurviewdemo \
    --collection 8idoto

# With cleanup (delete existing entities first)
python create_lineage.py --cleanup

# With type reset (if types have wrong supertypes)
python create_lineage.py --cleanup --reset-types
```

### Verify Lineage

```bash
python verify_lineage.py --purview-account pview-apfsipurviewdemo
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `--purview-account` | Purview account name (or set PURVIEW_ACCOUNT env var) |
| `--collection` | Collection ID to place entities in (or set PURVIEW_COLLECTION env var) |
| `--project-name` | Optional Fabric project name for metadata |
| `--dry-run` | Preview changes without creating anything |
| `--cleanup` | Delete existing custom entities before recreating |
| `--reset-types` | Delete and recreate type definitions |
| `--list-collections` | List all collections and their IDs, then exit |
