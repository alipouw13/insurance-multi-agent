# Microsoft Fabric Lakehouse Data Scripts

This folder contains Python scripts to populate a Microsoft Fabric Lakehouse with sample insurance claims data. The data is used by the **Claims Data Analyst** agent which leverages the Fabric Data Agent tool to query enterprise data.

## Prerequisites

1. **Microsoft Fabric Workspace** with a Lakehouse
2. **Fabric Data Agent** published in your workspace
3. **Connection** configured in Azure AI Foundry pointing to your Fabric resource
4. **Python environment** with required packages

## Installation

```bash
pip install azure-identity azure-storage-file-datalake pandas pyarrow
```

## Scripts

### Data Generation & Upload
- **`generate_sample_data.py`** - Generates synthetic insurance claims data (10,000+ records)
- **`upload_to_fabric.py`** - Uploads data to Fabric Lakehouse Files section as Parquet files

### Table Loading (Fabric Notebooks)
- **`load_tables.ipynb`** - Fabric notebook to load parquet files as Delta tables

### Data Agent Setup
- **`create_data_agent.ipynb`** - Fabric notebook to create and configure the Data Agent programmatically
- **`agent_config/`** - Configuration files for manual setup (instructions, example queries)

## Usage

### Step 1: Generate Sample Data
```bash
cd backend/fabric/sample_data
python generate_claims_data.py
```
This creates CSV files in the `./sample_data/` folder.

### Step 2: Set Environment Variables
```bash
# Required for upload (use workspace/lakehouse NAMES, not GUIDs)
export FABRIC_WORKSPACE_NAME="Claims Demo"
export FABRIC_LAKEHOUSE_NAME="LH_AIClaimsDemo"
```

### Step 3: Upload to Fabric
```bash
python upload_to_fabric.py --data-dir ./sample_data
```
This uploads parquet files to: `Files/claims_data/`

### Step 4: Load as Delta Tables

**Option A - Fabric Notebook (Recommended for schema-enabled Lakehouses):**
1. Upload `load_tables.ipynb` to your Fabric workspace
2. Attach the notebook to your Lakehouse
3. Run all cells to load parquet files as Delta tables

**Option B - Manual in Fabric UI:**
1. Open your Lakehouse
2. Navigate to **Files** → **claims_data**
3. Right-click the folder → **Load to Tables**
4. Select all parquet files and confirm

### Step 5: Create Fabric Data Agent

You can create the Data Agent using either the automated notebook or manually in the Fabric UI. Both methods use the same configuration from the `agent_config/` folder.

**Option A - Automated via Notebook (Recommended):**

Upload and run `create_data_agent.ipynb` in your Fabric workspace. This notebook:
- Creates the Data Agent programmatically using the Fabric SDK
- Sets agent instructions (how the agent should behave)
- Sets datasource description (what's in the data - used for question routing)
- Sets datasource instructions (how to use the data - used for query generation)
- Adds example queries (few-shot examples for better SQL generation)
- Publishes the agent

**Option B - Manual in Fabric UI:**

Use the configuration files in `agent_config/` folder to manually configure your Data Agent:

1. Go to your Fabric workspace
2. Click **+ New** → **Data Agent**
3. Name your Data Agent (e.g., `InsuranceClaimsDataAgent`)
4. Add your Lakehouse as a data source and select all 5 tables:
   - `claims_history`
   - `claimant_profiles`
   - `fraud_indicators`
   - `regional_statistics`
   - `policy_claims_summary`

5. Configure the agent using files from `agent_config/`:

   | UI Field | Source File | Description |
   |----------|-------------|-------------|
   | Agent instructions | `agent_instructions.md` | How the agent should behave and respond |
   | Data source description | `datasource_description.md` | What's in the data (max 800 chars, used for routing) |
   | Data source instructions | `datasource_instructions.md` | How to use the data (table schemas, query patterns) |
   | Example queries | `example_queries.json` | Sample question/SQL pairs for few-shot learning |

6. Test the agent in the Fabric UI
7. Click **Publish** to make the agent available

See [`agent_config/README.md`](agent_config/README.md) for detailed manual setup instructions.

### Step 6: Connect from Azure AI Foundry
1. In Azure AI Foundry portal, go to **Connections**
2. Add a new **Microsoft Fabric** connection
3. Provide your Fabric workspace URL and data agent details
4. Name the connection (use this as `FABRIC_CONNECTION_NAME`)

### Step 7: Enable in the Application
Set these environment variables:
```bash
USE_FABRIC_DATA_AGENT=true
FABRIC_CONNECTION_NAME=your-connection-name
```

## Data Schema

### claims_history
| Column | Type | Description |
|--------|------|-------------|
| claim_id | string | Unique claim identifier |
| policy_number | string | Associated policy |
| claimant_id | string | Customer identifier |
| claim_type | string | Auto Collision, Property Damage, etc. |
| estimated_damage | decimal | Estimated damage in USD |
| amount_paid | decimal | Actual amount paid |
| claim_date | date | Date claim was filed |
| incident_date | date | Date of incident |
| settlement_date | date | Date claim was settled (if any) |
| status | string | APPROVED, DENIED, PENDING, SETTLED |
| location | string | Incident location |
| state | string | State code |
| description | string | Claim description |
| police_report | boolean | Whether police report was filed |
| photos_provided | boolean | Whether photos were submitted |
| witness_statements | string | Number of witness statements |
| vehicle_vin | string | Vehicle VIN |
| vehicle_make | string | Vehicle make |
| vehicle_model | string | Vehicle model |
| vehicle_year | integer | Vehicle year |
| license_plate | string | License plate number |
| fraud_flag | boolean | Whether fraud was detected |

### claimant_profiles
| Column | Type | Description |
|--------|------|-------------|
| claimant_id | string | Unique customer identifier |
| name | string | Customer name |
| age | integer | Customer age |
| state | string | State code |
| city | string | City name |
| address | string | Full address |
| phone | string | Phone number |
| email | string | Email address |
| customer_since | date | Account creation date |
| total_claims_count | integer | Lifetime claims count |
| total_claims_amount | decimal | Lifetime claims value |
| average_claim_amount | decimal | Average claim value |
| risk_score | decimal | Calculated risk score (0-100) |
| claim_frequency | string | very_low, low, medium, high, very_high |
| credit_score | string | excellent, good, fair, poor |
| driving_record | string | clean, minor_violations, major_violations |
| policy_count | integer | Number of active policies |
| account_status | string | ACTIVE, SUSPENDED, CLOSED |
| age | integer | Customer age |
| location | string | Customer address |
| customer_since | date | Account creation date |
| total_claims_count | integer | Lifetime claims count |
| total_claims_amount | decimal | Lifetime claims value |
| risk_score | decimal | Calculated risk score (0-100) |
| policy_count | integer | Number of active policies |
| account_status | string | ACTIVE, SUSPENDED, CLOSED |

### fraud_indicators
| Column | Type | Description |
|--------|------|-------------|
| indicator_id | string | Unique indicator ID |
| claim_id | string | Associated claim |
| indicator_type | string | Pattern type |
| severity | string | LOW, MEDIUM, HIGH, CRITICAL |
| detected_date | date | When pattern was detected |
| pattern_description | string | Description of fraud pattern |
| investigation_status | string | OPEN, CLOSED, CONFIRMED |

### regional_statistics
| Column | Type | Description |
|--------|------|-------------|
| region | string | Geographic region |
| state | string | State code |
| city | string | City name |
| avg_claim_amount | decimal | Average claim value |
| claim_frequency | decimal | Claims per 1000 policies |
| fraud_rate | decimal | Percentage of fraudulent claims |
| most_common_claim_type | string | Most frequent claim type |
| seasonal_peak | string | Peak season for claims |
| total_claims | integer | Total claims in this area |
| year | integer | Year of statistics |

### policy_claims_summary
| Column | Type | Description |
|--------|------|-------------|
| policy_number | string | Policy identifier |
| total_claims | integer | Number of claims |
| total_amount_paid | decimal | Sum of approved claim amounts |
| avg_claim_amount | decimal | Average claim value |
| last_claim_date | date | Most recent claim date |
| first_claim_date | date | Oldest claim date |
| claims_trend | string | INCREASING, STABLE, DECREASING |
| policy_type | string | AUTO, HOME, COMMERCIAL |
| fraud_claims_count | integer | Number of fraud-flagged claims |

## Quick Start

```bash
# 1. Generate sample data
python generate_sample_data.py --output-dir ./sample_data

# 2. Set environment variables
export FABRIC_WORKSPACE_ID="your-workspace-guid"
export FABRIC_LAKEHOUSE_ID="your-lakehouse-guid"

# 3. Upload to Fabric Files section
python upload_to_fabric.py --data-dir ./sample_data

# 4. Load as Delta tables
python load_to_tables.py

# 5. Validate
python validate_data.py --data-dir ./sample_data
```

## Notes

- The sample data is synthetic and designed to demonstrate the agent's capabilities
- Adjust the data volume in `generate_sample_data.py` based on your needs (default: 10,000 claims)
- For production, connect to your actual claims data warehouse
- The `claims_data` folder in Files can be refreshed by re-running the upload script
