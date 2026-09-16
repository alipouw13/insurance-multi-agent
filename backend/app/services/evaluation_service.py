"""Evaluation service using Azure AI Foundry SDK."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import uuid

from app.core.config import get_settings
from app.models.evaluation import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationSummary,
    EvaluationStatus,
    EvaluatorType,
    EvaluationMetric,
    MetricScore,
    QUALITY_METRICS,
    SAFETY_SEVERITY_METRICS,
    SAFETY_LABEL_METRICS,
    DEFAULT_EVALUATION_MODEL,
)
from app.services.cosmos_service import get_cosmos_service

logger = logging.getLogger(__name__)
settings = get_settings()


def get_azure_ai_project() -> Optional[Any]:
    """Build the ``azure_ai_project`` argument for the evaluation SDK.

    The SDK accepts either a Foundry project endpoint URL or, for hub-based
    ("classic") projects, a dict of subscription / resource group / project name.
    Returns ``None`` when the project is not configured, in which case
    evaluations still run locally but are not uploaded to the portal.
    """
    if settings.azure_ai_project_endpoint:
        return settings.azure_ai_project_endpoint

    if (
        settings.azure_subscription_id
        and settings.azure_resource_group
        and settings.azure_ai_project_name
    ):
        return {
            "subscription_id": settings.azure_subscription_id,
            "resource_group_name": settings.azure_resource_group,
            "project_name": settings.azure_ai_project_name,
        }

    return None


class FoundryEvaluator:
    """Azure AI Foundry evaluator using the official azure-ai-evaluation SDK."""

    def __init__(self):
        self.available_evaluators: Dict[str, Any] = {}
        self.safety_evaluators: Dict[str, Any] = {}
        self.azure_ai_project = get_azure_ai_project()
        self._initialize_evaluators()

    def _build_model_config(self):
        """Build the judge-model configuration for AI-assisted evaluators."""
        from azure.ai.evaluation import AzureOpenAIModelConfiguration

        model_config_kwargs: Dict[str, Any] = {
            "azure_endpoint": settings.azure_openai_endpoint,
            "azure_deployment": settings.azure_openai_deployment_name or DEFAULT_EVALUATION_MODEL,
            "api_version": settings.azure_openai_api_version,
        }
        # Omitting the key makes the SDK fall back to Entra ID, which is required
        # when key-based auth is disabled on the Azure OpenAI resource.
        if settings.azure_openai_api_key:
            model_config_kwargs["api_key"] = settings.azure_openai_api_key

        return AzureOpenAIModelConfiguration(**model_config_kwargs)

    def _initialize_evaluators(self):
        """Initialize quality and (where available) risk & safety evaluators."""
        try:
            logger.info("Initializing Azure AI Foundry evaluators...")

            from azure.ai.evaluation import (
                GroundednessEvaluator,
                RelevanceEvaluator,
                CoherenceEvaluator,
                FluencyEvaluator,
            )

            model_config = self._build_model_config()

            # Quality evaluators. Each is scored 1-5 where higher is better.
            # Note the differing required inputs: FluencyEvaluator takes only
            # `response`, RelevanceEvaluator takes `query` + `response`, and
            # GroundednessEvaluator additionally requires `context`.
            self.available_evaluators = {
                "groundedness": GroundednessEvaluator(model_config),
                "relevance": RelevanceEvaluator(model_config),
                "coherence": CoherenceEvaluator(model_config),
                "fluency": FluencyEvaluator(model_config),
            }

            logger.info(
                "Initialized %d quality evaluators: %s",
                len(self.available_evaluators),
                ", ".join(self.available_evaluators),
            )

        except ImportError as e:
            logger.error(f"Azure AI Evaluation SDK not available: {e}")
            logger.info("Install with: pip install azure-ai-evaluation")
            self.available_evaluators = {}
            return
        except Exception as e:
            logger.error(f"Failed to initialize Azure AI Foundry evaluators: {e}", exc_info=True)
            self.available_evaluators = {}
            return

        self._initialize_safety_evaluators()

    def _initialize_safety_evaluators(self):
        """Initialize Azure AI Content Safety backed risk evaluators.

        These are service-backed rather than model-backed: they take a credential
        and the Foundry project instead of a ``model_config``, and are only
        available in a subset of regions. Failure here is non-fatal.
        """
        if not self.azure_ai_project:
            logger.info(
                "Foundry project not configured - risk & safety evaluators disabled")
            return

        try:
            from azure.identity import DefaultAzureCredential
            from azure.ai.evaluation import (
                ContentSafetyEvaluator,
                IndirectAttackEvaluator,
                ProtectedMaterialEvaluator,
            )

            credential = DefaultAzureCredential()

            # ContentSafetyEvaluator is a composite that returns violence, sexual,
            # self_harm and hate_unfairness, each 0-7 severity where LOWER is better.
            self.safety_evaluators = {
                "content_safety": ContentSafetyEvaluator(
                    credential=credential, azure_ai_project=self.azure_ai_project
                ),
                "indirect_attack": IndirectAttackEvaluator(
                    credential=credential, azure_ai_project=self.azure_ai_project
                ),
                "protected_material": ProtectedMaterialEvaluator(
                    credential=credential, azure_ai_project=self.azure_ai_project
                ),
            }

            logger.info(
                "Initialized %d risk & safety evaluators: %s",
                len(self.safety_evaluators),
                ", ".join(self.safety_evaluators),
            )

        except ImportError as e:
            logger.warning(f"Risk & safety evaluators unavailable: {e}")
            self.safety_evaluators = {}
        except Exception as e:
            # Most commonly an unsupported region or missing RBAC.
            logger.warning(
                f"Could not initialize risk & safety evaluators (region/permissions?): {e}")
            self.safety_evaluators = {}

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        try:
            if value is None or isinstance(value, bool):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_bool(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in ("true", "yes"):
                return True
            if value.lower() in ("false", "no"):
                return False
        return None

    @staticmethod
    def _flatten_outputs(eval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten a single-row ``evaluate()`` result into ``{key: value}``.

        The SDK returns ``{"metrics": {...}, "rows": [...], "studio_url": ...}``.
        Row keys are prefixed with ``outputs.`` (for example
        ``outputs.groundedness.groundedness``), while the aggregated ``metrics``
        dict uses the bare evaluator/metric name. Both are merged here, with
        row-level values taking precedence because they are per-record.
        """
        flat: Dict[str, Any] = {}

        metrics = eval_result.get("metrics")
        if isinstance(metrics, dict):
            for key, value in metrics.items():
                flat[key] = value

        rows = eval_result.get("rows")
        if isinstance(rows, list) and rows:
            row = rows[0]
            if isinstance(row, dict):
                for key, value in row.items():
                    if key.startswith("outputs."):
                        flat[key[len("outputs."):]] = value
                    else:
                        flat.setdefault(key, value)

        return flat

    @staticmethod
    def _lookup(flat: Dict[str, Any], *candidates: str) -> Any:
        for key in candidates:
            if key in flat and flat[key] is not None:
                return flat[key]
        return None

    def _extract_quality_metric(
        self, flat: Dict[str, Any], metric: str
    ) -> Optional[MetricScore]:
        """Pull a 1-5 quality metric out of the flattened results."""
        score = self._coerce_float(
            self._lookup(
                flat,
                f"{metric}.{metric}",          # groundedness.groundedness
                metric,                         # groundedness
                f"{metric}.gpt_{metric}",      # legacy gpt_* naming
                f"gpt_{metric}",
            )
        )
        if score is None:
            return None

        reason = self._lookup(flat, f"{metric}.{metric}_reason", f"{metric}_reason")
        threshold = self._coerce_float(
            self._lookup(flat, f"{metric}.{metric}_threshold", f"{metric}_threshold")
        )
        outcome = self._lookup(flat, f"{metric}.{metric}_result", f"{metric}_result")

        passed: Optional[bool] = None
        if isinstance(outcome, str):
            passed = outcome.lower() == "pass"
        elif threshold is not None:
            passed = score >= threshold

        return MetricScore(
            metric=metric,
            score=score,
            reason=reason if isinstance(reason, str) else None,
            threshold=threshold,
            passed=passed,
            scale="1-5",
            higher_is_better=True,
        )

    def _extract_severity_metric(
        self, flat: Dict[str, Any], metric: str
    ) -> Optional[MetricScore]:
        """Pull a 0-7 content-harm severity metric (lower is better)."""
        score = self._coerce_float(
            self._lookup(flat, f"content_safety.{metric}_score", f"{metric}_score")
        )
        if score is None:
            return None

        reason = self._lookup(
            flat, f"content_safety.{metric}_reason", f"{metric}_reason")
        threshold = self._coerce_float(
            self._lookup(flat, f"content_safety.{metric}_threshold", f"{metric}_threshold")
        )
        outcome = self._lookup(
            flat, f"content_safety.{metric}_result", f"{metric}_result")

        passed: Optional[bool] = None
        if isinstance(outcome, str):
            passed = outcome.lower() == "pass"
        elif threshold is not None:
            passed = score <= threshold

        return MetricScore(
            metric=metric,
            score=score,
            reason=reason if isinstance(reason, str) else None,
            threshold=threshold,
            passed=passed,
            scale="0-7",
            higher_is_better=False,
        )

    def _extract_label_metric(
        self, flat: Dict[str, Any], metric: str, *label_keys: str
    ) -> Optional[MetricScore]:
        """Pull a boolean safety label such as XPIA or protected material."""
        raw = self._lookup(flat, *label_keys)
        label = self._coerce_bool(raw)

        if label is None:
            # Batch runs aggregate boolean labels into a defect rate instead.
            rate = self._coerce_float(
                self._lookup(flat, f"{metric}.{metric}_defect_rate", f"{metric}_defect_rate")
            )
            if rate is None:
                return None
            label = rate > 0

        reason = self._lookup(flat, f"{metric}.{metric}_reason", f"{metric}_reason")

        return MetricScore(
            metric=metric,
            label=label,
            reason=reason if isinstance(reason, str) else None,
            # For a detection label, "not detected" is the passing outcome.
            passed=(label is False),
            scale="boolean",
            higher_is_better=False,
        )

    def _parse_results(
        self, eval_result: Any, request: EvaluationRequest, result: EvaluationResult
    ) -> List[str]:
        """Populate ``result`` from the SDK output. Returns names of missing metrics."""
        if not isinstance(eval_result, dict):
            raise TypeError(
                f"Unexpected evaluate() result type: {type(eval_result).__name__}")

        flat = self._flatten_outputs(eval_result)
        logger.debug("Flattened evaluation keys: %s", sorted(flat))

        metric_scores: List[MetricScore] = []
        missing: List[str] = []

        # --- Quality metrics (1-5, higher is better) ---
        for metric in request.metrics:
            name = metric.value
            if metric not in QUALITY_METRICS:
                continue
            parsed = self._extract_quality_metric(flat, name)
            if parsed is None:
                missing.append(name)
                continue
            metric_scores.append(parsed)
            setattr(result, f"{name}_score", parsed.score)

        # --- Risk & safety severities (0-7, lower is better) ---
        for metric in SAFETY_SEVERITY_METRICS:
            parsed = self._extract_severity_metric(flat, metric.value)
            if parsed is None:
                continue
            metric_scores.append(parsed)
            setattr(result, f"{metric.value}_score", parsed.score)

        # --- Boolean safety labels ---
        xpia = self._extract_label_metric(
            flat,
            "indirect_attack",
            "indirect_attack.xpia_label",
            "xpia_label",
            "indirect_attack_label",
        )
        if xpia is not None:
            metric_scores.append(xpia)
            result.indirect_attack_detected = xpia.label

        protected = self._extract_label_metric(
            flat,
            "protected_material",
            "protected_material.protected_material_label",
            "protected_material_label",
        )
        if protected is not None:
            metric_scores.append(protected)
            result.protected_material_detected = protected.label

        result.metric_scores = metric_scores
        result.detailed_scores = {
            m.metric: m.model_dump(mode="json") for m in metric_scores
        }

        # Overall score averages the quality metrics only. Mixing a 0-7
        # "lower is better" severity into a 1-5 "higher is better" mean would
        # be meaningless.
        quality_scores = [
            m.score for m in metric_scores
            if m.scale == "1-5" and m.score is not None
        ]
        result.overall_score = (
            sum(quality_scores) / len(quality_scores) if quality_scores else None
        )

        severities = [
            m.score for m in metric_scores
            if m.scale == "0-7" and m.score is not None
        ]
        if severities:
            result.max_safety_severity = max(severities)

        safety_outcomes = [
            m.passed for m in metric_scores
            if m.scale in ("0-7", "boolean") and m.passed is not None
        ]
        if safety_outcomes:
            result.safety_passed = all(safety_outcomes)

        return missing

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def _build_evaluator_set(self, request: EvaluationRequest) -> Dict[str, Any]:
        """Select the evaluators to run for this request."""
        requested = {m.value for m in request.metrics}
        evaluators = {
            name: ev for name, ev in self.available_evaluators.items()
            if name in requested
        } or dict(self.available_evaluators)

        if request.include_safety_metrics:
            evaluators.update(self.safety_evaluators)

        return evaluators

    def _run_evaluate(
        self, temp_file: str, evaluators: Dict[str, Any], run_name: str
    ) -> Tuple[Any, bool]:
        """Run the SDK evaluate() call, uploading to the portal when possible.

        Returns ``(result, uploaded)``. If the upload fails (most often missing
        RBAC on the project's storage account, or a storage account with public
        network access disabled) the evaluation is retried locally so the caller
        still gets real scores instead of losing the run entirely.
        """
        from azure.ai.evaluation import evaluate

        # Groundedness needs the context column; the others ignore extra columns.
        evaluator_config = {
            "default": {
                "column_mapping": {
                    "query": "${data.query}",
                    "response": "${data.response}",
                    "context": "${data.context}",
                }
            }
        }

        if self.azure_ai_project:
            try:
                logger.info(
                    "Running evaluation '%s' with portal upload enabled", run_name)
                result = evaluate(
                    data=temp_file,
                    evaluators=evaluators,
                    evaluator_config=evaluator_config,
                    evaluation_name=run_name,
                    azure_ai_project=self.azure_ai_project,
                )
                return result, True
            except Exception as upload_err:
                logger.warning(
                    "Evaluation upload to the Foundry portal failed (%s). "
                    "Retrying locally without upload.", upload_err
                )

        logger.info("Running evaluation '%s' locally (no portal upload)", run_name)
        result = evaluate(
            data=temp_file,
            evaluators=evaluators,
            evaluator_config=evaluator_config,
            evaluation_name=run_name,
        )
        return result, False

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Evaluate an agent response with Azure AI Foundry evaluators."""
        if not self.available_evaluators:
            raise ValueError("Azure AI Foundry evaluators not available")

        logger.info(
            f"Starting Azure AI Foundry evaluation for execution_id: {request.execution_id}")

        result = EvaluationResult(
            evaluation_id=request.evaluation_id,
            execution_id=request.execution_id,
            claim_id=request.claim_id,
            agent_type=request.agent_type,
            evaluator_type=EvaluatorType.FOUNDRY,
            question=request.question,
            answer=request.answer,
            context=request.context,
            ground_truth=request.ground_truth,
            evaluation_model=request.evaluation_model,
        )

        import asyncio
        import json
        import os
        import tempfile

        evaluators = self._build_evaluator_set(request)
        run_name = (
            f"claim_{request.claim_id}_{request.agent_type}_{request.evaluation_id[:8]}"
        )
        result.evaluation_run_name = run_name

        eval_data = {
            "query": request.question,
            "response": request.answer,
            "context": "\n".join(request.context) if request.context else "",
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps(eval_data) + "\n")
            temp_file = f.name

        try:
            # evaluate() is blocking and spawns a batch runner, so keep it off
            # the event loop.
            eval_result, uploaded = await asyncio.to_thread(
                self._run_evaluate, temp_file, evaluators, run_name
            )

            result.uploaded_to_portal = uploaded
            if isinstance(eval_result, dict):
                studio_url = eval_result.get("studio_url")
                if isinstance(studio_url, str) and studio_url:
                    result.studio_url = studio_url
                    logger.info("Evaluation available in Foundry portal: %s", studio_url)

            missing = self._parse_results(eval_result, request, result)

            if result.overall_score is None:
                # No quality metric could be parsed - report the failure rather
                # than inventing a score.
                result.status = EvaluationStatus.FAILED
                result.error_message = (
                    "Evaluation ran but no quality metric could be parsed from the "
                    f"result. Missing: {', '.join(missing) or 'all'}."
                )
                logger.error(
                    "Failed to parse any evaluation metric. Result keys: %s",
                    sorted(eval_result) if isinstance(eval_result, dict) else type(eval_result),
                )
            elif missing:
                result.status = EvaluationStatus.PARTIAL
                result.error_message = f"Missing metrics: {', '.join(missing)}"
                logger.warning("Evaluation partially parsed. Missing: %s", missing)
            else:
                result.status = EvaluationStatus.COMPLETED

            if result.overall_score is not None:
                result.reasoning = (
                    f"Azure AI Foundry evaluation across "
                    f"{len(result.metric_scores)} metric(s)."
                )
                quality = (
                    "poor" if result.overall_score < 2
                    else "fair" if result.overall_score < 3
                    else "good" if result.overall_score < 4
                    else "excellent"
                )
                logger.info(
                    "Overall quality score: %.2f/5.0 (%s)", result.overall_score, quality)
                if result.max_safety_severity is not None:
                    logger.info(
                        "Max content-harm severity: %.1f/7 (lower is better), safety_passed=%s",
                        result.max_safety_severity, result.safety_passed,
                    )

        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            result.status = EvaluationStatus.FAILED
            result.error_message = str(e)
            result.overall_score = None
        finally:
            try:
                os.unlink(temp_file)
            except OSError as cleanup_err:
                logger.warning(f"Could not delete temp file {temp_file}: {cleanup_err}")

        return result


class EvaluationService:
    """Service for managing agent evaluations."""
    
    def __init__(self):
        self.foundry_evaluator = None
        self._initialized = False
        self.cosmos_service = None
    
    def _ensure_initialized(self):
        """Lazy initialization (sync parts only)."""
        if not self._initialized:
            self._initialized = True
            try:
                self.foundry_evaluator = FoundryEvaluator()
                logger.info("Evaluation service initialized (sync)")
            except Exception as e:
                logger.error(f"Failed to initialize evaluation service: {e}")
    
    async def _ensure_cosmos_initialized(self):
        """Ensure cosmos service is initialized."""
        if self.cosmos_service is None:
            try:
                self.cosmos_service = await get_cosmos_service()
                logger.debug("Cosmos service initialized for evaluations")
            except Exception as e:
                logger.warning(f"Failed to initialize cosmos service: {e}")
    
    def is_available(self) -> bool:
        """Check if evaluation service is available."""
        self._ensure_initialized()
        return self.foundry_evaluator is not None and bool(self.foundry_evaluator.available_evaluators)
    
    async def evaluate_execution(self, request: EvaluationRequest) -> EvaluationResult:
        """Evaluate an agent execution."""
        self._ensure_initialized()
        await self._ensure_cosmos_initialized()
        
        if not self.is_available():
            raise ValueError("Evaluation service not available")
        
        logger.info(f"Starting evaluation for execution: {request.execution_id}, agent: {request.agent_type}")
        
        start_time = time.time()
        
        # Run evaluation
        result = await self.foundry_evaluator.evaluate(request)
        
        # Set timing
        result.evaluation_duration_ms = int((time.time() - start_time) * 1000)
        result.evaluation_timestamp = datetime.utcnow()
        
        # Store in Cosmos DB
        await self._store_result(result)
        
        logger.info(f"Evaluation completed in {result.evaluation_duration_ms}ms")
        
        return result
    
    async def _store_result(self, result: EvaluationResult) -> bool:
        """Store evaluation result in Cosmos DB."""
        try:
            if not self.cosmos_service:
                logger.warning("Cosmos service not available, skipping storage")
                return False
            
            result_dict = result.model_dump(mode='json')
            
            # Store in evaluations container
            await self.cosmos_service.store_evaluation_result(result_dict)
            
            logger.info(f"Stored evaluation result: {result.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store evaluation result: {e}")
            return False
    
    async def get_evaluation_result(self, evaluation_id: str) -> Optional[EvaluationResult]:
        """Retrieve evaluation result by ID."""
        try:
            await self._ensure_cosmos_initialized()
            if not self.cosmos_service:
                return None
            
            result_dict = await self.cosmos_service.get_evaluation_result(evaluation_id)
            if not result_dict:
                return None
            
            return EvaluationResult(**result_dict)
            
        except Exception as e:
            logger.error(f"Failed to retrieve evaluation result: {e}")
            return None
    
    async def get_evaluations_for_execution(self, execution_id: str) -> List[EvaluationResult]:
        """Get all evaluations for an execution."""
        try:
            await self._ensure_cosmos_initialized()
            if not self.cosmos_service:
                return []
            
            results = await self.cosmos_service.get_evaluations_by_execution(execution_id)
            return [EvaluationResult(**r) for r in results]
            
        except Exception as e:
            logger.error(f"Failed to get evaluations for execution: {e}")
            return []
    
    async def get_evaluations_for_claim(self, claim_id: str) -> List[EvaluationResult]:
        """Get all evaluations for a claim."""
        try:
            await self._ensure_cosmos_initialized()
            if not self.cosmos_service:
                return []
            
            results = await self.cosmos_service.get_evaluations_by_claim(claim_id)
            return [EvaluationResult(**r) for r in results]
            
        except Exception as e:
            logger.error(f"Failed to get evaluations for claim: {e}")
            return []
    
    async def get_evaluation_summary(self, execution_id: Optional[str] = None, claim_id: Optional[str] = None) -> EvaluationSummary:
        """Get evaluation summary."""
        try:
            if execution_id:
                results = await self.get_evaluations_for_execution(execution_id)
            elif claim_id:
                results = await self.get_evaluations_for_claim(claim_id)
            else:
                return EvaluationSummary()
            
            if not results:
                return EvaluationSummary(execution_id=execution_id, claim_id=claim_id)
            
            summary = EvaluationSummary(
                execution_id=execution_id,
                claim_id=claim_id,
                total_evaluations=len(results),
                evaluator_type=results[0].evaluator_type if results else EvaluatorType.FOUNDRY
            )
            
            # Calculate averages
            groundedness_scores = [r.groundedness_score for r in results if r.groundedness_score is not None]
            relevance_scores = [r.relevance_score for r in results if r.relevance_score is not None]
            coherence_scores = [r.coherence_score for r in results if r.coherence_score is not None]
            fluency_scores = [r.fluency_score for r in results if r.fluency_score is not None]
            overall_scores = [r.overall_score for r in results if r.overall_score is not None]
            
            summary.avg_groundedness = sum(groundedness_scores) / len(groundedness_scores) if groundedness_scores else None
            summary.avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else None
            summary.avg_coherence = sum(coherence_scores) / len(coherence_scores) if coherence_scores else None
            summary.avg_fluency = sum(fluency_scores) / len(fluency_scores) if fluency_scores else None
            summary.avg_overall = sum(overall_scores) / len(overall_scores) if overall_scores else None
            
            summary.start_time = min(r.evaluation_timestamp for r in results)
            summary.end_time = max(r.evaluation_timestamp for r in results)
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get evaluation summary: {e}")
            return EvaluationSummary()


# Global instance
_evaluation_service: Optional[EvaluationService] = None


def get_evaluation_service() -> EvaluationService:
    """Get the global evaluation service instance."""
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = EvaluationService()
    return _evaluation_service
