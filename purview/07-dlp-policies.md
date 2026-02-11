# 07 - Data Loss Prevention Policies for Fabric and Power BI

This document covers configuring Microsoft Purview Data Loss Prevention (DLP) policies for the Insurance Claims Multi-Agent application, protecting sensitive data in Fabric Lakehouses, Semantic Models, and Power BI reports.

> **Reference**: [Get started with DLP policies for Fabric and Power BI](https://learn.microsoft.com/en-us/purview/dlp-powerbi-get-started)

---

## Overview

DLP policies for Fabric detect sensitive information in supported item types and trigger protective actions:

- **Policy tips** notifying item owners of the violation
- **Administrator alerts** on the DLP Alerts page in the Purview portal
- **Email alerts** to administrators and specified users
- **Access restrictions** limiting who can view flagged items

### How DLP Evaluation Works

| Item Type | Evaluation Triggers |
|-----------|-------------------|
| Semantic Models | Publish, Republish, On-demand refresh, Scheduled refresh |
| Lakehouses | Data changes — new data, new source, table additions, table updates |
| KQL Databases | Data changes |
| Mirrored Databases | Data changes |
| SQL Databases | Data changes |

> **Note**: DLP evaluation does NOT occur if a service principal initiates the event or owns the semantic model.

### Supported Condition Types

DLP policy rules for Fabric support:
- **Sensitivity labels** (applied in [Step 06](06-sensitivity-labels.md))
- **Sensitive info types (SIT)** — a subset of built-in types (see [Limitations](#considerations-and-limitations))

---

## Prerequisites

- Microsoft 365 E5 or equivalent license with DLP capabilities
- Fabric workspaces on **Premium** or **Fabric** capacity
- One of the following roles:
  - Compliance Administrator
  - Security Administrator
  - Compliance Data Administrator
- Sensitivity labels already configured and applied (see [06 - Sensitivity Labels](06-sensitivity-labels.md))

---

## Part 1: Create DLP Policy for Sensitive Claims Data

This policy detects Fabric items labeled **Highly Confidential** (e.g., `claimant_profiles`, `fraud_indicators`) and restricts external access.

### Step 1: Open DLP Policy Creation

1. Go to the [Microsoft Purview portal](https://purview.microsoft.com)
2. Navigate to **Data loss prevention** > **Policies**
3. Click **+ Create policy**
4. Select **Custom** category → **Custom policy** template
5. Click **Next**

> **Important**: DLP policy templates are NOT supported for Fabric. You must use the **Custom policy** option.

### Step 2: Name the Policy

| Field | Value |
|-------|-------|
| **Name** | `Insurance Claims - Highly Confidential Fabric Data` |
| **Description** | `Detects and restricts access to Highly Confidential insurance data in Fabric Lakehouses and Semantic Models containing PII, fraud indicators, and claimant profiles` |

### Step 3: Assign Admin Units

Click **Next** (skip — applies organization-wide).

### Step 4: Choose Locations

1. Turn **off** all locations except **Fabric and Power BI**
2. Under Fabric and Power BI, scope to **All workspaces** (or select specific workspaces containing insurance data)
3. Click **Next**

### Step 5: Define Policy Rules

#### Rule 1: Highly Confidential Label Detection

1. Click **+ Create rule**
2. Name: `Block external access to Highly Confidential items`
3. Under **Conditions**, click **+ Add condition** → **Content contains**
4. Click **Add** > **Sensitivity labels**
5. Select: **Highly Confidential** (and all sub-labels)
6. Under **Actions**:
   - Enable **Restrict access or encrypt the content in Microsoft 365 locations**
   - Select **Block only people outside your organization**
7. Under **User notifications**:
   - Enable **Notify users in Office 365 service with a policy tip or email notifications**
8. Under **User notifications**:
   - Default is to enable **Allow overrides from M365 files and Microsoft Fabric**
   - Ensure you require a business justification to override policy restrictions
9. Under **Incident reports**:
   - Set severity to **High**
   - Enable **Send an alert to admins every time an activity matches the rule**
10. Click **Save**

#### Rule 2: PII Sensitive Info Type Detection

1. Click **+ Create rule**
2. Name: `Detect PII in Fabric items`
3. Under **Conditions**, click **+ Add condition** > **Content contains**
4. Click **Add** → **Sensitive info types**
5. Select the following SITs:
   - **U.S. Social Security Number (SSN)**
   - **Credit Card Number**
   - **U.S. Driver's License Number**
   - **U.S. Individual Taxpayer Identification Number (ITIN)**
6. Set instance count thresholds:
   - Min: `1`, Max: `Any`
7. Under **Actions**:
   - Enable **Restrict access or encrypt the content in Microsoft 365 locations**
   - Select **Block only people outside your organization**
8. Under **User notifications**:
   - Enable **Notify users in Office 365 service with a policy tip or email notifications**
9. Under **User notifications**:
   - Default is to enable **Allow overrides from M365 files and Microsoft Fabric**
   - Ensure you require a business justification to override policy restrictions
10. Under **Incident reports**:
   - Set severity to **High**
   - Enable **Send an alert to admins every time an activity matches the rule**
11. Click **Save**

### Step 6: Test or Turn On

1. Select **Run the policy in simulation mode** to test first
2. Click **Next** → **Submit**

> **Recommendation**: Run in simulation mode for 1–2 weeks, review alerts on the DLP Alerts page, then switch to **Turn it on right away**.

---

## Part 2: Create DLP Policy for Confidential Business Data

This policy applies lighter controls to items labeled **Confidential** (e.g., `claims_history`, `policy_claims_summary`, Semantic Model).

### Step 1: Create Policy

1. **Data loss prevention** → **Policies** → **+ Create policy**
2. **Custom** → **Custom policy** → **Next**

### Step 2: Name the Policy

| Field | Value |
|-------|-------|
| **Name** | `Insurance Claims - Confidential Fabric Data` |
| **Description** | `Monitors Confidential insurance claims data in Fabric and Power BI, generating alerts and policy tips without restricting access` |

### Step 3: Choose Locations

Turn on only **Fabric and Power BI** → **All workspaces**

### Step 4: Define Policy Rules

#### Rule: Confidential Label Monitoring

1. **+ Create rule** → Name: `Monitor Confidential Fabric items`
2. **Conditions** → **Content contains** → **Sensitivity labels** → Select **Confidential** (and all sub-labels)
3. **Actions**: None (monitoring only — no access restrictions)
4. **User notifications**: Enable policy tips
5. **User notifications**: Require a business justification to override
6. **Incident reports**: Severity **Low**, enable admin alerts
7. **Save**

### Step 5: Turn On

Select **Turn it on right away** (monitoring-only policy is low risk).

---

## Part 3: Review and Monitor DLP Alerts

### Via Purview Portal

1. Go to **Data loss prevention** → **Alerts**
2. Filter by:
   - **Policy**: `Insurance Claims - Highly Confidential Fabric Data`
   - **Severity**: High, Medium
3. Review flagged items and take action (dismiss, investigate, or restrict)

### Via Fabric

When a DLP policy flags an item:
- **Lakehouses**: A policy tip icon appears in the header in edit mode
- **Semantic Models**: A policy tip appears on the details page
- Users can click the icon to see violation details in a side panel

### Key Metrics to Track

| Metric | Where to Find |
|--------|---------------|
| Total DLP matches | Purview portal → DLP → Activity explorer |
| Items with policy tips | Purview portal → DLP → Alerts |
| Restricted items | Purview portal → DLP → Alerts (filter by action) |
| False positives | Review alerts and adjust SIT confidence levels |

---

## Policy Summary for Insurance Claims Application

| Policy | Scope | Condition | Action | Severity |
|--------|-------|-----------|--------|----------|
| Highly Confidential Fabric Data | Fabric & Power BI | Highly Confidential label | Block external access + policy tip + admin alert | High |
| Highly Confidential Fabric Data | Fabric & Power BI | PII (SSN, CC, DL, ITIN) | Block external access + policy tip + admin alert | Medium |
| Confidential Fabric Data | Fabric & Power BI | Confidential label | Policy tip + admin alert (no restriction) | Low |

### Item-to-Policy Mapping

| Fabric Item | Sensitivity Label | DLP Policy | Action |
|-------------|-------------------|------------|--------|
| claimant_profiles | Highly Confidential | Highly Confidential Fabric Data | Block external, alert |
| fraud_indicators | Highly Confidential | Highly Confidential Fabric Data | Block external, alert |
| claims_history | Confidential | Confidential Fabric Data | Monitor, policy tip |
| policy_claims_summary | Confidential | Confidential Fabric Data | Monitor, policy tip |
| regional_statistics | General | — | No DLP policy |
| Claims Semantic Model | Confidential | Confidential Fabric Data | Monitor, policy tip |
| Claims Dashboard (Report) | General | — | No DLP policy |
