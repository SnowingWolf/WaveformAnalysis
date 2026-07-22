"""Typed protocol objects for documentation-DAG execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NodeDefinition:
    """One executable documentation-DAG node."""

    node_id: str
    executor: str
    role: str | None
    objective: str
    inputs: list[str]
    instructions: list[str]
    constraints: list[str]
    acceptance: dict[str, Any]
    output_artifact: str | None
    output_schema: str | None
    output_path: str | None
    preconditions: list[str]
    transitions: dict[str, str]


@dataclass(frozen=True)
class DocumentationDAG:
    """Parsed DAG definition and artifact schema registry."""

    name: str
    version: int
    description: str
    initial_node: str
    terminal_nodes: set[str]
    global_context: dict[str, str]
    global_constraints: list[str]
    artifacts: dict[str, str]
    nodes: dict[str, NodeDefinition]
    retry_policy: dict[str, int]
    on_retry_exhausted: str


@dataclass
class DAGState:
    """Persistable state for one plugin documentation workflow."""

    plugin_name: str
    repository_root: str
    current_node: str
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    retries: dict[str, int] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class NodeExecutionRequest:
    """The complete instruction contract supplied to one executor."""

    dag_name: str
    dag_version: int
    node_id: str
    executor: str
    role: str | None
    objective: str
    instructions: list[str]
    constraints: list[str]
    acceptance: dict[str, Any]
    input_artifacts: dict[str, dict[str, Any]]
    output_schema: dict[str, Any] | None
    prompt: str | None


@dataclass(frozen=True)
class NodeExecutionResult:
    """Uniform envelope returned by deterministic, agent, and hybrid nodes."""

    dag_name: str
    dag_version: int
    node_id: str
    node_status: str
    artifact_type: str | None
    artifact: dict[str, Any] | None
    issues: list[dict[str, Any]]
    requested_evidence: list[dict[str, Any]]
    confidence: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> NodeExecutionResult:
        return cls(
            dag_name=str(value.get("dag_name", "")),
            dag_version=int(value.get("dag_version", 0)),
            node_id=str(value.get("node_id", "")),
            node_status=str(value.get("node_status", "")),
            artifact_type=value.get("artifact_type"),
            artifact=value.get("artifact"),
            issues=list(value.get("issues", [])),
            requested_evidence=list(value.get("requested_evidence", [])),
            confidence=str(value.get("confidence", "")),
        )
