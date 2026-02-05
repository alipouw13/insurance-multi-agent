# 06 - Custom Lineage via REST API

This document covers creating custom data lineage in Microsoft Purview for the Insurance Claims Multi-Agent application.

> **Implementation**: See [scripts/create_lineage.py](scripts/create_lineage.py) for the complete automation script.

---

## Overview

### Why Custom Lineage?

While Purview auto-captures lineage for many Azure services, you need custom lineage for:
- AI/ML agent pipelines not natively supported
- Cross-service connections (Lakehouse → Fabric Data Agent → Foundry Agents)
- Application-level data flows (Agents → Cosmos DB)

### Lineage in Purview Portal

![Insurance Claims Lineage](../frontend/public/lineage.png)

### Lineage Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           INSURANCE CLAIMS DATA LINEAGE                                         │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

                                    DATA INGESTION LAYER
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                 │
│  [Azure Storage]                      [Fabric Pipeline]              [Lakehouse]                │
│  stapfsidemoinsurance/                                                                          │
│  insurance-documents/  ────────────────────────────────────────────► claims_history             │
│    ├── claim/          ────────────────────────────────────────────► claimant_profiles          │
│    ├── policies/       ────────────────────────────────────────────► policy_claims_summary      │
│    └── policy/                                                       fraud_indicators           │
│                                                                      regional_statistics        │
│                                                                                                 │
│  [Cosmos DB]                          [Fabric Pipeline]                                         │
│  insurance-agents/                                                                              │
│    └── token-usage     ────────────────────────────────────────────► (analytics aggregation)    │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                                     FABRIC DATA AGENT LAYER
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                 │
│  [Lakehouse Tables]              [Fabric IQ Ontology]            [Fabric Data Agent]            │
│  claims_history     ──────────►  ClaimEntity          ──────────► Claims Data Analyst           │
│  claimant_profiles  ──────────►  ClaimantEntity       ──────────► (Queries via natural lang)    │
│  fraud_indicators   ──────────►  PolicyEntity                                                   │
│  policy_claims_sum  ──────────►  FraudIndicator                                                 │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                                   AZURE AI FOUNDRY AGENT LAYER
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                 │
│  [Fabric Data Agent]          [Foundry Supervisor]          [Foundry Specialist Agents]         │
│  Claims Data Analyst  ──────► Supervisor Agent    ◄──────── Claim Assessor Agent                │
│                                     │             ◄──────── Policy Checker Agent                │
│  [Lakehouse]                        │             ◄──────── Risk Analyst Agent ◄── fraud_ind    │
│  fraud_indicators ─────────────────►│             ◄──────── Claims Data Analyst Agent           │
│                                     │             ◄──────── Communication Agent                 │
│  [Azure AI Services]                │                                                           │
│  Content Understanding ─────────────┤                                                           │
│                                     │                                                           │
│  [Azure Storage]                    │                                                           │
│  insurance-documents/ ──────────────┤ (via AI Search for Policy Checker)                        │
│                                     │                                                           │
└─────────────────────────────────────│───────────────────────────────────────────────────────────┘
                                      ▼
                                    OUTPUT LAYER
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                 │
│  [Cosmos DB]                    [Evaluation]                 [Power BI]                         │
│  agent-executions  ────────────► evaluations  ──────────────► Claims Dashboard                  │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- **Purview Account** with Data Curator role
- **Azure CLI** authenticated (`az login`)
- **Python 3.9+** with dependencies: `pip install azure-identity requests`

---

## Quick Start

```bash
# List collections to find the collection ID
python scripts/create_lineage.py --list-collections

# Dry run to see what would be created
python scripts/create_lineage.py --purview-account pview-apfsipurviewdemo --dry-run

# Create lineage (specify collection ID, not friendly name)
python scripts/create_lineage.py \
    --purview-account pview-apfsipurviewdemo \
    --collection collection-id

# With cleanup (recreate entities)
python scripts/create_lineage.py --cleanup --reset-types
```

---

## Step 1: Custom Entity Types

The script creates these custom types in Purview to represent AI components:

| Type | Description | Key Attributes |
|------|-------------|----------------|
| `fabric_data_agent` | Fabric Data Agent powered by IQ | projectName, lakehouseName, ontologyEntities |
| `azure_foundry_agent` | Azure AI Foundry Agent | agentType, agentId, toolsUsed, modelDeployment |
| `azure_ai_service` | Azure AI Service | serviceType, endpoint, analyzerId |

---

## Step 2: Set Up Cosmos DB Mirroring

Before running the lineage script, configure Fabric Mirroring for Cosmos DB:

1. In Fabric workspace, select **New** → **Mirrored Azure Cosmos DB**
2. Connect to your Cosmos DB account
3. Select containers to mirror:
   - `agent-executions`
   - `token-tracking`
   - `evaluations`
4. Mirrored data appears as Delta tables in OneLake

| Cosmos DB Container | Mirrored Table | Refresh Rate |
|---------------------|----------------|--------------|
| `agent-executions` | `mirrored_agent_executions` | Near real-time |
| `token-tracking` | `mirrored_token_tracking` | Near real-time |
| `evaluations` | `mirrored_evaluations` | Near real-time |

---

## Step 3: Run the Lineage Script

The script performs these actions automatically:

### 3.1 Find Existing Assets
Searches Purview for already-scanned assets:
- Azure Storage containers
- Lakehouse tables
- Cosmos DB collections

### 3.2 Create Agent Entities
Creates entities for:
- **Fabric Data Agent**: Claims Data Analyst
- **Foundry Agents**: Supervisor, Claim Assessor, Policy Checker, Risk Analyst, Claims Data Analyst, Communication
- **AI Services**: Content Understanding

### 3.3 Create Lineage Relationships

| Lineage | Description |
|---------|---------|
| Storage → Lakehouse | Fabric Pipeline ingests claim documents and policy files |
| Cosmos DB → Lakehouse | Token usage sync for analytics |
| Lakehouse → Fabric Data Agent | IQ semantic layer enables natural language queries |
| Fabric Agent → Foundry Agent | Claims Data Analyst queries via Fabric Data Agent |
| AI Services → Claim Assessor | Content Understanding extracts document data |
| Fraud Data → Risk Analyst | Risk scoring uses fraud indicators from Lakehouse |
| Storage → Policy Checker | Policy verification via AI Search |
| Specialist Agents → Supervisor | Orchestration flow |
| Supervisor → Cosmos DB | Execution results stored |
| Executions → Evaluations | Quality evaluation pipeline |

---

## Step 4: Verify Lineage

### Via Purview Portal

1. Go to **Unified Catalog**
2. Search for any asset (e.g., `claims_history`)
3. Click **Lineage** tab
4. Verify upstream and downstream connections appear

### Via Script

```bash
python scripts/verify_lineage.py --purview-account purview-prod
```

---

## Lineage Summary

| Source | Process | Target | Description |
|--------|---------|--------|-------------|
| Azure Storage (insurance-documents/) | Insurance Documents Ingestion | Lakehouse (claims_history, claimant_profiles, policy_claims_summary) | Fabric Pipeline ingests documents |
| Cosmos DB (token-usage) | Token Usage Analytics Sync | Lakehouse (claimant_profiles) | Pipeline transforms for analytics |
| Lakehouse Tables | Lakehouse to Fabric Data Agent | Fabric Data Agent | IQ semantic layer queries |
| Fabric Data Agent | Fabric Agent to Foundry | Foundry Claims Data Analyst | Natural language data queries |
| Storage + Content Understanding | Content Understanding to Assessor | Foundry Claim Assessor | Document extraction |
| Lakehouse (fraud_indicators) | Fraud Data to Risk Analyst | Foundry Risk Analyst | Risk scoring |
| Storage (insurance-documents) | Policy Files to Policy Checker | Foundry Policy Checker | Policy verification via AI Search |
| All Specialist Agents | Agents to Supervisor | Foundry Supervisor | Orchestration flow |
| Foundry Supervisor | Supervisor to Cosmos | Cosmos DB (agent-executions) | Execution logging |
| Cosmos DB (agent-executions) | Evaluation Pipeline | Cosmos DB (evaluations) | Quality evaluation |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Assets not found | Ensure Purview scans have completed for Storage, Cosmos DB, and Fabric |
| Permission denied | Verify Data Curator role on Purview account |
| Type already exists | Safe to ignore - script handles existing types |

---

## Next Steps

1. [Configure sensitivity labels and DLP](07-sensitivity-labels-dlp.md)

