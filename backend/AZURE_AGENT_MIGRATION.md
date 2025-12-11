# Azure AI Agent Service Migration

This document describes the migration from LangGraph agents to Azure AI Agent Service.

## Prerequisites

### 1. Azure AI Foundry Project

You need an Azure AI Foundry project with:
- A deployed chat model (e.g., gpt-4.1-mini, gpt-4o)
- Proper access permissions (Azure AI User role)

### 2. Get Your Project Endpoint

1. Go to [Azure AI Foundry Portal](https://ai.azure.com)
2. Navigate to your project
3. Go to **Project Overview** → **Libraries** → **Foundry**
4. Copy the endpoint (format: `https://<your-resource>.services.ai.azure.com/api/projects/<project-name>`)
5. Set it in your `.env` file:
   ```
   PROJECT_ENDPOINT=https://your-resource.services.ai.azure.com/api/projects/your-project
   ```

### 3. Azure Authentication

The agents use `DefaultAzureCredential` for authentication. Make sure you're logged in:
```bash
az login
```

## Agent Migration Status

### ✅ Completed
- [x] **Claim Assessor** - Migrated to Azure AI Agent Service
  - Tools: `get_vehicle_details_function`, `analyze_image_function`
  - File: `app/workflow/agents/azure_claim_assessor.py`

### 🔄 In Progress
- [ ] **Policy Checker** - To be migrated
- [ ] **Risk Analyst** - To be migrated
- [ ] **Communication Agent** - To be migrated
- [ ] **Supervisor/Orchestration** - To be adapted

## Architecture Changes

### Before (LangGraph)
```python
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(
    model=llm,
    tools=[tool1, tool2],
    prompt="instructions",
    name="agent_name"
)
```

### After (Azure AI Agent Service)
```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, ToolSet

# Create client
project_client = AIProjectClient(
    endpoint=settings.project_endpoint,
    credential=DefaultAzureCredential()
)

# Define function tools
functions = FunctionTool(functions={func1, func2})
toolset = ToolSet()
toolset.add(functions)

# Create agent
agent = project_client.agents.create_agent(
    model="gpt-4o",
    name="agent_name",
    instructions="instructions",
    toolset=toolset
)
```

## Key Differences

### Tool Definition
- **LangGraph**: Uses `@tool` decorator from langchain_core
- **Azure AI Agent Service**: Wraps functions in `FunctionTool` and adds to `ToolSet`

### Agent Execution
- **LangGraph**: `agent.invoke({"messages": [...]})` returns graph state
- **Azure AI Agent Service**: Uses threads + runs pattern:
  1. Create thread
  2. Add message to thread
  3. Create and process run
  4. Fetch messages from thread

### State Management
- **LangGraph**: Built-in state graph with message history
- **Azure AI Agent Service**: Thread-based conversation management

## Testing

To test an individual Azure AI agent:

1. Ensure `PROJECT_ENDPOINT` is set in `.env`
2. Run `az login` to authenticate
3. The agent will be created on first use
4. Use the `/api/v1/agent/{agent_name}/run` endpoint

## Cost Considerations

- Azure AI Agent Service agents persist in your Foundry project
- Each agent creation uses Azure resources
- Consider cleanup of test agents during development:
  ```python
  from app.workflow.azure_agent_client import delete_agent
  delete_agent(agent_id)
  ```

## Next Steps

1. ✅ Migrate remaining agents (policy_checker, risk_analyst, communication_agent)
2. 🔄 Update supervisor/orchestration to work with Azure AI Agent Service
3. ⏳ Test multi-agent workflows
4. ⏳ Update frontend if needed

## Troubleshooting

### "PROJECT_ENDPOINT environment variable must be set"
- Check that `.env` contains `PROJECT_ENDPOINT`
- Restart the FastAPI server after updating `.env`

### "Authentication failed"
- Run `az login` in your terminal
- Ensure you have the correct Azure subscription selected
- Verify you have **Azure AI User** role on the Foundry project

### "Model deployment not found"
- Verify `AZURE_OPENAI_DEPLOYMENT_NAME` matches a deployed model in your project
- Check **Models + Endpoints** in Azure AI Foundry portal
