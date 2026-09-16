#!/usr/bin/env python3
"""Run an AI Red Teaming Agent scan against the insurance claims application.

Red teaming is a pre-production safety activity: a scan sends many adversarial
prompts to the target, so it takes minutes and is not something to run in the
request path. This script is the supported way to run a scan.

PyRIT (the engine behind the red team agent) is a heavy dependency and is
deliberately not installed in the API container image. Install it here first::

    cd backend
    uv pip install "azure-ai-evaluation[redteam]"

Authentication uses ``DefaultAzureCredential``; run ``az login`` first. The
signed-in identity needs access to the Foundry project.

Examples
--------
Scan the full multi-agent workflow with the default risk categories::

    python scripts/run_red_team_scan.py

Scan the base model with more objectives and easy-complexity attacks::

    python scripts/run_red_team_scan.py --target model --num-objectives 3 \
        --complexity EASY --output scan.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Make the app package importable when run from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=["workflow", "model"],
        default="workflow",
        help="Scan the full agent workflow (default) or the base model deployment",
    )
    parser.add_argument(
        "--num-objectives",
        type=int,
        default=1,
        help="Attack objectives per risk category (default: 1)",
    )
    parser.add_argument(
        "--risk-categories",
        nargs="*",
        default=["Violence", "HateUnfairness", "Sexual", "SelfHarm"],
        help="Risk categories to cover",
    )
    parser.add_argument(
        "--complexity",
        nargs="*",
        default=[],
        choices=["EASY", "MODERATE", "DIFFICULT"],
        help="Attack strategy complexity groups. Omit for baseline direct attacks only.",
    )
    parser.add_argument(
        "--scan-name",
        default=None,
        help="Name for the scan as it appears in the Foundry portal",
    )
    parser.add_argument(
        "--output",
        default="red-team-scan.json",
        help="Where to write the JSON scorecard",
    )
    return parser.parse_args()


async def main() -> int:
    load_dotenv()
    args = parse_args()

    try:
        import azure.ai.evaluation.red_team  # noqa: F401
    except ImportError:
        print(
            'ERROR: red teaming extras are not installed.\n'
            '       Install with: uv pip install "azure-ai-evaluation[redteam]"',
            file=sys.stderr,
        )
        return 2

    from app.models.evaluation import (
        RedTeamComplexity,
        RedTeamRiskCategory,
        RedTeamScanRequest,
    )
    from app.services.red_team_service import get_red_team_service

    service = get_red_team_service()
    detail = service.availability_detail()
    if not detail["available"]:
        print(f"ERROR: red teaming unavailable: {detail['reason']}", file=sys.stderr)
        print(
            "       Set AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP and "
            "AZURE_AI_PROJECT_NAME (or AZURE_AI_PROJECT).",
            file=sys.stderr,
        )
        return 2

    request = RedTeamScanRequest(
        scan_name=args.scan_name,
        risk_categories=[RedTeamRiskCategory(c) for c in args.risk_categories],
        num_objectives=args.num_objectives,
        complexity=(
            [RedTeamComplexity(c) for c in args.complexity]
            if args.complexity
            else [RedTeamComplexity.BASELINE]
        ),
        target=args.target,
    )

    print(
        f"Starting red team scan against '{args.target}' "
        f"({len(request.risk_categories)} risk categories x "
        f"{request.num_objectives} objectives). This may take several minutes..."
    )

    result = await service.run_scan(request)

    if result.status.value == "failed":
        print(f"\nScan FAILED: {result.error_message}", file=sys.stderr)
        return 1

    print(f"\nScan complete in {(result.duration_ms or 0) / 1000:.1f}s")
    if result.overall_attack_success_rate is not None:
        print(
            f"Overall Attack Success Rate: "
            f"{result.overall_attack_success_rate:.1f}% (lower is better)"
        )
    for entry in result.by_risk_category:
        if entry.attack_success_rate is not None:
            print(f"  {entry.name:<20} {entry.attack_success_rate:.1f}%")
    if result.studio_url:
        print(f"\nView in the Foundry portal: {result.studio_url}")

    if result.scorecard:
        Path(args.output).write_text(
            json.dumps(result.scorecard, indent=2, default=str), encoding="utf-8"
        )
        print(f"Scorecard written to {os.path.abspath(args.output)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
