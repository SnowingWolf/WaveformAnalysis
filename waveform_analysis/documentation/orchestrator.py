"""Orchestrate one documentation-DAG node at a time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from .artifact_store import FileArtifactStore
from .routing import route_result
from .types import (
    DAGState,
    DocumentationDAG,
    NodeDefinition,
    NodeExecutionRequest,
    NodeExecutionResult,
)
from .validators import validate_dag, validate_result

PACKAGE_ROOT = Path(__file__).parent
DAG_PATH = PACKAGE_ROOT / "dags" / "plugin_documentation.yaml"
PROMPT_ROOT = PACKAGE_ROOT / "prompts"
SCHEMA_ROOT = PACKAGE_ROOT / "schemas"


def load_plugin_documentation_dag(path: str | Path | None = None) -> DocumentationDAG:
    """Load and validate the bundled plugin-documentation DAG definition."""
    raw = yaml.safe_load(Path(path or DAG_PATH).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Documentation DAG must be a mapping")
    nodes = {
        node_id: _parse_node(node_id, definition)
        for node_id, definition in (raw.get("nodes") or {}).items()
    }
    dag = DocumentationDAG(
        name=_required_string(raw, "name"),
        version=_required_int(raw, "version"),
        description=_required_string(raw, "description"),
        initial_node=_required_string(raw, "initial_node"),
        terminal_nodes=set(_string_list(raw, "terminal_nodes")),
        global_context=dict(raw.get("global_context") or {}),
        global_constraints=_string_list(raw, "global_constraints"),
        artifacts={
            name: _required_string(definition, "schema")
            for name, definition in (raw.get("artifacts") or {}).items()
        },
        nodes=nodes,
        retry_policy={
            str(key): int(value) for key, value in (raw.get("retry_policy") or {}).items()
        },
        on_retry_exhausted=_required_string(raw, "on_retry_exhausted"),
    )
    if issues := validate_dag(dag):
        raise ValueError("Invalid documentation DAG: " + "; ".join(issues))
    return dag


class DocumentationOrchestrator:
    """Build, validate, persist, and route one node result at a time.

    The orchestrator deliberately has no model client. Callers run the returned
    ``NodeExecutionRequest`` with their chosen agent or deterministic executor,
    then submit the structured result through :meth:`accept_result`.
    """

    def __init__(
        self,
        dag: DocumentationDAG | None = None,
        *,
        artifact_store: FileArtifactStore | None = None,
        schema_root: str | Path = SCHEMA_ROOT,
        prompt_root: str | Path = PROMPT_ROOT,
    ):
        self.dag = dag or load_plugin_documentation_dag()
        self.artifact_store = artifact_store
        self.schema_root = Path(schema_root)
        self.prompt_root = Path(prompt_root)

    def new_state(self, plugin_name: str, repository_root: str | Path) -> DAGState:
        """Start a workflow at the DAG's deterministic discovery node."""
        return DAGState(
            plugin_name=plugin_name,
            repository_root=str(Path(repository_root).resolve()),
            current_node=self.dag.initial_node,
        )

    def build_request(self, state: DAGState) -> NodeExecutionRequest:
        """Build the bounded contract for the current node only."""
        node = self._node(state)
        inputs = self._input_artifacts(node, state)
        prompt = self._render_prompt(node, inputs)
        return NodeExecutionRequest(
            dag_name=self.dag.name,
            dag_version=self.dag.version,
            node_id=node.node_id,
            executor=node.executor,
            role=node.role,
            objective=node.objective,
            instructions=node.instructions,
            constraints=[*self.dag.global_constraints, *node.constraints],
            acceptance=node.acceptance,
            input_artifacts=inputs,
            output_schema=self._load_schema(node.output_schema),
            prompt=prompt,
        )

    def accept_result(
        self, state: DAGState, result: NodeExecutionResult | dict[str, Any]
    ) -> DAGState:
        """Validate a node result, persist its artifact, and select the next node."""
        parsed = (
            result
            if isinstance(result, NodeExecutionResult)
            else NodeExecutionResult.from_mapping(result)
        )
        if parsed.node_id != state.current_node:
            raise ValueError(
                f"Result belongs to `{parsed.node_id}`, expected `{state.current_node}`"
            )
        if issues := validate_result(
            self.dag,
            parsed,
            self.schema_root,
            available_artifacts=state.artifacts,
        ):
            raise ValueError("Invalid node result: " + "; ".join(issues))

        node = self._node(state)
        if parsed.artifact is not None and node.output_artifact:
            state.artifacts[node.output_artifact] = parsed.artifact
            self._persist_artifact(state, node.output_artifact, parsed.artifact)

        retries = state.retries.get(node.node_id, 0)
        next_node = route_result(self.dag, node, parsed, retries)
        if next_node == node.node_id:
            state.retries[node.node_id] = retries + 1
        state.history.append(
            {"node_id": node.node_id, "status": parsed.node_status, "next_node": next_node}
        )
        state.current_node = next_node
        self._persist_state(state)
        return state

    def publish(self, state: DAGState, destination_root: str | Path) -> Path:
        """Atomically write AgentDoc only after a passing verification report."""
        report = state.artifacts.get("verification_report", {})
        if report.get("passed") is not True:
            raise ValueError("AgentDoc publication requires verification_report.passed == true")
        agent_doc = state.artifacts.get("agent_doc")
        if not agent_doc:
            raise ValueError("No agent_doc artifact is available for publication")

        output = Path(destination_root) / f"{state.plugin_name}.yaml"
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".yaml.tmp")
        temporary.write_text(
            yaml.safe_dump(agent_doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        temporary.replace(output)
        return output

    def execute_agent_node(
        self,
        state: DAGState,
        agent_runner: Callable[[NodeExecutionRequest], NodeExecutionResult | dict[str, Any]],
    ) -> DAGState:
        """Run exactly one agent/hybrid node through an injected external runner."""
        request = self.build_request(state)
        if request.executor not in {"agent", "hybrid"}:
            raise ValueError(
                f"Node `{request.node_id}` requires `{request.executor}`, not an agent runner"
            )
        return self.accept_result(state, agent_runner(request))

    def execute_deterministic_node(
        self,
        state: DAGState,
        deterministic_runner: Callable[
            [NodeExecutionRequest], NodeExecutionResult | dict[str, Any]
        ],
    ) -> DAGState:
        """Run exactly one deterministic node through an injected executor.

        Keeping source collection outside the orchestrator makes the no-compute
        and no-run-data constraints independently auditable.
        """
        request = self.build_request(state)
        if request.executor != "deterministic":
            raise ValueError(
                f"Node `{request.node_id}` requires `{request.executor}`, not a deterministic runner"
            )
        return self.accept_result(state, deterministic_runner(request))

    def _node(self, state: DAGState) -> NodeDefinition:
        try:
            return self.dag.nodes[state.current_node]
        except KeyError as exc:
            raise ValueError(f"Unknown current node `{state.current_node}`") from exc

    def _input_artifacts(self, node: NodeDefinition, state: DAGState) -> dict[str, dict[str, Any]]:
        inputs: dict[str, dict[str, Any]] = {}
        for name in node.inputs:
            if name == "plugin_name":
                inputs[name] = {"value": state.plugin_name}
            elif name == "repository_root":
                inputs[name] = {"value": state.repository_root}
            elif name not in state.artifacts:
                if node.executor == "human":
                    continue
                raise ValueError(f"Node `{node.node_id}` requires missing artifact `{name}`")
            else:
                inputs[name] = state.artifacts[name]
        return inputs

    def _render_prompt(self, node: NodeDefinition, inputs: dict[str, dict[str, Any]]) -> str | None:
        if node.executor not in {"agent", "hybrid"}:
            return None
        path = self.prompt_root / f"{node.node_id}.md"
        if not path.exists():
            raise ValueError(f"Missing prompt template for agent node `{node.node_id}`")
        body = path.read_text(encoding="utf-8").strip()
        input_blocks = "\n\n".join(
            f"<{name}>\n{yaml.safe_dump(value, allow_unicode=True, sort_keys=False).strip()}\n</{name}>"
            for name, value in inputs.items()
        )
        return f"{body}\n\n{input_blocks}\n"

    def _load_schema(self, schema_name: str | None) -> dict[str, Any] | None:
        if not schema_name:
            return None
        import json

        return json.loads(
            (self.schema_root / f"{schema_name}.schema.json").read_text(encoding="utf-8")
        )

    def _persist_state(self, state: DAGState) -> None:
        if self.artifact_store:
            self.artifact_store.save_state(state.plugin_name, asdict(state))

    def _persist_artifact(self, state: DAGState, name: str, artifact: dict[str, Any]) -> None:
        if self.artifact_store:
            self.artifact_store.save_artifact(state.plugin_name, name, artifact)


def _parse_node(node_id: str, raw: Any) -> NodeDefinition:
    if not isinstance(raw, dict):
        raise ValueError(f"Node `{node_id}` must be a mapping")
    output = raw.get("output") or {}
    if not isinstance(output, dict):
        raise ValueError(f"Node `{node_id}` output must be a mapping")
    inputs = raw.get("inputs", [])
    if isinstance(inputs, dict):
        inputs = list(inputs)
    return NodeDefinition(
        node_id=node_id,
        executor=_required_string(raw, "executor"),
        role=raw.get("role"),
        objective=_required_string(raw, "objective"),
        inputs=_string_list({"inputs": inputs}, "inputs"),
        instructions=_string_list(raw, "instructions"),
        constraints=_string_list(raw, "constraints"),
        acceptance=dict(raw.get("acceptance") or {}),
        output_artifact=output.get("artifact"),
        output_schema=output.get("schema"),
        output_path=output.get("path"),
        preconditions=_string_list(raw, "preconditions"),
        transitions={str(key): str(value) for key, value in (raw.get("transitions") or {}).items()},
    )


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expected non-empty string `{key}`")
    return value


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Expected integer `{key}`")
    return value


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Expected string list `{key}`")
    return value
