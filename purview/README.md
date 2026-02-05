# Microsoft Purview Data Governance Setup

This folder contains documentation and scripts for setting up Microsoft Purview data governance for the Insurance Claims Multi-Agent application.

## Overview

Microsoft Purview provides unified data governance for discovering, classifying, and managing data across your organization. This guide covers integrating the following assets:

### Data Sources to Scan
| Source | Type | Purpose |
|--------|------|---------|
| Azure Storage Account | Blob/ADLS Gen2 | Raw claims data, documents |
| Azure Cosmos DB | NoSQL | Agent executions, evaluations |
| Microsoft Fabric Tenant | Lakehouses, Semantic Models, Reports, Pipelines | Claims analytics data |

### Governance Components
- **Data Map**: Automated scanning and discovery
- **Unified Catalog**: Searchable asset inventory
- **Data Products**: Business-aligned data packages
- **Governance Domains**: Organizational data ownership
- **Lineage**: End-to-end data flow visualization
- **Sensitivity Labels**: Data classification and protection
- **DLP Policies**: Data loss prevention

---

## Document Index

| # | Document | Description |
|---|----------|-------------|
| 1 | [Purview Setup](01-purview-setup.md) | Initial account creation and configuration |
| 2 | [Scan Storage Account](02-scan-storage-account.md) | Connect and scan Azure Storage |
| 3 | [Scan Cosmos DB](03-scan-cosmos-db.md) | Connect and scan Cosmos DB |
| 4 | [Scan Fabric Tenant](04-scan-fabric-tenant.md) | Register and scan Microsoft Fabric tenant |
| 5 | [Governance Domains](05-governance-domains.md) | Create domains and data products |
| 6 | [Lineage REST API](06-lineage-rest-api.md) | Custom lineage via Apache Atlas API |
| 7 | [Sensitivity Labels & DLP](07-sensitivity-labels-dlp.md) | Classification and protection policies |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MICROSOFT PURVIEW                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  Data Map   │  │  Catalog    │  │  Lineage    │  │  Policies   │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │                │            │
└─────────┼────────────────┼────────────────┼────────────────┼────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                   │
├─────────────────┬─────────────────┬─────────────────┬───────────────────┤
│                 │                 │                 │                   │
│  ┌───────────┐  │  ┌───────────┐  │  ┌───────────┐  │  ┌───────────┐   │
│  │  Azure    │  │  │  Cosmos   │  │  │  Fabric   │  │  │  Power    │   │
│  │  Storage  │  │  │  DB       │  │  │  Lakehouse│  │  │  BI       │   │
│  └───────────┘  │  └───────────┘  │  └───────────┘  │  └───────────┘   │
│                 │                 │                 │                   │
│  - Claims docs  │  - Executions   │  - claims_      │  - Dashboards    │
│  - Raw files    │  - Evaluations  │    history      │  - Reports       │
│  - Uploads      │  - Agent logs   │  - claimant_    │  - Datasets      │
│                 │                 │    profiles     │                   │
│                 │                 │  - fraud_       │                   │
│                 │                 │    indicators   │                   │
└─────────────────┴─────────────────┴─────────────────┴───────────────────┘
```

---

## Quick Start Checklist

### Phase 1: Foundation
- [ ] Create Microsoft Purview account
- [ ] Configure managed identity permissions
- [ ] Set up integration runtime (if needed)

### Phase 2: Data Discovery
- [ ] Register Azure Storage Account
- [ ] Register Cosmos DB
- [ ] Register Fabric workspace
- [ ] Run initial scans

### Phase 3: Governance Structure
- [ ] Create governance domains (Claims, Customers, Fraud)
- [ ] Define data products
- [ ] Establish data ownership

### Phase 4: Classification & Protection
- [ ] Apply sensitivity labels
- [ ] Configure DLP policies
- [ ] Set up alerts

### Phase 5: Lineage
- [ ] Verify auto-captured lineage
- [ ] Create custom lineage via REST API
- [ ] Document data flows

---

## Prerequisites

### Azure Resources Required
- Microsoft Purview account (or use Microsoft Purview in Microsoft Fabric)
- Azure Storage Account with claims data
- Azure Cosmos DB with agent execution data
- Microsoft Fabric workspace with Lakehouse

### Permissions Required
| Resource | Permission |
|----------|------------|
| Purview | Data Curator, Data Source Administrator |
| Storage Account | Storage Blob Data Reader |
| Cosmos DB | Cosmos DB Account Reader |
| Fabric | Workspace Admin or Member |

---

## Python Scripts

Automation scripts are available in the [scripts/](scripts/) folder:

| Script | Description |
|--------|-------------|
| [create_lineage.py](scripts/create_lineage.py) | Create custom lineage relationships between agents, Lakehouse, and Cosmos DB |
| [verify_lineage.py](scripts/verify_lineage.py) | Verify lineage relationships exist in Purview |
| [export_catalog.py](scripts/export_catalog.py) | Export Unified Catalog to JSON for backup |

### Usage

```bash
# Install dependencies
pip install azure-identity requests

# List collections (to find collection ID)
python scripts/create_lineage.py --list-collections

# Create lineage (dry run first)
python scripts/create_lineage.py --dry-run
python scripts/create_lineage.py --collection <collection-id>

# With cleanup (delete and recreate entities)
python scripts/create_lineage.py --cleanup --reset-types --collection <collection-id>

# Verify lineage
python scripts/verify_lineage.py --purview-account pview-apfsipurviewdemo

# Export catalog
python scripts/export_catalog.py --purview-account pview-apfsipurviewdemo --output catalog.json
```

---

## Related Documentation

- [Fabric IQ Ontology Configuration](../backend/fabric/docs/ontology-configuration-guide.md)
- [Fabric IQ Bindings Guidance](../backend/fabric/docs/bindings-guidance.md)

### Tools
- Azure CLI or Azure Portal
- Python 3.9+ (for REST API scripts)
- Azure Identity SDK

---

## Insurance Claims Data Classification

### Using Default Sensitivity Labels

We use the default Microsoft sensitivity labels that are pre-configured in your tenant:

| Label | Priority | Apply To |
|-------|----------|----------|
| **Public** | 1 | Publicly shareable policy terms |
| **General** | 2 | regional_statistics, Claims Dashboard |
| **Confidential** | 5 | claims_history, policy_claims_summary, Claims Semantic Model |
| **Highly Confidential** | 9 | claimant_profiles (PII), fraud_indicators |

### Recommended Glossary Terms

| Term | Definition | Related Assets |
|------|------------|----------------|
| Claimant | Person filing an insurance claim | claimant_profiles |
| Claim | Insurance claim record | claims_history |
| Fraud Indicator | Potential fraud signal | fraud_indicators |
| Policy | Insurance policy contract | policy_claims_summary |

---

## Contact

For questions about data governance for this project, contact the data steward assigned to the Insurance Claims domain.

---

*Last Updated: February 2026*
