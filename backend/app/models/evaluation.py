"""Evaluation models for agent performance tracking."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class EvaluatorType(str, Enum):
    """Types of evaluators available."""
    FOUNDRY = "foundry"
    CUSTOM = "custom"


class EvaluationMetric(str, Enum):
    """Available evaluation metrics."""
    GROUNDEDNESS = "groundedness"
    RELEVANCE = "relevance"
    COHERENCE = "coherence"
    FLUENCY = "fluency"
    ACCURACY = "accuracy"


class EvaluationRequest(BaseModel):
    """Request model for evaluation."""
    evaluation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = Field(description="Agent execution ID to evaluate")
    claim_id: str = Field(description="Claim ID being processed")
    agent_type: str = Field(description="Type of agent being evaluated")
    question: str = Field(description="Input/question to the agent")
    answer: str = Field(description="Agent's response")
    context: List[str] = Field(default_factory=list, description="Context provided to agent")
    ground_truth: Optional[str] = None
    evaluator_type: EvaluatorType = Field(default=EvaluatorType.FOUNDRY)
    metrics: List[EvaluationMetric] = Field(
        default_factory=lambda: [
            EvaluationMetric.GROUNDEDNESS,
            EvaluationMetric.RELEVANCE,
            EvaluationMetric.COHERENCE,
            EvaluationMetric.FLUENCY
        ]
    )
    evaluation_model: str = Field(default="gpt-4o-mini")


class EvaluationResult(BaseModel):
    """Result of an evaluation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evaluation_id: str = Field(description="Links to request")
    execution_id: str = Field(description="Agent execution being evaluated")
    claim_id: str = Field(description="Claim ID")
    agent_type: str = Field(description="Agent type evaluated")
    evaluator_type: EvaluatorType
    
    # Scores (1-5 scale for Azure AI Foundry)
    groundedness_score: Optional[float] = None
    relevance_score: Optional[float] = None
    coherence_score: Optional[float] = None
    fluency_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    overall_score: Optional[float] = None
    
    # Details
    reasoning: Optional[str] = None
    feedback: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)
    detailed_scores: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    evaluation_model: str = Field(default="gpt-4o-mini")
    evaluation_duration_ms: Optional[int] = None
    evaluation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # Question/Answer being evaluated
    question: str = ""
    answer: str = ""
    context: List[str] = Field(default_factory=list)
    ground_truth: Optional[str] = None


class EvaluationSummary(BaseModel):
    """Summary of evaluations for an execution or claim."""
    execution_id: Optional[str] = None
    claim_id: Optional[str] = None
    agent_type: Optional[str] = None
    
    total_evaluations: int = 0
    avg_groundedness: Optional[float] = None
    avg_relevance: Optional[float] = None
    avg_coherence: Optional[float] = None
    avg_fluency: Optional[float] = None
    avg_overall: Optional[float] = None
    
    evaluator_type: EvaluatorType = EvaluatorType.FOUNDRY
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime = Field(default_factory=datetime.utcnow)
    
    best_performing_metrics: List[str] = Field(default_factory=list)
    worst_performing_metrics: List[str] = Field(default_factory=list)


class AgentEvaluationContext(BaseModel):
    """Context for evaluating an agent's performance."""
    claim_id: str
    agent_type: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    execution_id: str
    
    # For evaluation
    query: str = Field(description="What the agent was asked to do")
    response: str = Field(description="What the agent produced")
    context: List[str] = Field(default_factory=list, description="Information available to the agent")
    expected_behavior: Optional[str] = None
