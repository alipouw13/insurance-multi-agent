from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from app.api.v1.endpoints import workflow as workflow_endpoints
from app.api.v1.endpoints import files as files_endpoints
from app.api.v1.endpoints import agent as agent_endpoints
from app.workflow.policy_search import get_policy_search

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
frontend_origin = os.getenv("FRONTEND_ORIGIN")

# Default origins for local development
default_dev_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

# Azure Container Apps production origins
azure_origins = [
    "https://frontend-gqxcjz.redflower-818d79c8.eastus2.azurecontainerapps.io",
]

# Determine CORS configuration
if frontend_origin:
    # Explicit frontend origin set
    allow_origins = [frontend_origin]
    allow_origin_regex = None
    logger.info(f"CORS configured for explicit frontend origin: {frontend_origin}")
elif os.getenv("ALLOW_ALL_CORS", "false").lower() == "true":
    # Allow all origins (not recommended for production)
    allow_origins = ["*"]
    allow_origin_regex = None
    logger.warning("CORS is configured to allow all origins – set FRONTEND_ORIGIN for stricter policy.")
else:
    # Use development origins + regex for Azure Container Apps
    allow_origins = default_dev_origins + azure_origins
    allow_origin_regex = r"https://.*\.azurecontainerapps\.io"
    logger.info(f"CORS configured for development origins: {default_dev_origins}")
    logger.info(f"CORS configured for Azure origins: {azure_origins}")
    logger.info(f"CORS configured with regex pattern: {allow_origin_regex}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize policy search index and deploy Azure AI agents on startup."""
    # Initialize OpenTelemetry tracing
    logger.info("🚀 Setting up OpenTelemetry tracing...")
    try:
        from app.core.tracing import setup_tracing
        tracing_enabled = setup_tracing()
        if tracing_enabled:
            logger.info("✅ OpenTelemetry tracing configured with Azure Monitor")
        else:
            logger.info("ℹ️  Tracing disabled or not configured")
    except Exception as e:
        logger.warning(f"⚠️  Failed to setup tracing: {e}")
    
    # Initialize Cosmos DB for agent persistence
    logger.info("🚀 Initializing Cosmos DB for agent persistence...")
    try:
        from app.services.cosmos_service import get_cosmos_service
        cosmos_service = await get_cosmos_service()
        if cosmos_service._initialized:
            logger.info("✅ Cosmos DB initialized for agent tracking")
        else:
            logger.info("ℹ️  Cosmos DB not configured, agent persistence disabled")
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize Cosmos DB: {e}")
    
    # Initialize policy search index
    logger.info("🚀 Initializing policy search index...")
    try:
        policy_search = get_policy_search()
        logger.info("✅ Policy search index initialized successfully")
    except Exception as e:
        logger.error("❌ Failed to initialize policy search index: %s", e)
        # Don't raise - let the app start but log the error
    
    # Deploy Azure AI agents
    logger.info("🚀 Deploying Azure AI Agent Service agents...")
    try:
        from app.workflow.azure_agent_manager import deploy_azure_agents
        azure_agents = deploy_azure_agents()
        if azure_agents:
            logger.info(f"✅ Azure AI agents deployed: {list(azure_agents.keys())}")
        else:
            logger.info("ℹ️  Using LangGraph agents (Azure AI agents not available)")
    except Exception as e:
        logger.warning(f"⚠️  Failed to deploy Azure AI agents: {e}")
        logger.info("ℹ️  Using LangGraph agents as fallback")

# Root


@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "Hello World"}

# Mount API V1 routers
app.include_router(workflow_endpoints.router, prefix="/api/v1")
app.include_router(files_endpoints.router, prefix="/api/v1")
app.include_router(agent_endpoints.router, prefix="/api/v1")

# Import and mount document management endpoints (Azure-enabled)
from app.api.v1.endpoints import documents as documents_endpoints
# Import and mount agent management endpoints (Cosmos DB + OpenTelemetry)
from app.api.v1.endpoints import agent_management
from app.api.v1.endpoints import index_management as index_endpoints
# Import and mount evaluation endpoints
from app.api.v1.endpoints import evaluation as evaluation_endpoints

app.include_router(documents_endpoints.router, prefix="/api/v1")
app.include_router(agent_management.router, prefix="/api/v1")
app.include_router(index_endpoints.router, prefix="/api/v1")
app.include_router(evaluation_endpoints.router, prefix="/api/v1/evaluation")
