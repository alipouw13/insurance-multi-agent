"""AI Red Teaming Agent service.

Wraps the Azure AI Evaluation SDK's ``RedTeam`` agent so the insurance claims
workflow can be scanned for safety risks with adversarial prompts.

The red team agent is an *offline* safety tool: a scan issues many adversarial
requests against the target and therefore takes minutes, not seconds. Scans are
run as background jobs and their results are persisted, rather than being run in
the request path.

Requires the ``redteam`` extra::

    pip install "azure-ai-evaluation[redteam]"

which pulls in PyRIT and needs Python 3.10+.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.models.evaluation import (
    RedTeamComplexity,
    RedTeamRiskResult,
    RedTeamScanRequest,
    RedTeamScanResult,
    RedTeamScanStatus,
)
from app.services.cosmos_service import get_cosmos_service
from app.services.evaluation_service import get_azure_ai_project

logger = logging.getLogger(__name__)
settings = get_settings()


def red_team_available() -> bool:
    """Whether the optional red teaming dependencies are importable."""
    try:
        import azure.ai.evaluation.red_team  # noqa: F401
        return True
    except Exception:
        return False


class RedTeamService:
    """Runs AI Red Teaming Agent scans against the claims application."""

    def __init__(self) -> None:
        self.azure_ai_project = get_azure_ai_project()
        self._scans: Dict[str, RedTeamScanResult] = {}
        self._running: Optional[str] = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return bool(self.azure_ai_project) and red_team_available()

    def availability_detail(self) -> Dict[str, Any]:
        return {
            "available": self.is_available(),
            "sdk_installed": red_team_available(),
            "project_configured": bool(self.azure_ai_project),
            "reason": (
                None if self.is_available()
                else "azure-ai-evaluation[redteam] not installed"
                if not red_team_available()
                else "Foundry project not configured"
            ),
        }

    # ------------------------------------------------------------------
    # Targets
    # ------------------------------------------------------------------

    @staticmethod
    def _workflow_target():
        """Build a callback that sends each adversarial prompt to the supervisor.

        The red team agent passes a single string prompt and expects a string
        response, which maps onto the supervisor's claim-processing entry point.
        """
        def target(query: str) -> str:
            try:
                from app.services.claim_processing import run as run_workflow

                claim = {
                    "claim_id": "REDTEAM-PROBE",
                    "claimant_name": "Red Team Probe",
                    "claim_type": "Auto Accident",
                    "description": query,
                    "estimated_damage": 1000,
                }
                result = run_workflow(claim)

                messages = result.get("messages") if isinstance(result, dict) else None
                if messages:
                    last = messages[-1]
                    content = getattr(last, "content", None)
                    if content is None and isinstance(last, dict):
                        content = last.get("content")
                    if content:
                        return str(content)
                return json.dumps(result, default=str)[:4000]
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Red team target callback failed: %s", exc)
                # Returning a refusal keeps the scan running; a hard exception
                # would abort the whole scan.
                return (
                    "I'm unable to process that request. I only handle "
                    "legitimate insurance claim assessments."
                )

        return target

    def _model_target(self) -> Dict[str, Any]:
        """Scan the base Azure OpenAI deployment directly."""
        config: Dict[str, Any] = {
            "azure_endpoint": settings.azure_openai_endpoint,
            "azure_deployment": settings.azure_openai_deployment_name,
        }
        if settings.azure_openai_api_key:
            config["api_key"] = settings.azure_openai_api_key
        return config

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    @staticmethod
    def _build_attack_strategies(complexity: List[RedTeamComplexity]) -> List[Any]:
        """Map the requested complexity groups onto SDK attack strategies.

        ``BASELINE`` means "send the direct adversarial queries only", which the
        SDK expresses as passing no attack strategies at all.
        """
        from azure.ai.evaluation.red_team import AttackStrategy

        mapping = {
            RedTeamComplexity.EASY: AttackStrategy.EASY,
            RedTeamComplexity.MODERATE: AttackStrategy.MODERATE,
            RedTeamComplexity.DIFFICULT: AttackStrategy.DIFFICULT,
        }
        return [mapping[c] for c in complexity if c in mapping]

    @staticmethod
    def _parse_scorecard(scorecard: Any) -> Dict[str, Any]:
        """Normalize the SDK scorecard into plain JSON."""
        if scorecard is None:
            return {}
        if isinstance(scorecard, dict):
            return scorecard
        for attr in ("to_dict", "as_dict"):
            fn = getattr(scorecard, attr, None)
            if callable(fn):
                try:
                    return fn()
                except Exception:
                    pass
        try:
            return json.loads(json.dumps(scorecard, default=str))
        except Exception:
            return {}

    @classmethod
    def _extract_rates(cls, scorecard: Dict[str, Any]) -> Dict[str, Any]:
        """Pull overall and per-category attack success rates from a scorecard.

        The scorecard layout has changed across SDK versions, so several shapes
        are tolerated and anything unrecognised is simply reported as absent.
        """
        overall: Optional[float] = None
        by_category: List[RedTeamRiskResult] = []
        by_strategy: List[RedTeamRiskResult] = []

        joint = scorecard.get("scorecard") if isinstance(scorecard, dict) else None
        root = joint if isinstance(joint, dict) else scorecard

        if isinstance(root, dict):
            # Overall ASR may be reported under a few different names.
            for key in ("overall_asr", "attack_success_rate", "overall_attack_success_rate"):
                value = root.get(key)
                if isinstance(value, (int, float)):
                    overall = float(value)
                    break

            risk_summary = root.get("joint_risk_attack_summary") or root.get(
                "risk_category_summary")
            if isinstance(risk_summary, list):
                for entry in risk_summary:
                    if not isinstance(entry, dict):
                        continue
                    name = entry.get("risk_category") or entry.get("category")
                    if not name:
                        continue
                    asr = None
                    for key in ("overall_asr", "asr", "attack_success_rate"):
                        if isinstance(entry.get(key), (int, float)):
                            asr = float(entry[key])
                            break
                    by_category.append(
                        RedTeamRiskResult(name=str(name), attack_success_rate=asr))

            strategy_summary = root.get("attack_technique_summary") or root.get(
                "attack_strategy_summary")
            if isinstance(strategy_summary, list):
                for entry in strategy_summary:
                    if not isinstance(entry, dict):
                        continue
                    name = entry.get("attack_technique") or entry.get("strategy")
                    if not name:
                        continue
                    asr = None
                    for key in ("overall_asr", "asr", "attack_success_rate"):
                        if isinstance(entry.get(key), (int, float)):
                            asr = float(entry[key])
                            break
                    by_strategy.append(
                        RedTeamRiskResult(name=str(name), attack_success_rate=asr))

        return {
            "overall": overall,
            "by_category": by_category,
            "by_strategy": by_strategy,
        }

    async def run_scan(self, request: RedTeamScanRequest) -> RedTeamScanResult:
        """Run a red team scan. Long-running; intended for background execution."""
        result = RedTeamScanResult(
            scan_id=request.scan_id,
            scan_name=request.scan_name or f"claims-redteam-{request.scan_id[:8]}",
            status=RedTeamScanStatus.RUNNING,
            risk_categories=[c.value for c in request.risk_categories],
            num_objectives=request.num_objectives,
            target=request.target,
        )
        self._scans[request.scan_id] = result
        self._running = request.scan_id
        started = time.time()

        if not self.is_available():
            detail = self.availability_detail()
            result.status = RedTeamScanStatus.FAILED
            result.error_message = detail["reason"] or "Red teaming not available"
            result.completed_at = datetime.utcnow()
            self._running = None
            await self._store(result)
            return result

        output_path = None
        try:
            from azure.identity import DefaultAzureCredential
            from azure.ai.evaluation.red_team import RedTeam, RiskCategory

            risk_categories = [
                getattr(RiskCategory, c.value) for c in request.risk_categories
            ]

            red_team = RedTeam(
                azure_ai_project=self.azure_ai_project,
                credential=DefaultAzureCredential(),
                risk_categories=risk_categories,
                num_objectives=request.num_objectives,
            )

            target = (
                self._model_target() if request.target == "model"
                else self._workflow_target()
            )

            scan_kwargs: Dict[str, Any] = {
                "target": target,
                "scan_name": result.scan_name,
            }

            strategies = self._build_attack_strategies(request.complexity)
            if strategies:
                scan_kwargs["attack_strategies"] = strategies

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f:
                output_path = f.name
            scan_kwargs["output_path"] = output_path

            logger.info(
                "Starting red team scan '%s' (%d categories x %d objectives, target=%s)",
                result.scan_name, len(risk_categories),
                request.num_objectives, request.target,
            )

            scan_result = await red_team.scan(**scan_kwargs)

            scorecard = self._parse_scorecard(
                getattr(scan_result, "scan_result", None) or scan_result)

            # Prefer the JSON scorecard written to disk when present.
            if output_path and os.path.exists(output_path):
                try:
                    with open(output_path, "r", encoding="utf-8") as fh:
                        content = fh.read().strip()
                    if content:
                        scorecard = json.loads(content)
                except Exception as read_err:
                    logger.warning("Could not read red team scorecard: %s", read_err)

            result.scorecard = scorecard
            rates = self._extract_rates(scorecard)
            result.overall_attack_success_rate = rates["overall"]
            result.by_risk_category = rates["by_category"]
            result.by_attack_strategy = rates["by_strategy"]

            studio_url = getattr(scan_result, "studio_url", None)
            if not studio_url and isinstance(scorecard, dict):
                studio_url = scorecard.get("studio_url")
            if isinstance(studio_url, str):
                result.studio_url = studio_url

            result.status = RedTeamScanStatus.COMPLETED
            logger.info(
                "Red team scan '%s' complete. Overall ASR: %s",
                result.scan_name, result.overall_attack_success_rate,
            )

        except Exception as exc:
            logger.error("Red team scan failed: %s", exc, exc_info=True)
            result.status = RedTeamScanStatus.FAILED
            result.error_message = str(exc)
        finally:
            result.completed_at = datetime.utcnow()
            result.duration_ms = int((time.time() - started) * 1000)
            self._running = None
            if output_path:
                try:
                    os.unlink(output_path)
                except OSError:
                    pass

        await self._store(result)
        return result

    def start_scan(self, request: RedTeamScanRequest) -> RedTeamScanResult:
        """Kick off a scan in the background and return its pending record."""
        if self._running:
            raise ValueError(
                f"A red team scan is already running (scan_id={self._running})")

        pending = RedTeamScanResult(
            scan_id=request.scan_id,
            scan_name=request.scan_name or f"claims-redteam-{request.scan_id[:8]}",
            status=RedTeamScanStatus.PENDING,
            risk_categories=[c.value for c in request.risk_categories],
            num_objectives=request.num_objectives,
            target=request.target,
        )
        self._scans[request.scan_id] = pending

        asyncio.create_task(self.run_scan(request))
        return pending

    # ------------------------------------------------------------------
    # Persistence / retrieval
    # ------------------------------------------------------------------

    async def _store(self, result: RedTeamScanResult) -> None:
        try:
            cosmos = await get_cosmos_service()
            if not cosmos:
                return
            payload = result.model_dump(mode="json")
            # Reuse the evaluations container; red team scans are evaluations.
            payload["record_type"] = "red_team_scan"
            payload["id"] = result.id
            payload["evaluation_id"] = result.scan_id
            await cosmos.store_evaluation_result(payload)
        except Exception as exc:
            logger.warning("Could not persist red team scan result: %s", exc)

    def get_scan(self, scan_id: str) -> Optional[RedTeamScanResult]:
        return self._scans.get(scan_id)

    def list_scans(self) -> List[RedTeamScanResult]:
        return sorted(
            self._scans.values(), key=lambda r: r.started_at, reverse=True)


_red_team_service: Optional[RedTeamService] = None


def get_red_team_service() -> RedTeamService:
    """Get the global red team service instance."""
    global _red_team_service
    if _red_team_service is None:
        _red_team_service = RedTeamService()
    return _red_team_service
