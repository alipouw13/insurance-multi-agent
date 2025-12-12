# Contoso Claims - Multi-Agent Insurance Claims Platform

## Original Source

This project is based on the [Insurance Multi-Agent Demo](https://github.com/alisoliman/insurance-multi-agent). It has been enhanced with **Azure AI Agent Service** integration for production-ready agentic workflows.

## Overview

An **Agentic AI Claims Demo** powered by advanced multi-agent systems leveraging **Azure AI Agent Service** and **Azure OpenAI (GPT-4o)**, designed to streamline and enhance the end-to-end insurance claims process. This implementation showcases a cutting-edge architecture where specialized AI agents collaboratively assess claims, delivering instant, transparent, and explainable recommendations directly to claims processors. By augmenting human decision-making, the solution significantly accelerates claim handling—reducing processing time from hours to minutes—while enhancing consistency, transparency, and customer satisfaction.

## What This Demo Showcases

### Multi-Agent Architecture with Azure AI Agent Service
Unlike traditional single-model AI systems, Contoso Claims employs a **collaborative multi-agent approach** powered by **Azure AI Agent Service**, where specialized AI agents work together:

- **Claim Assessor Agent** - Analyzes damage photos, evaluates repair costs, and validates claim consistency
- **Policy Checker Agent** - Verifies coverage terms, searches policy documents, and determines claim eligibility  
- **Risk Analyst Agent** - Detects fraud patterns, analyzes claimant history, and assesses risk factors
- **Communication Agent** - Generates personalized customer emails and requests missing documentation
- **Supervisor Agent** - Orchestrates the workflow and synthesizes final recommendations

### Azure AI Agent Service Integration
This implementation leverages **Azure AI Foundry's Agent Service** for production-grade agent orchestration:

- **Managed Agent Lifecycle** - Automatic deployment and management of agents in Azure AI Foundry
- **Function Calling** - Native tool integration with automatic execution via FunctionTool and ToolSet
- **Thread-based Conversations** - Persistent conversation threads for complex multi-turn interactions
- **Agent Reusability** - Smart agent discovery prevents duplicate deployments across restarts
- **Fallback Architecture** - Graceful degradation to LangGraph implementation when Azure agents unavailable

### Agent Behaviors & Capabilities

#### Claim Assessor
- **Multimodal Analysis**: Processes damage photos using Azure OpenAI LLMs with vision Capabilities
- **Cost Validation**: Cross-references repair estimates with vehicle specifications
- **Documentation Review**: Evaluates completeness of supporting evidence
- **Damage Assessment**: Provides detailed analysis of incident consistency

#### Policy Checker  
- **Coverage Verification**: Searches policy documents using semantic similarity
- **Multi-language Support**: Handles both English and Dutch insurance policies
- **Exclusion Analysis**: Identifies policy limitations and coverage gaps
- **Intelligent Search**: Uses vector embeddings for accurate policy matching

#### Risk Analyst
- **Fraud Detection**: Analyzes patterns indicative of fraudulent claims
- **History Analysis**: Reviews claimant's previous claim patterns
- **Risk Scoring**: Provides quantitative risk assessments
- **Red Flag Identification**: Highlights suspicious claim elements

#### Communication Agent
- **Personalized Messaging**: Crafts contextual customer communications
- **Missing Document Requests**: Generates specific requests for additional evidence
- **Professional Tone**: Maintains appropriate insurance industry language
- **Template Generation**: Creates reusable communication templates

## Architecture

### Technology Stack
- **Multi-Agent Framework**: Azure AI Agent Service with LangGraph fallback
- **Agent Orchestration**: Azure AI Foundry project-based deployment
- **AI Provider**: Azure OpenAI (GPT-4o, GPT-4.1-mini)
- **Backend**: FastAPI with async/await patterns
- **Frontend**: Next.js 15 with React 19 and shadcn/ui
- **Search**: FAISS vector database for policy retrieval
- **Infrastructure**: Azure Container Apps
- **Authentication**: Azure DefaultAzureCredential (Azure CLI, Managed Identity)

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  Next.js Frontend (React 19 + shadcn/ui) - Port 3000           │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/REST
┌───────────────────────────▼─────────────────────────────────────┐
│                    FastAPI Backend - Port 8000                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              API Layer (v1 Endpoints)                       │ │
│  │  /workflow/sample-claims  /agent/{name}/run                │ │
│  └────────────────────┬───────────────────────────────────────┘ │
│                       │                                          │
│  ┌────────────────────▼───────────────────────────────────────┐ │
│  │           Azure Agent Manager (Startup)                     │ │
│  │  - Deploy agents to Azure AI Foundry on startup            │ │
│  │  - Check for existing agents (prevent duplicates)          │ │
│  │  - Store agent IDs for routing                             │ │
│  └────────────────────┬───────────────────────────────────────┘ │
│                       │                                          │
│  ┌────────────────────▼───────────────────────────────────────┐ │
│  │         Single Agent Service (Routing Logic)                │ │
│  │  if Azure Agent Available: use Azure AI Agent Service      │ │
│  │  else: fallback to LangGraph implementation                │ │
│  └─────┬──────────────────────────────────────────────────────┘ │
└────────┼─────────────────────────────────────────────────────────┘
         │
         ├──────────────────┬──────────────────┐
         │                  │                  │
┌────────▼─────────┐ ┌──────▼────────┐ ┌──────▼──────────┐
│ Azure AI Agent   │ │   LangGraph   │ │  Policy Search  │
│    Service       │ │    Fallback   │ │   (FAISS)       │
│                  │ │               │ │                 │
│ - Agent Threads  │ │ - Local Exec  │ │ - Vector Store  │
│ - Function Call  │ │ - react_agent │ │ - Embeddings    │
│ - Auto Execution │ │               │ │                 │
└────────┬─────────┘ └───────────────┘ └─────────────────┘
         │
         │ Deployed in Azure AI Foundry
┌────────▼──────────────────────────────────────────────────────┐
│              Azure AI Foundry Project                          │
│  https://insurance-resource.services.ai.azure.com              │
│                                                                 │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ Claim Assessor  │  │  Policy Checker  │  │Risk Analyst  │ │
│  │  Agent          │  │  Agent           │  │  Agent       │ │
│  │  asst_xxx...    │  │  asst_yyy...     │  │  asst_zzz... │ │
│  │                 │  │                  │  │              │ │
│  │ Tools:          │  │ Tools:           │  │ Tools:       │ │
│  │ - get_vehicle   │  │ - get_policy     │  │ - get_claim  │ │
│  │ - analyze_image │  │ - search_docs    │  │   _history   │ │
│  └─────────────────┘  └──────────────────┘  └──────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │          Communication Agent                             │  │
│  │          asst_aaa...                                     │  │
│  │          (No tools - pure language model)                │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                          │
                          │ Uses
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Azure OpenAI Service                          │
│  Model: gpt-4o / gpt-4.1-mini                                  │
│  API Version: 2024-08-01-preview                               │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Workflow

```
User Request
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  1. API Endpoint receives claim processing request  │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  2. Single Agent Service checks agent availability  │
│     - Is Azure agent deployed? Use Azure            │
│     - Not deployed? Use LangGraph                   │
└──────────────────┬──────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       │                       │
       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  Azure AI Agent  │    │   LangGraph      │
│                  │    │   Agent          │
│ 1. Create Thread │    │ 1. Create State  │
│ 2. Add Message   │    │ 2. Execute Graph │
│ 3. Run Agent     │    │ 3. Return Result │
│ 4. Poll Status   │    │                  │
│ 5. Fetch Result  │    │                  │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  3. Agent calls registered tools automatically       │
│     - get_vehicle_details(vin)                      │
│     - search_policy_documents(query)                │
│     - get_claimant_history(claimant_id)            │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  4. Agent generates assessment with tool results    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  5. Return structured response to client            │
│     - Assessment text                               │
│     - Tool call logs                                │
│     - Confidence scores                             │
└─────────────────────────────────────────────────────┘
```

### Agent Deployment Lifecycle

```
Application Startup
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  Azure Agent Manager: deploy_azure_agents()         │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  For each agent type:                               │
│    1. Connect to Azure AI Foundry Project           │
│    2. List existing agents                          │
│    3. Search for agent by name                      │
│    4. If found: reuse existing agent ID             │
│    5. If not found: create new agent                │
│    6. Register agent ID in global cache             │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Agent IDs cached in memory:                        │
│  {                                                   │
│    "claim_assessor": "asst_xxx...",                │
│    "policy_checker": "asst_yyy...",                │
│    "risk_analyst": "asst_zzz...",                  │
│    "communication_agent": "asst_aaa..."            │
│  }                                                   │
└─────────────────────────────────────────────────────┘
```

## Key Features

### Azure AI Agent Service Integration
- **Managed Agent Deployment**: Agents automatically deployed to Azure AI Foundry on startup
- **Agent Reusability**: Smart discovery prevents duplicate agent creation across restarts
- **Native Function Calling**: Tools registered via FunctionTool with automatic execution
- **Thread-Based Conversations**: Persistent conversation threads for complex interactions
- **Graceful Fallback**: Automatic fallback to LangGraph when Azure agents unavailable

### Core Capabilities
- **Real-time Agent Collaboration**: Watch agents work together in live workflows
- **Explainable AI**: Full transparency into agent reasoning and decision paths
- **Document Intelligence**: PDF processing and semantic search across policies
- **Multimodal Processing**: Image analysis for damage assessment using Azure OpenAI vision
- **Interactive Demos**: Individual agent testing and complete workflow simulation
- **Production Ready**: Deployed on Azure with enterprise security and managed identity

## Development Setup

### Prerequisites
- Python 3.12+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) for Python dependency management
- Azure OpenAI account
- Azure AI Foundry project (for Azure AI Agent Service)
- Azure CLI (`az login` for authentication)

### Environment Configuration

Create a `.env` file in the backend directory:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Azure AI Foundry Project (for Azure AI Agent Service)
PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/projects/your-project-name

# Azure Blob Storage (for document storage)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=your-account;AccountKey=your-key;EndpointSuffix=core.windows.net
AZURE_STORAGE_CONTAINER_NAME=insurance-documents

# Azure AI Search (for document indexing)
AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AZURE_SEARCH_API_KEY=your-search-admin-key
AZURE_SEARCH_INDEX_NAME=insurance-policies
```

### Azure Resources Required

The application requires the following Azure resources:

1. **Azure OpenAI Service**: For LLM and embedding models
   - Deployments: `gpt-4o`, `gpt-4.1-mini`, `text-embedding-3-large`
   - API version: `2024-08-01-preview`

2. **Azure AI Foundry Project**: For Azure AI Agent Service
   - Manages 4 specialized agents (Claim Assessor, Policy Checker, Risk Analyst, Communication Agent)
   - Handles agent lifecycle and function calling

3. **Azure Storage Account**: For document storage
   - Container: `insurance-documents` (auto-created)
   - Stores uploaded policy documents, regulations, and reference materials
   - Provides SAS token-based secure access

4. **Azure AI Search**: For semantic document search
   - Index: `insurance-policies` (auto-created)
   - Vector search enabled with HNSW algorithm
   - Dimensions: 3072 (for text-embedding-3-large)
   - Supports hybrid search (vector + keyword)

### Authentication for Azure AI Agent Service

The application uses `DefaultAzureCredential` for authentication. Authenticate via Azure CLI:

```bash
az login
```

This enables the application to:
- Deploy agents to Azure AI Foundry
- Execute agent runs with function calling
- Manage agent lifecycle (create, reuse, delete)

### Backend Setup

Install dependencies:
```bash
cd backend
uv venv
uv pip install -r pyproject.toml
```

Ensure you're authenticated with Azure CLI:
```bash
az login
```

Start the backend server:
```bash
uv run fastapi dev
```

On startup, the application will:
1. Connect to Azure AI Foundry using `DefaultAzureCredential`
2. Check for existing agents by name (duplicate prevention)
3. Deploy 4 specialized agents if they don't exist:
   - Claim Assessor (`asst_xxx...`)
   - Policy Checker (`asst_yyy...`)
   - Communication Agent (`asst_aaa...`)
   - Risk Analyst (`asst_zzz...`)
4. Store agent IDs in global cache for request routing
5. Initialize Azure Blob Storage container (`insurance-documents`)
6. Create Azure AI Search index (`insurance-policies`) with vector search

The API will be available at http://localhost:8000

### Document Management with Azure

The application uses Azure Blob Storage and AI Search for document management:

**Upload Documents**:
- Documents are uploaded to Azure Blob Storage (not local filesystem)
- Organized in containers: `policy/`, `regulation/`, `reference/`
- Each document receives a unique blob name with metadata

**Indexing**:
- Documents are automatically indexed in Azure AI Search
- Text is split into 1000-character chunks with 200-character overlap
- Each chunk is embedded using `text-embedding-3-large` (3072 dimensions)
- Vector search uses HNSW algorithm for fast similarity search

**Search**:
- Semantic search combines vector similarity and keyword matching
- Results include source attribution and policy section references
- Configurable score thresholds filter low-quality matches

**Migration from Local Storage**:
To migrate existing local documents to Azure:
1. Documents currently in `backend/app/workflow/data/uploaded_docs/` 
2. Can be uploaded via the `/api/v1/documents/upload` endpoint
3. The old FAISS index in `backend/app/workflow/data/policy_index/` is replaced by Azure AI Search

### Frontend Setup

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

The frontend will be available at http://localhost:3000


## 🌐 Azure Deployment

### Prerequisites
- [Azure Developer CLI (azd)](https://docs.microsoft.com/en-us/azure/developer/azure-developer-cli/)
- Azure subscription with appropriate permissions

### Deploy to Azure Container Apps
```bash
# Login to Azure
azd auth login

# Initialize and deploy
azd up
```

This will:
1. Create Azure Container Apps environment
2. Set up container registry with managed identity
3. Deploy both frontend and backend containers
4. Configure networking and CORS policies
5. Output the deployed application URLs

### Infrastructure
The deployment creates:
- **Container Apps Environment** with consumption-based scaling
- **Azure Container Registry** for image storage
- **Managed Identity** for secure registry access
- **Log Analytics Workspace** for monitoring
- **HTTPS endpoints** with automatic SSL certificates

## Demo Scenarios

### Individual Agent Testing
- `/agents/claim-assessor` - Test damage photo analysis with vehicle detail extraction
- `/agents/policy-checker` - Verify coverage scenarios with multilingual support (Dutch/English)
- `/agents/risk-analyst` - Fraud detection demos with claimant history analysis
- `/agents/communication-agent` - Professional email generation

### Complete Workflow
- Go to `/demo` for end-to-end claim processing
- Upload damage photos and watch multimodal analysis
- See agents collaborate in real-time via Azure AI Foundry
- Review final assessment with full reasoning chains

### Sample Claims
The system includes realistic test scenarios:
- Standard auto collision claim (CLM-001)
- High-value vehicle damage
- Dutch language insurance claim
- High-risk fraud scenario (CLM-002)

## Testing Azure AI Agents

The project includes comprehensive tests for all Azure AI Agent Service agents:

### Running Tests

```bash
cd backend

# Run all agent tests
uv run python tests/run_all_tests.py

# Run individual agent test
uv run pytest tests/test_azure_claim_assessor.py
uv run pytest tests/test_azure_policy_checker.py
uv run pytest tests/test_azure_communication_agent.py
uv run pytest tests/test_azure_risk_analyst.py

# Cleanup test agents (if needed)
uv run python tests/cleanup_agents.py
```

### Test Coverage

Each agent test validates:
- Agent deployment to Azure AI Foundry
- Function tool calling and execution
- Response quality and reasoning
- Proper cleanup (agent deletion after tests)

Test scenarios include:
- Claim Assessor: Vehicle damage assessment with image analysis
- Policy Checker: Policy verification and document search
- Communication Agent: Email drafting in professional tone
- Risk Analyst: Low-risk and high-risk fraud detection

See `tests/README.md` for detailed test documentation.

## Project Structure

```
simple-insurance-multi-agent/
├── backend/                            # FastAPI application
│   ├── app/
│   │   ├── api/v1/                    # REST API endpoints
│   │   ├── workflow/                  # Agent orchestration
│   │   │   ├── agents/                # Azure AI Agent Service implementations
│   │   │   │   ├── azure_claim_assessor.py       # Damage assessment agent
│   │   │   │   ├── azure_policy_checker.py       # Policy verification agent
│   │   │   │   ├── azure_communication_agent.py  # Email generation agent
│   │   │   │   └── azure_risk_analyst.py         # Fraud detection agent
│   │   │   ├── azure_agent_manager.py   # Agent deployment orchestrator
│   │   │   ├── azure_agent_client.py    # Azure AI Foundry client
│   │   │   ├── tools.py                 # Function tools for agents
│   │   │   ├── supervisor.py            # Workflow orchestration (LangGraph)
│   │   │   └── registry.py              # Agent registry
│   │   ├── core/                        # Configuration and logging
│   │   └── services/                    # Business logic layer
│   ├── tests/                           # Agent tests with cleanup
│   │   ├── test_azure_claim_assessor.py
│   │   ├── test_azure_policy_checker.py
│   │   ├── test_azure_communication_agent.py
│   │   ├── test_azure_risk_analyst.py
│   │   ├── run_all_tests.py             # Test orchestrator
│   │   └── cleanup_agents.py            # Manual cleanup utility
│   └── pyproject.toml                   # Python dependencies
├── frontend/                            # Next.js application
│   ├── app/                            # App router pages
│   ├── components/                     # Reusable UI components
│   └── lib/                            # API clients and utilities
├── infra/                              # Azure Bicep templates
└── azure.yaml                          # Azure deployment configuration
```

## Explainable AI Features

- **Decision Trees**: Visual representation of agent reasoning
- **Source Attribution**: Links decisions to specific policy documents  
- **Confidence Scoring**: Quantitative assessment of decision certainty
- **Audit Trails**: Complete log of agent interactions for compliance
- **Human Intervention Points**: Clear override capabilities for human reviewers

## Azure AI Agent Service Integration Details

### Agent Lifecycle Management

Agents are automatically deployed on application startup:

1. **Initialization**: `azure_agent_manager.py` deploys all 4 agents
2. **Duplicate Prevention**: `find_agent_by_name()` checks for existing agents
3. **Agent Creation**: Only creates agents that don't exist in Azure AI Foundry
4. **ID Caching**: Stores agent IDs in global `_AZURE_AGENT_IDS` dictionary
5. **Request Routing**: FastAPI routes requests to appropriate agent by cached ID

### Function Tool Registration

Each agent registers custom tools for specialized tasks:

- **Claim Assessor**: `get_vehicle_details()`, `analyze_image()`
- **Policy Checker**: `get_policy_details()`, `search_policy_documents()`
- **Risk Analyst**: `get_claimant_history()`
- **Communication Agent**: No tools (pure language model)

Tools are registered using `FunctionTool.from_function_def()` with structured schemas.

### Thread-based Conversations

Each agent interaction creates an isolated thread:

1. Create thread via `project_client.agents.create_thread()`
2. Add user message to thread
3. Create run with agent ID and enable function calling
4. Poll run status until completion
5. Fetch response messages from thread
6. Extract assistant responses

### Fallback Architecture

The system maintains both Azure AI Agent Service and LangGraph implementations:

- Primary: Azure AI Agent Service (managed agents in Azure AI Foundry)
- Fallback: LangGraph (local multi-agent workflows)
- Selection: Configurable via environment or feature flags

This ensures high availability and allows gradual migration.

## License

MIT License - see LICENSE file for details.

---

Built with Azure AI Agent Service to demonstrate the future of insurance claim processing.