# 06 - Sensitivity Labels and Label Publishing Policies

This document covers configuring Microsoft Purview sensitivity labels for the Insurance Claims Multi-Agent application, with specific guidance for Fabric and Power BI. We will go over configuring the [mandatory label publishing](https://learn.microsoft.com/en-us/fabric/governance/mandatory-label-policy) policy and [default label publishing](https://learn.microsoft.com/en-us/fabric/governance/sensitivity-label-default-label-policy) policy.

---

## Overview

### Default Sensitivity Labels (Microsoft Built-in)

We use the default Microsoft sensitivity labels that are pre-configured in your tenant:

| Label | Priority | Scope | Use Case |
|-------|----------|-------|----------|
| Personal | 0 | Files, Email, Meetings | Personal data not for business use |
| Public | 1 | Files, Email, Meetings | Information approved for public sharing |
| General | 2 | Files, Email | Standard business data with no special restrictions |
| Confidential | 5 | Files, Email | Business-sensitive data requiring controlled access |
| Highly Confidential | 9 | Files, Email | Most sensitive data with strictest controls |

---

## Limitations

Mandatory labeling in Fabric and Power BI is supported for all item types except:

- Scorecard
- Dataflow Gen 1
- Dataflow Gen 2
- Streaming semantic model
- Streaming dataflow

---

## Part 1: Using Default Sensitivity Labels

Your tenant already has the default Microsoft sensitivity labels configured. These labels are ready to use without additional configuration.

### Default Labels Available

| Label | Priority | Description | Protection |
|-------|----------|-------------|------------|
| **Personal** | 0 | Non-business data that is personal in nature | None |
| **Public** | 1 | Business data specifically prepared for public consumption | None |
| **General** | 2 | Business data not intended for public consumption | Content marking optional |
| **Confidential** | 5 | Sensitive business data that could cause harm if shared improperly | Encryption + Content marking |
| **Highly Confidential** | 9 | Very sensitive data requiring the highest level of protection | Strong encryption + Strict access |

> **Note**: General, Confidential, and Highly Confidential labels may have sub-labels with additional granularity.

---

### Step 1: Verify Labels are Published

1. Go to Microsoft Purview Compliance Portal
2. Navigate to **Information Protection** → **Sensitivity Labels**
3. Verify the default labels exist (Personal, Public, General, Confidential, Highly Confidential)

If labels are not published to users:
1. Go to **Information Protection** → **Policies** → **Label publiching policies**
2. Verify a policy exists that publishes the labels to your organization

---

### Step 2: Enable Sensitivity Labels in Fabric

1. Go to [Fabric Admin Portal](https://app.fabric.microsoft.com/admin-portal/tenantSettings)
2. Navigate to **Tenant settings** → **Information protection**
3. Find **Allow users to apply sensitivity labels for content**
4. Turn on the toggle
5. Configure who can apply labels to **The entire organization**
6. Click **Apply**

> **Important**: Users need both Create/Edit permissions on items AND the label must be published to them.

---

### Step 3: Apply Labels to Fabric Items

#### Via Flyout Menu

1. Open a Fabric item (Lakehouse, Report, Semantic Model)
2. Click the sensitivity label indicator in the header
3. Select the appropriate label from the flyout

#### Via Item Settings

1. Open item settings
2. Find the **Sensitivity** section
3. Choose the desired label

#### Recommended Labels for Your Assets

| Item | Type | Recommended Label |
|------|------|-------------------|
| claimant_profiles | Lakehouse Table | Highly Confidential |
| claims_history | Lakehouse Table | Confidential |
| fraud_indicators | Lakehouse Table | Highly Confidential |
| policy_claims_summary | Lakehouse Table | Confidential |
| regional_statistics | Lakehouse Table | General |
| Claims Dashboard | Report | General |
| Claims Semantic Model | Semantic Model | Confidential |

---

## Part 2: Default and mandatory sensitivity label policy for Fabric and Power BI

Review documentation [here](https://learn.microsoft.com/en-us/fabric/governance/sensitivity-label-default-label-policy) and [here](https://learn.microsoft.com/en-us/fabric/governance/mandatory-label-policy) for exact implementation steps

### Step 1: Create a label publishing policy for Fabric / Power BI

1. Open the sensitivity label publishing policies page
2. Click **+ Create policy**
3. Choose **Custom** category and **Custom policy** template
4. Click **Next**

### Step 2: Select sensitivity labels to publish

```
Select all the default sensitivity labels to publish.
```

### Step 3: Skip Admin Units

Click **Next** (Skip)

### Step 4: Select Scope

Select all users and groups

### Step 5 - Policy Settings - Mandatory default label

Select _Require users to apply a label to their Fabric and Power BI content_

### Step 6 - Select Default Label

Skip past documents, emails, meetings, sites and groups to Fabric and Power BI settings. Select _Confidential/All Employees_ as your default label.

### Step 7 - Name your policy and provide description

Name: Insurance Claims Data Protection - Fabric
Description: Default Fabric and Power BI labelling policy

