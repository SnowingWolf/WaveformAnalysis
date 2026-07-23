"""Validation for DAG definitions, result envelopes, and artifact payloads."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .types import DocumentationDAG, NodeExecutionResult

VALID_STATUSES = {
    "success",
    "passed",
    "no_blocking_ambiguities",
    "missing_evidence",
    "plugin_not_found",
    "insufficient_context",
    "requires_human",
    "semantic_failure",
    "writing_failure",
    "fact_error",
    "semantic_error",
    "failure",
}
VALID_CONFIDENCE = {"low", "medium", "high"}


def validate_dag(dag: DocumentationDAG) -> list[str]:
    """Return configuration errors without executing any documentation node."""
    issues: list[str] = []
    if dag.initial_node not in dag.nodes:
        issues.append(f"Unknown initial node: {dag.initial_node}")
    for node in dag.nodes.values():
        for destination in node.transitions.values():
            if destination != "terminal" and destination not in dag.nodes:
                issues.append(f"Node `{node.node_id}` routes to unknown node `{destination}`")
        if node.output_artifact and node.output_artifact not in dag.artifacts:
            issues.append(f"Node `{node.node_id}` emits unknown artifact `{node.output_artifact}`")
    return issues


def validate_result(
    dag: DocumentationDAG,
    result: NodeExecutionResult,
    schema_root: Path,
    *,
    available_artifacts: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Validate the uniform envelope and its artifact against its declared schema."""
    issues: list[str] = []
    if result.dag_name != dag.name:
        issues.append("Result dag_name does not match the active DAG")
    if result.dag_version != dag.version:
        issues.append("Result dag_version does not match the active DAG")
    node = dag.nodes.get(result.node_id)
    if node is None:
        return [*issues, f"Unknown result node_id: {result.node_id}"]
    if result.node_status not in VALID_STATUSES:
        issues.append(f"Unsupported node_status: {result.node_status}")
    if result.confidence not in VALID_CONFIDENCE:
        issues.append(f"Unsupported confidence: {result.confidence}")
    if not isinstance(result.issues, list) or not isinstance(result.requested_evidence, list):
        issues.append("issues and requested_evidence must be lists")
    if result.node_status in {"success", "passed", "no_blocking_ambiguities"}:
        if not result.artifact_type or not isinstance(result.artifact, dict):
            issues.append("Successful results must include an artifact_type and object artifact")
        elif node.output_schema and result.artifact_type != node.output_schema:
            issues.append(
                f"Node `{node.node_id}` requires `{node.output_schema}`, got `{result.artifact_type}`"
            )
        elif node.output_schema:
            issues.extend(
                validate_artifact(
                    result.artifact, schema_root / f"{node.output_schema}.schema.json"
                )
            )
            if not issues:
                issues.extend(
                    validate_acceptance(
                        node_id=node.node_id,
                        output_artifact=node.output_artifact,
                        artifact=result.artifact,
                        acceptance=node.acceptance,
                        available_artifacts=available_artifacts or {},
                        node_status=result.node_status,
                    )
                )
    if result.node_status == "missing_evidence" and not result.requested_evidence:
        issues.append("missing_evidence results must request exact evidence")
    return issues


def validate_acceptance(
    *,
    node_id: str,
    output_artifact: str | None,
    artifact: dict[str, Any],
    acceptance: dict[str, Any],
    available_artifacts: dict[str, dict[str, Any]],
    node_status: str,
) -> list[str]:
    """Enforce executable acceptance rules beyond top-level JSON Schema.

    The generic ``required`` list uses artifact-qualified dotted paths from the
    DAG definition. Node-specific checks cover relationships that JSON Schema
    cannot express with the intentionally lightweight bundled contracts.
    """
    issues: list[str] = []
    artifact_name = output_artifact or "artifact"
    for path in acceptance.get("required", []):
        relative_path = path.removeprefix(f"{artifact_name}.")
        if _lookup(artifact, relative_path) is _MISSING:
            issues.append(f"Acceptance requires artifact field: {path}")

    if node_id == "recover_semantics":
        issues.extend(_validate_semantic_spec(artifact))
    elif node_id == "detect_ambiguities":
        issues.extend(_validate_ambiguity_report(artifact))
    elif node_id == "generate_agent_doc":
        issues.extend(_validate_agent_doc_inputs(artifact, available_artifacts))
    elif node_id == "verify_agent_doc":
        issues.extend(_validate_verification_report(artifact, node_status))
    return issues


def _validate_semantic_spec(artifact: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for index, rule in enumerate(artifact.get("decision_rules", [])):
        if not isinstance(rule, dict) or not rule.get("evidence"):
            issues.append(f"decision_rules[{index}] must include non-empty evidence")
        elif not isinstance(rule["evidence"], list):
            issues.append(f"decision_rules[{index}].evidence must be an array")
        condition = rule.get("condition") if isinstance(rule, dict) else None
        if not isinstance(condition, str) or not any(
            operator in condition for operator in ("<=", ">=", "==", "!=", "<", ">")
        ):
            issues.append(f"decision_rules[{index}] must state an explicit comparison operator")

    for index, step in enumerate(artifact.get("processing_steps", [])):
        if (
            not isinstance(step, dict)
            or not isinstance(step.get("evidence"), list)
            or not step["evidence"]
        ):
            issues.append(f"processing_steps[{index}] must include non-empty evidence")

    origins = artifact.get("field_origins", {})
    if not isinstance(origins, dict) or not isinstance(origins.get("anchor_copied"), list):
        issues.append("field_origins.anchor_copied must be an array")
    if not isinstance(origins, dict) or not isinstance(origins.get("cluster_derived"), list):
        issues.append("field_origins.cluster_derived must be an array")
    return issues


def _validate_ambiguity_report(artifact: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for index, ambiguity in enumerate(artifact.get("ambiguities", [])):
        if not isinstance(ambiguity, dict):
            issues.append(f"ambiguities[{index}] must be an object")
            continue
        if ambiguity.get("severity") not in {"blocking", "non_blocking"}:
            issues.append(f"ambiguities[{index}].severity must be blocking or non_blocking")
        if (
            not isinstance(ambiguity.get("affected_sections"), list)
            or not ambiguity["affected_sections"]
        ):
            issues.append(f"ambiguities[{index}] must list affected_sections")
        if ambiguity.get("severity") == "blocking" and not ambiguity.get("requested_evidence"):
            issues.append(f"blocking ambiguities[{index}] must request resolving evidence")
    return issues


def _validate_agent_doc_inputs(
    artifact: dict[str, Any], available_artifacts: dict[str, dict[str, Any]]
) -> list[str]:
    report = available_artifacts.get("ambiguity_report", {})
    blocking = report.get("blocking_ambiguities", []) if isinstance(report, dict) else []
    if blocking:
        return ["generate_agent_doc cannot run while blocking ambiguities remain"]
    facts = available_artifacts.get("plugin_facts", {})
    contract = facts.get("contract") if isinstance(facts, dict) else None
    if not isinstance(contract, dict):
        return ["generate_agent_doc requires plugin_facts.contract"]
    return validate_agent_doc_contract(artifact, contract)


def validate_agent_doc_contract(agent_doc: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    """Reject generated claims that disagree with deterministic source facts."""
    issues: list[str] = []
    narrative = _narrative_text(agent_doc)
    steps = "\n".join(str(item) for item in agent_doc.get("steps", []))
    output = contract.get("output", {})
    annotation = str(output.get("annotation", "")).lower()
    if "list" in annotation and re.search(r"\b(dict|dictionary|mapping)\b", narrative):
        issues.append(
            "AgentDoc output container contradicts plugin_facts.contract.output.annotation"
        )

    option_defaults = {
        str(item.get("name")): str(item.get("default"))
        for item in contract.get("options", [])
        if isinstance(item, dict) and item.get("name") is not None
    }
    for call in contract.get("calls", []):
        if not isinstance(call, dict):
            continue
        call_name = str(call.get("name", ""))
        if call_name and not _contains_term(steps, call_name):
            issues.append(f"AgentDoc steps must name returned call `{call_name}`")
        for argument in call.get("keyword_arguments", []):
            if not _contains_term(steps, str(argument)):
                issues.append(f"AgentDoc steps must include `{call_name}` argument `{argument}`")
        for option_name in call.get("option_arguments", []):
            name = str(option_name)
            default = option_defaults.get(name)
            if default is None:
                continue
            if not _contains_term(steps, name):
                issues.append(f"AgentDoc steps must mention option `{name}`")
            elif not _option_default_matches(steps, name, default):
                issues.append(
                    f"AgentDoc option `{name}` default must match `{default}` from contract"
                )
    return issues


def _narrative_text(agent_doc: dict[str, Any]) -> str:
    values = []
    for name in ("summary", "overview", "steps", "edge_cases", "operational_notes"):
        value = agent_doc.get(name, "")
        values.extend(value if isinstance(value, list) else [value])
    return "\n".join(str(value).lower() for value in values)


def _contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<![\w.]){re.escape(term)}(?![\w.])", text, re.IGNORECASE))


def _option_default_matches(text: str, option_name: str, default: str) -> bool:
    escaped_name = re.escape(option_name)
    escaped_default = re.escape(default)
    return bool(
        re.search(
            rf"{escaped_name}.{{0,100}}?(?:default|=|is).{{0,20}}?{escaped_default}",
            text,
            re.IGNORECASE,
        )
    )


def _validate_verification_report(artifact: dict[str, Any], node_status: str) -> list[str]:
    issues: list[str] = []
    if node_status == "passed" and artifact.get("passed") is not True:
        issues.append("A passed verification result must set artifact.passed to true")
    if artifact.get("passed") is True:
        for field in (
            "contradicted_claims",
            "unsupported_critical_claims",
            "blocking_ambiguities",
        ):
            if artifact.get(field) != 0:
                issues.append(f"Passing verification requires {field} == 0")
    return issues


_MISSING = object()


def _lookup(value: object, path: str) -> object:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def validate_artifact(artifact: dict[str, Any], schema_path: Path) -> list[str]:
    """Validate the subset of JSON Schema used by bundled artifact contracts."""
    import json

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    issues: list[str] = []
    for field in schema.get("required", []):
        if field not in artifact:
            issues.append(f"Missing required artifact field: {field}")
    for field, definition in schema.get("properties", {}).items():
        if field not in artifact:
            continue
        value = artifact[field]
        expected_type = definition.get("type")
        if expected_type and not _matches_type(value, expected_type):
            issues.append(f"Artifact field `{field}` must be {expected_type}")
        if "enum" in definition and value not in definition["enum"]:
            issues.append(f"Artifact field `{field}` has unsupported value `{value}`")
    return issues


def _matches_type(value: Any, expected_type: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "number": isinstance(value, int | float) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "null": value is None,
    }.get(expected_type, True)
