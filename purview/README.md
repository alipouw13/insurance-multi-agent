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
| 6 | [Sensitivity Labels](06-sensitivity-labels.md) | Sensitivity label configuration and publishing policies |
| 7 | [DLP Policies](07-dlp-policies.md) | Data Loss Prevention policies for Fabric and Power BI |
| 8 | [Lineage REST API](08-lineage-rest-api.md) | Custom lineage via Atlas API |


---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MICROSOFT PURVIEW                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Data Map   │  │  Catalog    │  │  Lineage    │  │  Policies   │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │                │            │
└─────────┼────────────────┼────────────────┼────────────────┼────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                  │
├─────────────────┬─────────────────┬─────────────────┬───────────────────┤
│                 │                 │                 │                   │
│  ┌───────────┐  │  ┌───────────┐  │  ┌───────────┐  │  ┌───────────┐    │
│  │  Azure    │  │  │  Cosmos   │  │  │  Fabric   │  │  │  Power    │    │
│  │  Storage  │  │  │  DB       │  │  │  Lakehouse│  │  │  BI       │    │
│  └───────────┘  │  └───────────┘  │  └───────────┘  │  └───────────┘    │
│                 │                 │                 │                   │
│  - Claims docs  │  - Executions   │  - claims_      │  - Dashboards     │
│  - Raw files    │  - Evaluations  │    history      │  - Reports        │
│  - Uploads      │  - Agent logs   │  - claimant_    │  - Datasets       │
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
