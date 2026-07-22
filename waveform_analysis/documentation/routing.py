"""Deterministic transition rules for documentation-DAG result envelopes."""

from __future__ import annotations

from .types import DocumentationDAG, NodeDefinition, NodeExecutionResult


def route_result(
    dag: DocumentationDAG,
    node: NodeDefinition,
    result: NodeExecutionResult,
    retry_count: int,
) -> str:
    """Map a validated result to its next node without interpreting artifacts."""
    status = result.node_status
    if status in {"success", "passed", "no_blocking_ambiguities"}:
        key = "success" if status == "success" else status
        return node.transitions.get(key, node.transitions.get("success", "terminal"))

    if status in {"missing_evidence", "plugin_not_found", "insufficient_context"}:
        return node.transitions.get(status, node.transitions.get("failure", "human_review"))

    if status in {"requires_human", "semantic_failure"}:
        return node.transitions.get(status, "human_review")

    if status in {"writing_failure", "fact_error", "semantic_error"}:
        return node.transitions.get(status, node.transitions.get("failure", "human_review"))

    retry_limit = dag.retry_policy.get(node.node_id, 0)
    if retry_count < retry_limit:
        return node.node_id
    return dag.on_retry_exhausted
