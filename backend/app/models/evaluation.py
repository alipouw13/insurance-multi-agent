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
    SAFETY = "safety"
    RED_TEAM = "red_team"


class EvaluationMetric(str, Enum):
    """Available evaluation metrics.

    Quality metrics are scored 1-5 where higher is better.
    Safety metrics are scored 0-7 severity where LOWER is better.
    """
    # Quality (1-5, higher is better)
    GROUNDEDNESS = "groundedness"
    RELEVANCE = "relevance"
    COHERENCE = "coherence"
    FLUENCY = "fluency"
    RETRIEVAL = "retrieval"
    INTENT_RESOLUTION = "intent_resolution"
    TASK_ADHERENCE = "task_adherence"
    ACCURACY = "accuracy"
    # Safety (0-7 severity, lower is better)
    VIOLENCE = "violence"
    SEXUAL = "sexual"
    SELF_HARM = "self_harm"
    HATE_UNFAIRNESS = "hate_unfairness"
    # Safety (boolean label)
    INDIRECT_ATTACK = "indirect_attack"
    PROTECTED_MATERIAL = "protected_material"


#: Metrics scored on the 1-5 Likert scale where a higher score is better.
QUALITY_METRICS = {
    EvaluationMetric.GROUNDEDNESS,
    EvaluationMetric.RELEVANCE,
    EvaluationMetric.COHERENCE,
    EvaluationMetric.FLUENCY,
    EvaluationMetric.RETRIEVAL,
    EvaluationMetric.INTENT_RESOLUTION,
    EvaluationMetric.TASK_ADHERENCE,
    EvaluationMetric.ACCURACY,
}

#: Metrics scored on the 0-7 content-harm severity scale where a LOWER score is better.
SAFETY_SEVERITY_METRICS = {
    EvaluationMetric.VIOLENCE,
    EvaluationMetric.SEXUAL,
    EvaluationMetric.SELF_HARM,
    EvaluationMetric.HATE_UNFAIRNESS,
}

#: Metrics that return a boolean label rather than a numeric score.
SAFETY_LABEL_METRICS = {
    EvaluationMetric.INDIRECT_ATTACK,
    EvaluationMetric.PROTECTED_MATERIAL,
}

#: Default judge model used when no deployment is configured.
DEFAULT_EVALUATION_MODEL = "gpt-4.1-mini"


class EvaluationStatus(str, Enum):
    """Outcome of an evaluation run."""
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class MetricScore(BaseModel):
    """A single metric result, carrying its own scale so the UI can render it correctly."""
    metric: str
    score: Optional[float] = None
    label: Optional[bool] = None
    reason: Optional[str] = None
    threshold: Optional[float] = None
    passed: Optional[bool] = None
    scale: str = Field(
        default="1-5",
        description="'1-5' (higher is better), '0-7' (lower is better) or 'boolean'",
    )
    higher_is_better: bool = True



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
    include_safety_metrics: bool = Field(
        default=True,
        description="Run Azure AI Content Safety backed risk evaluators alongside quality metrics",
    )
    evaluation_model: str = Field(default=DEFAULT_EVALUATION_MODEL)


class EvaluationResult(BaseModel):
    """Result of an evaluation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evaluation_id: str = Field(description="Links to request")
    execution_id: str = Field(description="Agent execution being evaluated")
    claim_id: str = Field(description="Claim ID")
    agent_type: str = Field(description="Agent type evaluated")
    evaluator_type: EvaluatorType
    
    # Scores (1-5 scale for Azure AI Foundry quality evaluators)
    groundedness_score: Optional[float] = None
    relevance_score: Optional[float] = None
    coherence_score: Optional[float] = None
    fluency_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    overall_score: Optional[float] = None

    # Risk & safety results (0-7 severity, LOWER is better)
    violence_score: Optional[float] = None
    sexual_score: Optional[float] = None
    self_harm_score: Optional[float] = None
    hate_unfairness_score: Optional[float] = None
    #: Highest observed content-harm severity across the safety evaluators
    max_safety_severity: Optional[float] = None
    #: True when every safety evaluator returned a result at or below its threshold
    safety_passed: Optional[bool] = None
    indirect_attack_detected: Optional[bool] = None
    protected_material_detected: Optional[bool] = None

    # Per-metric detail, including scale so clients render direction correctly
    metric_scores: List[MetricScore] = Field(default_factory=list)

    # Outcome / provenance
    status: EvaluationStatus = EvaluationStatus.COMPLETED
    #: Deep link to the run in the Microsoft Foundry portal Evaluations pane
    studio_url: Optional[str] = None
    #: Name of the evaluation run as it appears in the portal
    evaluation_run_name: Optional[str] = None
    #: True when results were successfully uploaded to the Foundry project
    uploaded_to_portal: bool = False
    
    # Details
    reasoning: Optional[str] = None
    feedback: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)
    detailed_scores: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    evaluation_model: str = Field(default=DEFAULT_EVALUATION_MODEL)
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


# ---------------------------------------------------------------------------
# AI Red Teaming Agent
# ---------------------------------------------------------------------------


class RedTeamRiskCategory(str, Enum):
    """Risk categories supported by the AI Red Teaming Agent."""
    VIOLENCE = "Violence"
    HATE_UNFAIRNESS = "HateUnfairness"
    SEXUAL = "Sexual"
    SELF_HARM = "SelfHarm"


class RedTeamComplexity(str, Enum):
    """Grouped attack-strategy complexity levels."""
    BASELINE = "baseline"
    EASY = "EASY"
    MODERATE = "MODERATE"
    DIFFICULT = "DIFFICULT"


class RedTeamScanStatus(str, Enum):
    """Lifecycle of a red team scan."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RedTeamScanRequest(BaseModel):
    """Request to run an AI Red Teaming Agent scan against the claims workflow."""
    scan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scan_name: Optional[str] = None
    risk_categories: List[RedTeamRiskCategory] = Field(
        default_factory=lambda: [
            RedTeamRiskCategory.VIOLENCE,
            RedTeamRiskCategory.HATE_UNFAIRNESS,
            RedTeamRiskCategory.SEXUAL,
            RedTeamRiskCategory.SELF_HARM,
        ]
    )
    #: Attack objectives per risk category. Kept small by default because each
    #: objective is a full call against the target application.
    num_objectives: int = Field(default=1, ge=1, le=20)
    complexity: List[RedTeamComplexity] = Field(
        default_factory=lambda: [RedTeamComplexity.BASELINE]
    )
    #: Which target to attack: the supervisor workflow, or the base model directly.
    target: str = Field(default="workflow", pattern="^(workflow|model)$")


class RedTeamRiskResult(BaseModel):
    """Attack success rate for a single risk category or attack strategy."""
    name: str
    attack_success_rate: Optional[float] = None
    successful_attacks: Optional[int] = None
    total_attacks: Optional[int] = None


class RedTeamScanResult(BaseModel):
    """Result of an AI Red Teaming Agent scan."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scan_id: str
    scan_name: Optional[str] = None
    status: RedTeamScanStatus = RedTeamScanStatus.PENDING

    #: Overall attack success rate as a percentage (0-100). LOWER is better.
    overall_attack_success_rate: Optional[float] = None
    total_attacks: Optional[int] = None
    successful_attacks: Optional[int] = None

    by_risk_category: List[RedTeamRiskResult] = Field(default_factory=list)
    by_attack_strategy: List[RedTeamRiskResult] = Field(default_factory=list)

    risk_categories: List[str] = Field(default_factory=list)
    num_objectives: int = 0
    target: str = "workflow"

    studio_url: Optional[str] = None
    scorecard: Optional[Dict[str, Any]] = None

    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
