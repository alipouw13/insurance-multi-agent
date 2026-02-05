# 03 - Scan Azure Cosmos DB

This document covers registering and scanning your Azure Cosmos DB in Microsoft Purview for the Insurance Claims application.

---

## Overview

Your Cosmos DB (`cosmos-dataplatform-dev-001-eastus2`) contains:

| Database | Container | Purpose |
|----------|-----------|---------|
| `insurance-agents` | `agent-definitions` | Agent definitions |
| `insurance-agents` | `agent-executions` | Multi-agent workflow execution logs |
| `insurance-agents` | `evaluations` | AI evaluation results |
| `insurance-agents` | `token-usage` | Token usage for agent executions |

---

## Pre-requisites

- Key auth must be enabled for your Cosmos account - run the below script in azure cli.
```
az resource update --resource-group      "<name-of-existing-resource-group>" --name "<name-of-existing-account>" --resource-type "Microsoft.DocumentDB/databaseAccounts" --set properties.disableLocalAuth=true
```
- Other pre-requisites are listed [here](https://learn.microsoft.com/en-us/purview/register-scan-azure-cosmos-database#prerequisites).

## Steps

Review [these steps](https://learn.microsoft.com/en-us/purview/register-scan-azure-cosmos-database) to scan Cosmos DB accounts. Ensure the above pre-requisites before executing the scan.
