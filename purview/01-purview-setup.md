# 01 - Microsoft Purview Account Setup

This document covers the initial setup of Microsoft Purview for the Insurance Claims Multi-Agent application. Please note - you will have one Purview tenant per Azure tenant. If you have this configured already, please skip to step 2.

---

## Option 1: Standalone Microsoft Purview Account

### Step 1: Create Purview Account via Azure Portal

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Search for **"Microsoft Purview"**
3. Click **"+ Create"**
4. Configure:

   | Setting | Recommended Value |
   |---------|-------------------|
   | Subscription | Your Azure subscription |
   | Resource Group | `rg-insurance-governance` |
   | Purview Account Name | `purview-prod` |
   | Location | Same region as your data sources |
   | Managed Resource Group | `purview-insurance-claims-managed` |

5. Click **Review + Create** → **Create**

---

## Step 2: Configure Managed Identity Permissions

Purview uses a managed identity to scan data sources.

### Get Purview Managed Identity

```bash
# Get the managed identity object ID
az purview account show \
  --name purview-contoso-insurance \
  --resource-group rg-insurance-governance \
  --query "identity.principalId" \
  --output tsv
```

### Grant Permissions to Data Sources

#### For Azure Storage Account

```bash
PURVIEW_IDENTITY="<purview-managed-identity-object-id>"
STORAGE_ACCOUNT="<your-storage-account-name>"
SUBSCRIPTION_ID="<your-subscription-id>"

# Assign Storage Blob Data Reader role
az role assignment create \
  --assignee $PURVIEW_IDENTITY \
  --role "Storage Blob Data Reader" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-insurance-governance/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT"
```

#### For Cosmos DB

```bash
COSMOS_ACCOUNT="<your-cosmos-account-name>"

# Assign Cosmos DB Account Reader role
az role assignment create \
  --assignee $PURVIEW_IDENTITY \
  --role "Cosmos DB Account Reader Role" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-insurance-governance/providers/Microsoft.DocumentDB/databaseAccounts/$COSMOS_ACCOUNT"
```

#### For Microsoft Fabric

Fabric uses different authentication - see [04-scan-fabric-lakehouse.md](04-scan-fabric-lakehouse.md).

---

## Step 3: Configure Collections

Collections organize your data sources hierarchically.

### Recommended Collection Structure

```
Root Collection (purview-contoso-insurance)
├── Insurance Operations Application
│   ├── Claims Processing
│   ├── Policy Creation
│   └──Analytics
├── Application 2
│   ├── ...
...

```

### Create Collections via Portal

1. Open Purview Governance Portal
2. Navigate to **Data Map** > **Domains**
3. Click **+ Add a collection** under your parent domain
4. Create the hierarchy above

**Please note, you need the role data curator in order to create collections.**

---

## Step 4: Configure Integration Runtime (Optional)

If your data sources are behind a firewall or in a private network, you need a Self-Hosted Integration Runtime (SHIR).

### When SHIR is Required
- Private endpoint enabled storage accounts
- Cosmos DB with private networking
- On-premises data sources

### Install SHIR

1. Download from [Microsoft Download Center](https://www.microsoft.com/en-us/download/details.aspx?id=105539)
2. Install on a VM with network access to your data sources
3. Register with Purview:

```bash
# In Purview Portal
# Go to Data Map → Integration runtimes → + New
# Select "Self-Hosted" and follow registration steps
```

---

## Roles and Cost

See this [repo](https://github.com/alipouw13/appurviewdemo) for costs and role assignments guidance.

Costs are incurred per governed asset in the Unified Catalog (~$0.5/month), for Data Qulity runs, and for auto labelling policies. Pricing listed [here](https://learn.microsoft.com/en-us/purview/data-governance-billing).

---

## Next Steps

1. [Register and scan Azure Blob Storage Account](02-scan-storage-account.md)
2. [Register and scan Cosmos DB](03-scan-cosmos-db.md)
3. [Register and scan Fabric Tenant](04-scan-fabric-tenant.md)
