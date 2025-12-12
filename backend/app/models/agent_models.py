"""Pydantic models for agent persistence and tracking in Cosmos DB."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Types of agents in the insurance workflow."""
    CLAIM_ASSESSOR = "claim_assessor"
    POLICY_CHECKER = "policy_checker"
    RISK_ANALYST = "risk_analyst"
    COMMUNICATION_AGENT = "communication_agent"


class AgentVersion(BaseModel):
    """Version information for an agent definition."""
    version: str = Field(description="Semantic version (e.g., 1.0.0)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(default="system")
    changelog: str = Field(default="", description="What changed in this version")


class AgentToolDefinition(BaseModel):
    """Definition of a tool available to an agent."""
    name: str = Field(description="Tool function name")
    description: str = Field(description="What the tool does")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")


class AgentDefinition(BaseModel):
    """Complete agent definition stored in Cosmos DB."""
    id: str = Field(description="Unique agent ID (partition key)")
    agent_type: AgentType = Field(description="Type of agent")
    name: str = Field(description="Human-readable agent name")
    description: str = Field(description="Agent purpose and capabilities")
    instructions: str = Field(description="System prompt/instructions for the agent")
    model_deployment: str = Field(default="gpt-4o", description="Azure OpenAI deployment name")
    temperature: float = Field(default=0.1, description="Model temperature setting")
    tools: List[AgentToolDefinition] = Field(default_factory=list, description="Available tools")
    version: str = Field(default="1.0.0", description="Current version")
    version_history: List[AgentVersion] = Field(default_factory=list, description="Version changelog")
    is_active: bool = Field(default=True, description="Whether agent is currently active")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "claim_assessor_v1",
                "agent_type": "claim_assessor",
                "name": "Claim Assessor",
                "description": "Evaluates damage and assesses repair costs",
                "instructions": "You are a claim assessor...",
                "model_deployment": "gpt-4o",
                "temperature": 0.1,
                "tools": [
                    {
                        "name": "get_vehicle_details",
                        "description": "Retrieve vehicle information",
                        "parameters": {"vin": "string"}
                    }
                ],
                "version": "1.0.0",
                "is_active": True
            }
        }


class ExecutionStatus(str, Enum):
    """Status of an agent execution."""
    STARTED = "started"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AgentStepExecution(BaseModel):
    """Individual agent step within a workflow execution."""
    agent_type: AgentType = Field(description="Which agent executed this step")
    agent_version: str = Field(description="Version of agent that executed")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input to the agent")
    output_data: Dict[str, Any] = Field(default_factory=dict, description="Agent's response")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Tools invoked by agent")
    token_usage: Dict[str, int] = Field(default_factory=dict, description="Tokens used in this step")
    status: ExecutionStatus = Field(default=ExecutionStatus.STARTED)
    error_message: Optional[str] = None


class AgentExecution(BaseModel):
    """Complete workflow execution record stored in Cosmos DB."""
    id: str = Field(description="Unique execution ID (partition key)")
    workflow_id: str = Field(description="Claim ID or workflow identifier")
    workflow_type: str = Field(default="claim_processing", description="Type of workflow")
    claim_id: str = Field(description="Insurance claim ID being processed")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: ExecutionStatus = Field(default=ExecutionStatus.STARTED)
    
    # Complete workflow trace
    agent_steps: List[AgentStepExecution] = Field(default_factory=list, description="All agent executions in order")
    
    # Aggregated metrics
    total_tokens: int = Field(default=0, description="Total tokens across all steps")
    total_cost: float = Field(default=0.0, description="Estimated cost in USD")
    agents_invoked: List[str] = Field(default_factory=list, description="List of agent types used")
    
    # Context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Result
    final_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "exec_123456",
                "workflow_id": "claim_AUTO_001",
                "workflow_type": "claim_processing",
                "claim_id": "AUTO_001",
                "status": "completed",
                "agent_steps": [
                    {
                        "agent_type": "claim_assessor",
                        "agent_version": "1.0.0",
                        "token_usage": {"prompt_tokens": 500, "completion_tokens": 200}
                    }
                ],
                "total_tokens": 700,
                "total_cost": 0.0105
            }
        }


class ServiceType(str, Enum):
    """Service types for token usage tracking."""
    AGENT_SERVICE = "agent_service"
    OPENAI_CHAT = "openai_chat"
    OPENAI_EMBEDDING = "openai_embedding"
    AI_SEARCH = "ai_search"
    DOCUMENT_INTELLIGENCE = "document_intelligence"


class OperationType(str, Enum):
    """Operation types for detailed tracking."""
    CLAIM_ASSESSMENT = "claim_assessment"
    POLICY_CHECK = "policy_check"
    RISK_ANALYSIS = "risk_analysis"
    COMMUNICATION = "communication"
    DOCUMENT_SEARCH = "document_search"
    DOCUMENT_EMBEDDING = "document_embedding"
    IMAGE_ANALYSIS = "image_analysis"


class TokenUsageRecord(BaseModel):
    """Comprehensive token usage record following OpenTelemetry standards."""
    id: str = Field(description="Unique record ID")
    record_id: str = Field(description="Same as id for Cosmos DB")
    
    # Trace context (OpenTelemetry)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    
    # Session & request context
    session_id: str = Field(description="User session identifier")
    user_id: Optional[str] = None
    claim_id: Optional[str] = None
    execution_id: Optional[str] = None
    
    # Service identification
    service_type: ServiceType = Field(description="Type of Azure service")
    operation_type: OperationType = Field(description="Specific operation being performed")
    agent_type: Optional[AgentType] = None
    agent_version: Optional[str] = None
    
    # Model information
    model_name: str = Field(description="Model or deployment name")
    deployment_name: Optional[str] = None
    model_version: Optional[str] = None
    
    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Cost information
    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    total_cost: float = 0.0
    cost_currency: str = "USD"
    
    # Request details
    endpoint: Optional[str] = None
    request_text: Optional[str] = None
    response_text: Optional[str] = None
    request_size_chars: int = 0
    response_size_chars: int = 0
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    
    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_start_time: Optional[float] = None
    request_end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    
    # Result information
    success: bool = True
    error_message: Optional[str] = None
    http_status_code: int = 200
    
    # Azure resource information
    azure_region: Optional[str] = None
    azure_subscription_id: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "token_123456",
                "record_id": "token_123456",
                "session_id": "sess_abc",
                "claim_id": "AUTO_001",
                "service_type": "openai_chat",
                "operation_type": "claim_assessment",
                "agent_type": "claim_assessor",
                "model_name": "gpt-4o",
                "prompt_tokens": 500,
                "completion_tokens": 200,
                "total_tokens": 700,
                "total_cost": 0.0105,
                "success": True
            }
        }
