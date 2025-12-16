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

The system uses a supervisor pattern with specialized agents:

1. **Claim Assessor**: Analyzes claim details and identifies key information
2. **Policy Checker**: Searches and validates policy coverage
3. **Risk Analyst**: Evaluates risk factors and fraud indicators
4. **Communication Agent**: Generates customer-facing communications

The supervisor coordinates agent execution, manages state, and aggregates results.

## Evaluation

The system supports Azure AI Foundry evaluations with metrics:
- **Groundedness**: Factual accuracy based on context
- **Relevance**: Response alignment with query
- **Coherence**: Logical flow and consistency
- **Fluency**: Natural language quality

Results are stored in Cosmos DB and can be viewed in Azure AI Foundry portal.