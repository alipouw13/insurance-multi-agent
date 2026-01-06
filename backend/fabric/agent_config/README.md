# Fabric Data Agent Configuration Files

This folder contains configuration files for setting up the Insurance Claims Data Agent in Microsoft Fabric.

## Quick Start: Automated Setup

The easiest way to create the Data Agent is using the automated scripts:

### Option 1: Fabric Notebook (Recommended)
1. Upload `../create_data_agent.ipynb` to your Fabric workspace
2. Update the configuration variables (Lakehouse name, etc.)
3. Run all cells in sequence

### Option 2: Python Script
Run `../create_data_agent.py` in a Fabric notebook environment.

## Manual Setup Using Configuration Files

If you prefer to configure manually through the Fabric UI, use the files below.

## Files Overview

| File | Purpose | Where to Use in Fabric UI |
|------|---------|---------------------------|
| `agent_instructions.md` | Main agent AI instructions | Data Agent > Agent instructions |
| `datasource_description.md` | High-level data source summary for routing | Data Agent > Data Sources > [Lakehouse] > Data source description |
| `datasource_instructions.md` | Query-specific guidance with tables/columns | Data Agent > Data Sources > [Lakehouse] > Data source instructions |
| `example_queries.json` | Sample question:SQL pairs | Data Agent > Data Sources > [Lakehouse] > Example queries |

## Setup Instructions

### Step 1: Create the Data Agent

1. Open your Fabric workspace
2. Navigate to your Lakehouse
3. Open the **SQL Analytics Endpoint**
4. Click **New** > **Data Agent**
5. Name it: `Insurance Claims Data Agent`

### Step 2: Add Data Sources

1. In the Data Agent editor, click **Add data source**
2. Select your Lakehouse
3. Add each table:
   - claims_history
   - claimant_profiles
   - fraud_indicators
   - regional_statistics
   - policy_claims_summary

### Step 3: Configure Data Source

1. Click on your Lakehouse data source (e.g., `LH_AIClaimsDemo`)
2. In the **Data source description** field, copy the content from `datasource_description.md`
   - This describes what the data contains and helps route questions to this source
3. In the **Data source instructions** field, copy the content from `datasource_instructions.md`
   - This provides table schemas and query-specific guidance for SQL generation

### Step 4: Add Agent Instructions

1. In the Data Agent editor, find **AI Instructions**
2. Copy the entire content of `agent_instructions.md`
3. Paste into the AI Instructions field

### Step 5: Import Example Queries

1. Under your Lakehouse data source, find **Example queries**
2. Click **Import** or **Add**
3. Upload `example_queries.json`

The file format is simple key-value pairs:
```json
{
    "What is the average claim amount?": "SELECT AVG(estimated_damage) FROM dbo.claims_history",
    "Show all fraud indicators": "SELECT * FROM dbo.fraud_indicators"
}
```

> **Note**: Example queries are not supported for Power BI semantic model data sources, but work for Lakehouse/Warehouse sources.

### Step 6: Publish

1. Review all settings
2. Click **Publish**
3. Note the Data Agent endpoint URL

### Step 7: Create Azure AI Foundry Connection

1. Go to Azure AI Foundry portal
2. Navigate to **Connections**
3. Click **New connection** > **Microsoft Fabric**
4. Enter:
   - Connection name: `fabric-claims-data` (or your preference)
   - Fabric workspace URL
   - Data Agent details
5. Save the connection

### Step 8: Configure Application

Set environment variables in your `.env` file:

```bash
USE_FABRIC_DATA_AGENT=true
FABRIC_CONNECTION_NAME=fabric-claims-data
```

## Customization

### Modifying Instructions

Edit `agent_instructions.md` to:
- Add company-specific terminology
- Update business rules
- Add additional data source routing logic

### Adding New Example Queries

Edit `example_queries.json` to add new question-SQL pairs:

```json
{
    "Your natural language question": "SELECT ... FROM dbo.table_name WHERE ..."
}
```

### Updating Datasource Documentation

Edit the datasource files when:
- Schema changes (new columns added)
- Business definitions change
- New query patterns emerge

**datasource_description.md**: Update when the types of questions this data source answers changes
**datasource_instructions.md**: Update when table schemas or query logic changes

## Testing

After setup, test the Data Agent with questions like:

1. "What is the average claim amount for auto collision claims?"
2. "Show me all fraud indicators for claim CLM-00001"
3. "Which policies have increasing claim trends?"
4. "What is the fraud rate in California?"
5. "Find high-risk claimants with risk score above 70"

## Troubleshooting

**Data Agent not returning results:**
- Verify tables are loaded correctly in Lakehouse
- Check that the SQL Analytics Endpoint is accessible
- Ensure table names match exactly

**Wrong data source selected:**
- Add more specific routing instructions in `agent_instructions.md`
- Add more example queries for the specific data source

**Query errors:**
- Check column names match the actual schema
- Verify data types in example queries
