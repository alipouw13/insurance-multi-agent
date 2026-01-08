# Insurance Multi-Agent Backend

FastAPI backend service for the Insurance Claims Processing multi-agent system, powered by Azure AI services.

## Features

- **Multi-Agent Orchestration**: Supervisor-based workflow with specialized agents (Claim Assessor, Policy Checker, Risk Analyst, Communication Agent)
- **Azure AI Integration**: OpenAI GPT-4o-mini, Azure AI Agent Service, AI Foundry Evaluations
- **Document Processing**: Azure AI Search, Blob Storage, Content Understanding for document analysis
- **Data Persistence**: Azure Cosmos DB for agent data, executions, and evaluation results
- **Observability**: Application Insights telemetry and structured logging
- **API Documentation**: Interactive OpenAPI/Swagger UI
- **Docker Containerization**: Production-ready container deployment

## Getting Started

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Install uv if you don't have it already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create and activate a virtual environment:

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
```

3. Install dependencies:

```bash
uv pip install -e .
```

4. Create a `.env` file based on the `.env.sample` template:

```bash
cp .env.sample .env
```

5. Configure required Azure services in `.env`:
   - Azure OpenAI (API key, endpoint, deployment names)
   - Azure AI Foundry Project (project endpoint)
   - Azure Cosmos DB (endpoint)
   - Azure Blob Storage (account name)
   - Azure AI Search (endpoint, index name)
   - Application Insights (connection string)
   - Optional: Azure Content Understanding (for document analysis)

### Running the Application

**If using Fabric Data Agent integration**, first authenticate with your user account:

```bash
# Required for Fabric Data Agent - uses user identity passthrough
az login
```

> **Note**: Fabric Data Agent only supports user identity authentication, not service principals. The `az login` step ensures your user identity is used when querying Fabric data.

Start the development server:

```bash
uvicorn app.main:app --reload
```

Or use the fastapi CLI:

```bash
fastapi dev
```

The API will be available at http://localhost:8000 with documentation at http://localhost:8000/api/docs.

### Running Tests

Run the tests with pytest:

```bash
uv run pytest
```

### Docker

Build and run the Docker container:

```bash
# Build the image
docker build -t shadcn-fastapi-backend .

# Run the container
docker run -p 8000:80 shadcn-fastapi-backend
```

## API Endpoints

### Workflow Execution
- `POST /api/v1/workflow/process-claim` - Process insurance claim through multi-agent workflow
- `GET /api/v1/workflow/executions` - List all workflow executions
- `GET /api/v1/workflow/executions/{execution_id}` - Get specific execution details

### Agent Management
- `GET /api/v1/agents` - List all available agents
- `GET /api/v1/agents/{agent_id}` - Get agent configuration
- `POST /api/v1/agents/{agent_id}/execute` - Execute single agent

### Document Management
- `POST /api/v1/documents/upload` - Upload documents to Azure Blob Storage
- `GET /api/v1/documents` - List all documents
- `POST /api/v1/documents/analyze` - Analyze document with Content Understanding
- `POST /api/v1/documents/{document_id}/index` - Index document in AI Search

### Evaluation
- `POST /api/v1/evaluation/evaluate` - Run AI evaluation on agent responses
- `GET /api/v1/evaluation/results` - Get evaluation results

### Health Check
- `GET /` - Service health status

Access API documentation at http://localhost:8000/api/docs

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/      # API endpoint handlers
│   │           ├── agents.py   # Agent management
│   │           ├── documents.py # Document operations
│   │           ├── evaluation.py # AI evaluation
│   │           └── workflow.py  # Workflow execution
│   ├── core/
│   │   ├── config.py           # Settings and configuration
│   │   └── logging_config.py   # Logging setup
│   ├── models/
│   │   ├── agent.py            # Agent data models
│   │   └── claim.py            # Claim data models
│   ├── services/
│   │   ├── claim_processing.py # Claim processing logic
│   │   ├── evaluation_service.py # AI evaluation
│   │   ├── single_agent.py     # Single agent execution
│   │   └── content_understanding_service.py # Document analysis
│   ├── workflow/
│   │   ├── agents/             # Agent implementations
│   │   ├── supervisor.py       # Multi-agent orchestrator
│   │   ├── tools.py            # Agent tools
│   │   └── policy_search.py    # Document retrieval
│   └── main.py                 # FastAPI application
├── build_policy_index.py       # Initialize AI Search index
├── .env.sample                 # Environment variables template
├── Dockerfile                  # Container configuration
├── pyproject.toml              # Dependencies
└── README.md                   # This file
```

## Azure Services Integration

The backend integrates with these Azure services:

- **Azure OpenAI**: GPT-4o-mini for LLM reasoning, text-embedding-3-large for semantic search
- **Azure AI Foundry**: AI Agent Service and evaluation portal
- **Azure Cosmos DB**: Stores agent definitions, executions, token usage, evaluations
- **Azure Blob Storage**: Document storage for policies and claims
- **Azure AI Search**: Semantic search for policy documents
- **Azure Content Understanding**: Document analysis and field extraction
- **Application Insights**: Application performance monitoring and telemetry

## Multi-Agent Architecture

The system uses a supervisor pattern with specialized agents deployed to Azure AI Foundry.

### Deployed Agents

When the application starts with `USE_AZURE_AGENTS=true`, the following agents are automatically created in Azure AI Foundry:

| Agent Name | ID in Foundry | Description | Tools |
|------------|---------------|-------------|-------|
| **Insurance Supervisor** | `insurance_supervisor_v2` | Orchestrates the multi-agent workflow, coordinates specialists, and aggregates results | Function tools to call specialist agents |
| **Claim Assessor** | `claim_assessor_v2` | Analyzes claim details, validates damage estimates, processes supporting images | `analyze_image` for damage photo analysis |
| **Policy Checker** | `policy_checker_v2` | Searches policy documents, validates coverage, checks exclusions | `search_policy_documents` for RAG search |
| **Risk Analyst** | `risk_analyst_v2` | Evaluates fraud indicators, assesses risk scores, identifies patterns | None (analysis-based) |
| **Communication Agent** | `communication_agent_v2` | Generates customer-facing emails and communications | None (generation-based) |
| **Claims Data Analyst** | `claims_data_analyst_v2` | Queries enterprise claims data using natural language (Fabric integration) | `FabricTool` connected to Fabric Data Agent |

### Optional Agents

The **Claims Data Analyst** agent is only created when Fabric integration is enabled:

```bash
# Enable in .env
USE_AZURE_AGENTS=true
USE_FABRIC_DATA_AGENT=true
FABRIC_CONNECTION_NAME=your-fabric-connection-name
```

This agent uses the `FabricTool` to connect to a Microsoft Fabric Data Agent, enabling natural language queries against enterprise data in Fabric Lakehouse. See the [`fabric/README.md`](fabric/README.md) for setup instructions.

### Workflow Coordination

The supervisor coordinates agent execution, manages state, and aggregates results. The workflow follows this pattern:

1. **Claim Assessment**: Claim Assessor analyzes the claim details and damage
2. **Policy Validation**: Policy Checker searches for relevant coverage
3. **Risk Analysis**: Risk Analyst evaluates fraud indicators
4. **Data Analysis** (optional): Claims Data Analyst queries historical data
5. **Communication**: Communication Agent drafts customer response
6. **Final Decision**: Supervisor aggregates all inputs and makes recommendation

## Evaluation

The system supports Azure AI Foundry evaluations with metrics:
- **Groundedness**: Factual accuracy based on context
- **Relevance**: Response alignment with query
- **Coherence**: Logical flow and consistency
- **Fluency**: Natural language quality

Results are stored in Cosmos DB and can be viewed in Azure AI Foundry portal.