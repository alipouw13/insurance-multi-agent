"""Microsoft Foundry ("new Foundry") agent registration and execution.

The classic Agents API (``project_client.agents.create_agent`` with ``asst_*``
IDs) registers agents under **Classic agents** in the Foundry portal. The new
Foundry agents list is backed by a different API: named, versioned agents
created with ``project.agents.create_version`` and a ``PromptAgentDefinition``,
and invoked through the OpenAI Responses API with an ``agent_reference``.

This module registers the six claims agents as new Foundry prompt agents and
runs the workflow against them, resolving function calls locally.

Requires ``azure-ai-projects>=2.x``.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

#: Registered agent name -> agent version object
_REGISTERED: Dict[str, Any] = {}
_REGISTRATION_ATTEMPTED = False


# ---------------------------------------------------------------------------
# Function tools
# ---------------------------------------------------------------------------

def _tool(name: str, description: str, properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    """Build a function tool definition for a PromptAgentDefinition."""
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "strict": True,
    }


CLAIM_ASSESSOR_TOOLS = [
    _tool(
        "get_vehicle_details",
        "Look up vehicle specifications and market value from a VIN.",
        {"vin": {"type": "string", "description": "Vehicle Identification Number"}},
        ["vin"],
    ),
    _tool(
        "analyze_image",
        "Analyze a damage photo and extract structured damage information.",
        {"image_path": {"type": "string", "description": "Path to the image file"}},
        ["image_path"],
    ),
    _tool(
        "process_claim_document",
        "Extract structured fields from a claim document using Content Understanding.",
        {"file_path": {"type": "string", "description": "Path to the claim document"}},
        ["file_path"],
    ),
]

POLICY_CHECKER_TOOLS = [
    _tool(
        "get_policy_details",
        "Retrieve the policy record for a policy number.",
        {"policy_number": {"type": "string", "description": "Policy number"}},
        ["policy_number"],
    ),
    _tool(
        "search_policy_documents",
        "Semantic search across policy documents for coverage terms and exclusions.",
        {"query": {"type": "string", "description": "Search query"}},
        ["query"],
    ),
]

RISK_ANALYST_TOOLS = [
    _tool(
        "get_claimant_history",
        "Retrieve prior claims and fraud indicators for a claimant.",
        {"claimant_id": {"type": "string", "description": "Claimant identifier"}},
        ["claimant_id"],
    ),
]


def _function_registry() -> Dict[str, Callable[..., Any]]:
    """Map tool names to their Python implementations."""
    from app.workflow.agents.azure_claim_assessor_v2 import get_claim_assessor_functions
    from app.workflow.agents.azure_policy_checker_v2 import get_policy_checker_functions
    from app.workflow.agents.azure_risk_analyst_v2 import get_risk_analyst_functions

    registry: Dict[str, Callable[..., Any]] = {}
    for getter in (
        get_claim_assessor_functions,
        get_policy_checker_functions,
        get_risk_analyst_functions,
    ):
        try:
            registry.update(getter())
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not load functions from %s: %s", getter.__name__, exc)
    return registry


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

SUPERVISOR_INSTRUCTIONS = """You are the Insurance Claims Supervisor coordinating a team of specialists.

Assess the claim end to end and produce a single recommendation. Consider damage
plausibility and cost, policy coverage and exclusions, fraud and risk signals,
historical claims context, and what needs to be communicated to the customer.

Always finish with exactly this structure:

ASSESSMENT_COMPLETE

PRIMARY RECOMMENDATION: [APPROVE/DENY/INVESTIGATE] (Confidence: HIGH/MEDIUM/LOW)
- Brief rationale for the recommendation

SUPPORTING FACTORS:
- Factors supporting the recommendation

RISK FACTORS:
- Risks or concerns

INFORMATION GAPS:
- Missing information, if any

RECOMMENDED NEXT STEPS:
- Concrete next actions
"""

def _fabric_tool() -> Optional[Dict[str, Any]]:
    """Build the Fabric data agent tool from the configured connection.

    Returns ``None`` when no Fabric connection is configured or it cannot be
    resolved, so the agent is still registered (without enterprise data access)
    rather than failing registration outright.
    """
    settings = get_settings()
    connection_name = settings.fabric_connection_name
    if not connection_name:
        logger.info(
            "FABRIC_CONNECTION_NAME not set - claims-data-analyst registered without "
            "the Fabric data agent tool")
        return None

    try:
        project = _get_project_client()
        connection = project.connections.get(connection_name)
        connection_id = getattr(connection, "id", None)
        if not connection_id:
            logger.warning("Fabric connection '%s' has no id", connection_name)
            return None

        logger.info("Attaching Fabric data agent connection '%s'", connection_name)
        # The payload property is keyed by the tool type name.
        return {
            "type": "fabric_dataagent_preview",
            "fabric_dataagent_preview": {
                "connections": [{"connection_id": connection_id}]
            },
        }
    except Exception as exc:
        logger.warning(
            "Could not resolve Fabric connection '%s': %s", connection_name, exc)
        return None


AGENT_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "claim-assessor",
        "instructions": (
            "You are a Claim Assessor for motor and property insurance claims. "
            "Evaluate damage severity, validate repair estimates against vehicle "
            "specifications and market value, and review the completeness of "
            "supporting evidence. Use your tools to look up vehicle details, "
            "analyze damage photos and extract data from claim documents. "
            "Be specific about figures and state clearly when evidence is missing."
        ),
        "tools": CLAIM_ASSESSOR_TOOLS,
    },
    {
        "name": "policy-checker",
        "instructions": (
            "You are a Policy Checker. Determine whether a claim is covered by the "
            "policy. Verify coverage types and limits, identify exclusions and "
            "deductibles, and cite the specific policy language you relied on. "
            "Use your tools to retrieve the policy and search policy documents. "
            "Policies may be in English or Dutch."
        ),
        "tools": POLICY_CHECKER_TOOLS,
    },
    {
        "name": "risk-analyst",
        "instructions": (
            "You are a Risk Analyst specializing in insurance fraud detection. "
            "Assess the likelihood of fraud, identify red flags, and produce a "
            "quantitative risk score with justification. Use your tools to review "
            "the claimant's history. Distinguish clearly between suspicion and "
            "evidence, and avoid accusing a claimant without support."
        ),
        "tools": RISK_ANALYST_TOOLS,
    },
    {
        "name": "communication-agent",
        "instructions": (
            "You are a Communication Agent for an insurance company. Draft clear, "
            "empathetic and professional customer correspondence: status updates, "
            "requests for missing documentation, and decision explanations. Keep an "
            "appropriate insurance-industry tone and never promise an outcome that "
            "has not been decided."
        ),
        "tools": [],
    },
    {
        "name": "claims-data-analyst",
        "instructions": (
            "You are a Claims Data Analyst with access to historical claims data "
            "in Microsoft Fabric. Use the Fabric data agent tool to query the "
            "claims lakehouse for claim patterns, regional benchmarks, fraud "
            "trends and claimant risk profiles. Always give concrete numbers and "
            "state the basis for comparison. If the data is unavailable, say so "
            "rather than estimating."
        ),
        "tools": [],
        # Resolved at registration time from FABRIC_CONNECTION_NAME.
        "fabric": True,
    },
    {
        "name": "insurance-supervisor",
        "instructions": SUPERVISOR_INSTRUCTIONS,
        "tools": [],
    },
]

SUPERVISOR_AGENT_NAME = "insurance-supervisor"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def _get_project_client():
    """Create an AIProjectClient for the configured Foundry project."""
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    settings = get_settings()
    endpoint = settings.project_endpoint
    if not endpoint:
        raise ValueError("PROJECT_ENDPOINT is not configured")

    return AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())


def get_agent_model() -> str:
    """Model deployment used for the Foundry agents."""
    settings = get_settings()
    return settings.foundry_agent_model or settings.azure_openai_deployment_name or "gpt-4.1-mini"


def register_foundry_agents(force: bool = False) -> Dict[str, Any]:
    """Register (or update) the claims agents as new Foundry prompt agents.

    ``create_version`` is idempotent by name: calling it again publishes a new
    version of the same agent rather than creating a duplicate, so the portal
    shows one agent per role with an incrementing version.
    """
    global _REGISTRATION_ATTEMPTED

    if _REGISTERED and not force:
        return _REGISTERED

    _REGISTRATION_ATTEMPTED = True

    try:
        from azure.ai.projects.models import PromptAgentDefinition
    except ImportError as exc:
        logger.warning(
            "azure-ai-projects v2 is required for new Foundry agents (%s). "
            "Falling back to the classic agent path.", exc
        )
        return {}

    try:
        project = _get_project_client()
    except Exception as exc:
        logger.warning("Could not create Foundry project client: %s", exc)
        return {}

    model = get_agent_model()
    logger.info("Registering %d Foundry agents with model '%s'", len(AGENT_DEFINITIONS), model)

    fabric_tool = _fabric_tool()

    for definition in AGENT_DEFINITIONS:
        name = definition["name"]
        try:
            tools = list(definition["tools"])
            if definition.get("fabric") and fabric_tool:
                tools.append(fabric_tool)

            kwargs: Dict[str, Any] = {
                "model": model,
                "instructions": definition["instructions"],
            }
            if tools:
                kwargs["tools"] = tools

            agent = project.agents.create_version(
                agent_name=name,
                definition=PromptAgentDefinition(**kwargs),
            )
            _REGISTERED[name] = agent
            logger.info(
                "Registered Foundry agent '%s' (version %s)",
                name, getattr(agent, "version", "?"),
            )
        except Exception as exc:
            logger.error("Failed to register Foundry agent '%s': %s", name, exc)

    return _REGISTERED


def foundry_agents_available() -> bool:
    """Whether the new Foundry agents were registered successfully."""
    return bool(_REGISTERED)


def get_registered_agents() -> Dict[str, Any]:
    return dict(_REGISTERED)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

MAX_TOOL_ITERATIONS = 6


def _agent_reference(name: str) -> Dict[str, Any]:
    return {"agent_reference": {"name": name, "type": "agent_reference"}}


def run_agent(
    agent_name: str,
    prompt: str,
    conversation_id: Optional[str] = None,
    project: Any = None,
    openai_client: Any = None,
) -> Dict[str, Any]:
    """Run a single Foundry agent, resolving any function calls it requests.

    Returns ``{"text": str, "tool_calls": [...]}``.
    """
    if project is None:
        project = _get_project_client()
    if openai_client is None:
        openai_client = project.get_openai_client()

    functions = _function_registry()
    tool_calls: List[Dict[str, Any]] = []

    # The Responses API expects a conversation to anchor an agent_reference run.
    owns_conversation = conversation_id is None
    if owns_conversation:
        conversation_id = openai_client.conversations.create().id

    request: Dict[str, Any] = {
        "input": prompt,
        "conversation": conversation_id,
        "extra_body": _agent_reference(agent_name),
    }

    try:
        response = openai_client.responses.create(**request)
    except Exception as exc:
        body = getattr(exc, "response", None)
        detail = ""
        if body is not None:
            try:
                detail = body.text
            except Exception:
                detail = ""
        logger.error("Responses API call for '%s' failed: %s %s", agent_name, exc, detail)
        raise

    for _ in range(MAX_TOOL_ITERATIONS):
        outputs: List[Dict[str, Any]] = []

        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "function_call":
                continue

            fn_name = getattr(item, "name", "")
            raw_args = getattr(item, "arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                args = {}

            impl = functions.get(fn_name)
            if impl is None:
                result: Any = {"error": f"Unknown function '{fn_name}'"}
            else:
                try:
                    result = impl(**args)
                except Exception as exc:
                    logger.warning("Tool '%s' failed: %s", fn_name, exc)
                    result = {"error": str(exc)}

            tool_calls.append({"name": fn_name, "arguments": args})
            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": getattr(item, "call_id", None),
                    "output": json.dumps(result, default=str),
                }
            )

        if not outputs:
            break

        follow_up: Dict[str, Any] = {
            "input": outputs,
            "extra_body": _agent_reference(agent_name),
        }
        if conversation_id:
            follow_up["conversation"] = conversation_id
        response = openai_client.responses.create(**follow_up)

    return {
        "text": getattr(response, "output_text", "") or "",
        "tool_calls": tool_calls,
    }


def run_claim_workflow(claim: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run a claim through the Foundry agents and return workflow chunks.

    Returns the same chunk shape the Azure AI Agents v2 supervisor produces -
    a list of ``{node_name: {"messages": [...], "source": "azure_agents_v2"}}`` -
    so the API layer does not need to know which backend ran the claim.
    """
    if not _REGISTERED:
        register_foundry_agents()
    if not _REGISTERED:
        raise RuntimeError("No Foundry agents are registered")

    project = _get_project_client()
    openai_client = project.get_openai_client()

    claim_json = json.dumps(claim, indent=2, default=str)
    chunks: List[Dict[str, Any]] = []

    def emit(node: str, messages: List[Dict[str, Any]]) -> None:
        chunks.append({node: {"messages": messages, "source": "azure_agents_v2"}})

    emit(
        "supervisor",
        [
            {
                "role": "human",
                "content": (
                    "Please process this insurance claim through your team of "
                    f"specialists:\n\n{claim_json}"
                ),
            }
        ],
    )

    specialists = [
        ("claim-assessor", "claim_assessor"),
        ("policy-checker", "policy_checker"),
        ("risk-analyst", "risk_analyst"),
        ("claims-data-analyst", "claims_data_analyst"),
        ("communication-agent", "communication_agent"),
    ]

    findings: List[str] = []
    for agent_name, node in specialists:
        if agent_name not in _REGISTERED:
            continue
        try:
            outcome = run_agent(
                agent_name,
                f"Assess this insurance claim from your specialist perspective:\n\n{claim_json}",
                project=project,
                openai_client=openai_client,
            )
            text = outcome["text"]
            findings.append(f"### {node}\n{text}")

            messages: List[Dict[str, Any]] = []
            for call in outcome["tool_calls"]:
                messages.append(
                    {
                        "role": "assistant",
                        "content": (
                            f"TOOL_CALL: {call['name']}("
                            f"{json.dumps(call['arguments'], default=str)})"
                        ),
                    }
                )
            messages.append({"role": "assistant", "content": text})
            emit(node, messages)
        except Exception as exc:
            message = str(exc)
            if "fabric_dataagent_preview" in message or "tools[0].type" in message:
                # The Fabric data agent tool can be attached to an agent version
                # (and works in the portal playground) but the Responses API does
                # not yet accept it as a tool type when invoking the agent.
                note = (
                    f"[{node} skipped: the Fabric data agent tool is attached to this "
                    "agent but is not yet invocable through the Responses API. "
                    "Use the agent in the Foundry playground for Fabric queries.]"
                )
                logger.warning(
                    "Skipping '%s': Fabric data agent tool is not supported by the "
                    "Responses API yet", agent_name,
                )
            else:
                note = f"[{node} unavailable: {exc}]"
                logger.error("Foundry agent '%s' failed: %s", agent_name, exc)
            emit(node, [{"role": "assistant", "content": note}])

    summary_prompt = (
        "Synthesize the specialist assessments below into your final recommendation "
        f"for this claim.\n\nCLAIM:\n{claim_json}\n\n"
        "SPECIALIST ASSESSMENTS:\n" + "\n\n".join(findings)
    )
    supervisor = run_agent(
        SUPERVISOR_AGENT_NAME, summary_prompt, project=project, openai_client=openai_client
    )
    emit("supervisor", [{"role": "assistant", "content": supervisor["text"]}])

    return chunks
