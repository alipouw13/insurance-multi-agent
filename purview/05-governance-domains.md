# 05 - Governance Domains and Data Products

This document covers setting up governance domains, data products, and data ownership in Microsoft Purview for the Insurance Claims application.

---

## Overview

### What are Governance Domains?

Governance domains are logical groupings of data assets organized by business function. They help establish:
- Data ownership
- Stewardship responsibilities
- Access policies
- Data Quality standards

### What are Data Products?

Data products are curated, trustworthy data assets that are:
- Well-documented
- Quality-assured
- Ready for consumption
- Discoverable in the catalog

---

## Recommended Domain Structure

These domains should be implemented both on the Purview and Fabric sides.
```
Insurance Claims Organization
├── Claims
│   ├── Claims Processing (Data Product)
│   ├── Claims Analytics (Data Product)
│   └── Claims Documents (Data Product)
├── Customer
│   ├── Customer Profiles (Data Product)
│   └── Customer Communications (Data Product)
├── Fraud
│   ├── Fraud Detection (Data Product)
│   └── Fraud Investigation (Data Product)
└── Operations
    ├── Agent Operations (Data Product)
```

---

## Step 1: Create Governance Domains

### Via Purview Portal

1. Go to **Microsoft Purview Governance Portal**
2. Navigate to **Unified Catalog** → **Governance domains**
3. Click **+ New governance domain**

### Create Claims Domain

| Setting | Value |
|---------|-------|
| Name | `Claims` |
| Description | `Domain for all insurance claims-related data assets` |
| Domain owners | Claims Operations Manager |
| Domain experts | Claims Team Lead |

### Create Customer Domain

| Setting | Value |
|---------|-------|
| Name | `Customer` |
| Description | `Domain for customer/claimant data assets` |
| Domain owners | Customer Experience Manager |
| Domain experts | Data Privacy Officer |

### Create Fraud Domain

| Setting | Value |
|---------|-------|
| Name | `Fraud` |
| Description | `Domain for fraud detection and investigation data` |
| Domain owners | Risk & Compliance Manager |
| Domain experts | Fraud Analytics Lead |

### Create Operations Domain

| Setting | Value |
|---------|-------|
| Name | `Operations` |
| Description | `Domain for AI agent operations and system data` |
| Domain owners | Technology Operations Manager |
| Domain experts | MLOps Engineer |

---

## Step 2: Create Data Products

Data products package related assets for easy discovery and consumption. Below are the data products organized by governance domain.

### Claims Domain

| Name | Description | Type | Audience | Owner | Data Assets | Use Cases |
|------|-------------|------|----------|-------|-------------|-----------|
| Claims Processing | Production claims data for daily operations and processing workflows | Transactional data | Business Analyst | System Administrator | `LH_AIClaimsDemo.dbo.claims_history`, `LH_AIClaimsDemo.dbo.policy_claims_summary`, Storage: `claims-documents/` | Claims assessment workflow, Policy verification, Settlement processing |
| Claims Analytics | Aggregated claims metrics and trends for reporting | Dashboards/Reports | BI Engineer, Business User, Executive | System Administrator | `LH_AIClaimsDemo.dbo.claims_history`, `LH_AIClaimsDemo.dbo.regional_statistics` | Executive dashboards, Claims trend analysis, Performance reporting |
| Claims Documents | Scanned and processed claim documents | Dataset | Business Analyst, Business User | System Administrator | Storage: `claims-documents/`, Azure AI Services: Document Intelligence outputs | Document retrieval, OCR verification, Audit trails |

### Customer Domain

| Name | Description | Type | Audience | Owner | Data Assets | Use Cases |
|------|-------------|------|----------|-------|-------------|-----------|
| Customer Profiles | Customer/claimant profile data for service delivery | Master and reference data | Business Analyst | System Administrator | `LH_AIClaimsDemo.dbo.claimant_profiles` | Customer communications, Service personalization, Risk assessment |
| Customer Communications | Customer interaction history and correspondence | Transactional data | Business User | System Administrator | Cosmos DB: `agent-executions`, Storage: `customer-correspondence/` | Communication history, Customer service, Compliance auditing |

### Fraud Domain

| Name | Description | Type | Audience | Owner | Data Assets | Use Cases |
|------|-------------|------|----------|-------|-------------|-----------|
| Fraud Detection | Fraud indicators and patterns for risk analysis | Analytics model | Data Scientist | System Administrator | `LH_AIClaimsDemo.dbo.fraud_indicators`, Derived: Risk scores from `claimant_profiles` | Fraud pattern detection, Risk analyst workflows, Investigation support |
| Fraud Investigation | Case files and investigation tracking data | Dataset | Business Analyst | System Administrator | `LH_AIClaimsDemo.dbo.fraud_cases`, Storage: `investigation-files/` | Case management, Evidence tracking, Regulatory reporting |

### Operations Domain

| Name | Description | Type | Audience | Owner | Data Assets | Use Cases |
|------|-------------|------|----------|-------|-------------|-----------|
| Agent Operations | Multi-agent system execution logs and evaluation metrics | Operational | Data Engineer | System Administrator | Cosmos DB: `agent-executions`, Cosmos DB: `evaluations` | Agent performance monitoring, AI quality evaluation, Operational dashboards |

---

## Step 3: Assign Data Ownership

Assign Ownership by Governance Domain - Governance Domains should be aligned to business domains and associated business owners will be the responsible data stewards to curate data products in this domain.

## Step 4: Create Business Glossary

### Glossary Structure

See below for some ideas on glossary items for each of our governance domains.

```
Insurance Claims Glossary
├── Claims Terms
│   ├── Claim
│   ├── Claimant
│   ├── Claim Type
│   ├── Estimated Damage
│   └── Settlement
├── Customer Terms
│   ├── Customer Profile
│   ├── Risk Score
│   └── Policy Holder
├── Fraud Terms
│   ├── Fraud Indicator
│   ├── Fraud Pattern
│   └── Investigation Status
└── Operational Terms
    ├── Agent Execution
    ├── Evaluation Score
    └── Token Usage
```

### Create Glossary Terms

#### Term: Claim

| Setting | Value |
|---------|-------|
| Name | `Claim` |
| Definition | `A formal request by a policyholder to an insurance company for coverage or compensation for a covered loss or policy event` |
| Status | `Approved` |
| Domain | Claims |
| Related Terms | Claimant, Policy, Settlement |

#### Term: Fraud Indicator

| Setting | Value |
|---------|-------|
| Name | `Fraud Indicator` |
| Definition | `A data point or pattern that suggests potential fraudulent activity in an insurance claim` |
| Status | `Approved` |
| Domain | Fraud |
| Sensitivity | Highly Confidential |

---

## Step 5: Link Glossary Terms to Assets

Associate terms with data assets for better discovery:

### Via Portal

1. Open asset in Unified Catalog
2. Click **Edit**
3. Under **Glossary terms**, add relevant terms

### Asset-Term Mapping

| Asset | Glossary Terms |
|-------|---------------|
| claims_history | Claim, Claim Type, Settlement, Estimated Damage |
| claimant_profiles | Claimant, Customer Profile, Risk Score |
| fraud_indicators | Fraud Indicator, Fraud Pattern, Investigation Status |
| agent_executions | Agent Execution, Evaluation Score |

---

## Summary: Insurance Claims Data Products

| Data Product | Domain | Type | Audience | Key Assets | Access Level |
|--------------|--------|------|----------|------------|--------------|
| Claims Processing | Claims | Transactional data | Business Analyst | claims_history, policy_claims_summary | Internal |
| Claims Analytics | Claims | Dashboards/Reports | BI Engineer | claims_history, regional_statistics | Internal |
| Claims Documents | Claims | Dataset | Business Analyst | claims-documents/ | Internal |
| Customer Profiles | Customer | Master and reference data | Business Analyst | claimant_profiles | Restricted |
| Customer Communications | Customer | Transactional data | Business User | agent-executions | Restricted |
| Fraud Detection | Fraud | Analytics model | Data Scientist | fraud_indicators | Highly Restricted |
| Fraud Investigation | Fraud | Dataset | Business Analyst | fraud_cases | Highly Restricted |
| Agent Operations | Operations | Operational | Data Engineer | agent-executions, evaluations | Internal |
| System Metrics | Operations | Operational | Software Engineer | Application Insights, Azure Monitor | Internal |

---

## Next Steps

1. [Create custom lineage via REST API](06-lineage-rest-api.md)
2. [Configure sensitivity labels and DLP](07-sensitivity-labels-dlp.md)

---
