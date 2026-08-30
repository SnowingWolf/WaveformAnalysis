#!/usr/bin/env python3
"""Manage repository-local AgentTask records without executing agents or gates."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit('PyYAML is required; install with `pip install -e ".[dev]"`.') from exc


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = Path("docs/agents/index.yaml")
TASK_SCHEMA_PATH = Path("docs/agents/schema/agent-task.schema.json")
CURRENT_ROOT = Path("docs/agents/runs/current")
ARCHIVE_ROOT = Path("docs/agents/runs/archive")
TASK_FILENAME = "task.yaml"
API_VERSION = "waveform-analysis/agent-task/v1"
KIND = "AgentTask"
VALID_COSTS = {"light", "standard", "strict"}
VALID_SHAPES = {"direct", "compact", "staged"}
VALID_RISK_LEVELS = {"low", "medium", "high"}
VALID_STATES = {
    "created",
    "planning",
    "awaiting_user_input",
    "awaiting_approval",
    "ready_for_execution",
    "executing",
    "reviewing",
    "rework_required",
    "blocked",
    "completed",
    "failed",
    "cancelled",
}
TERMINAL_STATES = {"completed", "failed", "cancelled"}
READY_OR_LATER_STATES = {
    "ready_for_execution",
    "executing",
    "reviewing",
    "rework_required",
    "completed",
}
SHA1_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ARCHIVE_YEAR_RE = re.compile(r"^[0-9]{4}$")


class WorkflowError(ValueError):
    """A user-correctable record or command error."""


def _as_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError(f"{label} must be a mapping")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise WorkflowError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{path} must contain a mapping")
    return value


def _dump_yaml(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(dict(value), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _load_manifest(project_root: Path) -> dict[str, Any]:
    path = project_root / MANIFEST_PATH
    try:
        try:
            from scripts import render_agent_docs
        except ImportError:  # direct script execution
            import render_agent_docs
        if path == render_agent_docs.MANIFEST_PATH:
            return render_agent_docs._load_manifest(path)
    except (ImportError, AttributeError):
        pass
    return _load_yaml(path)


def _manifest_routes(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    routes = manifest.get("task_routes")
    if not isinstance(routes, list):
        raise WorkflowError("manifest task_routes must be a list")
    result = []
    for entry in routes:
        if not isinstance(entry, dict) or not isinstance(entry.get("task"), str):
            raise WorkflowError("manifest task_routes contains an invalid entry")
        result.append(entry)
    return result


def _route_map(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["task"]: entry for entry in _manifest_routes(manifest)}


def resolve_route(manifest: Mapping[str, Any], name: str) -> tuple[dict[str, Any], bool]:
    routes = _route_map(manifest)
    current = name
    seen: set[str] = set()
    was_alias = False
    while True:
        if current in seen:
            raise WorkflowError(f"route alias cycle detected at `{current}`")
        seen.add(current)
        route = routes.get(current)
        if route is None:
            raise WorkflowError(f"unknown route: {name}")
        alias_of = route.get("alias_of")
        if alias_of is None:
            return route, was_alias
        if not isinstance(alias_of, str) or not alias_of:
            raise WorkflowError(f"route alias `{current}` has invalid alias_of")
        was_alias = True
        current = alias_of


def _route_aliases(manifest: Mapping[str, Any], canonical: Mapping[str, Any]) -> list[str]:
    names = [x for x in canonical.get("aliases", []) if isinstance(x, str)]
    for route in _manifest_routes(manifest):
        if route.get("alias_of") == canonical.get("task") and route.get("task") not in names:
            names.append(str(route["task"]))
    return names


def _default_shape(manifest: Mapping[str, Any], cost: str) -> str:
    contract = manifest.get("workflow_shape_contract")
    defaults = contract.get("default_by_workflow_cost") if isinstance(contract, dict) else None
    if isinstance(defaults, dict) and isinstance(defaults.get(cost), str):
        return defaults[cost]
    return "compact" if cost == "light" else "staged"


def _allowed_shapes(manifest: Mapping[str, Any], cost: str) -> set[str]:
    contract = manifest.get("workflow_shape_contract")
    allowed = contract.get("allowed_by_workflow_cost") if isinstance(contract, dict) else None
    if isinstance(allowed, dict) and isinstance(allowed.get(cost), list):
        return {x for x in allowed[cost] if isinstance(x, str)}
    return {"direct", "compact", "staged"} if cost == "light" else {"staged"}


def _cost_rank(cost: str) -> int:
    return {"light": 0, "standard": 1, "strict": 2}[cost]


def _route_executor_role(route: Mapping[str, Any]) -> str:
    owner = route.get("rework_owner_default")
    if isinstance(owner, str) and owner.startswith("executor."):
        return owner
    handoff = route.get("handoff_sequence")
    if isinstance(handoff, list):
        for role in handoff:
            if isinstance(role, str) and role.startswith("executor."):
                return role
    return "executor.code"


def _route_gates(route: Mapping[str, Any]) -> list[str]:
    gates = route.get("blocking_gates", [])
    return [x for x in gates if isinstance(x, str) and x.strip()] if isinstance(gates, list) else []


def _validate_task_id(task_id: str) -> str:
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        raise WorkflowError(
            "task id must contain only letters, digits, '.', '_' or '-' and cannot be empty"
        )
    return task_id


def _validate_archive_year(year: str) -> str:
    if not isinstance(year, str) or not ARCHIVE_YEAR_RE.fullmatch(year):
        raise WorkflowError("archive year must be a four-digit year")
    return year


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _managed_root(project_root: Path, relative_root: Path) -> Path:
    """Resolve a managed task root without following it outside the repository."""

    repository_root = project_root.resolve()
    root = (repository_root / relative_root).resolve()
    if not _is_within(root, repository_root):
        raise WorkflowError(f"managed task root escapes the repository: {relative_root}")
    return root


def _safe_managed_task_path(
    candidate: Path,
    roots: Iterable[Path],
    *,
    require_exists: bool,
) -> Path:
    """Return a regular task path whose resolved target stays in ``roots``.

    Task records are stateful control data.  Refusing symlinks avoids reading a
    record outside the managed tree and avoids moving a link whose target could
    change independently of the record being archived.
    """

    if candidate.is_symlink():
        raise WorkflowError(f"task path must not be a symlink: {candidate}")
    resolved = candidate.resolve(strict=False)
    if resolved.name != TASK_FILENAME or not any(_is_within(resolved, root) for root in roots):
        raise WorkflowError("task path must remain below the managed current/archive roots")
    if require_exists and not resolved.is_file():
        raise WorkflowError(f"task file does not exist: {candidate}")
    return resolved


def _task_path(task_ref: str, project_root: Path, *, allow_archive: bool = True) -> Path:
    project_root = project_root.resolve()
    current_root = _managed_root(project_root, CURRENT_ROOT)
    archive_root = _managed_root(project_root, ARCHIVE_ROOT)
    task_ref = os.fspath(task_ref)
    if "/" not in task_ref and "\\" not in task_ref and not task_ref.endswith(".yaml"):
        task_id = _validate_task_id(task_ref)
        current = current_root / task_id / TASK_FILENAME
        if current.exists() or not allow_archive:
            return _safe_managed_task_path(current, (current_root,), require_exists=False)
        candidates = sorted(archive_root.glob(f"*/{task_id}/{TASK_FILENAME}"))
        for candidate in candidates:
            if not ARCHIVE_YEAR_RE.fullmatch(candidate.parent.parent.name):
                continue
            try:
                return _safe_managed_task_path(candidate, (archive_root,), require_exists=True)
            except WorkflowError:
                continue
        return _safe_managed_task_path(current, (current_root,), require_exists=False)
    candidate = Path(task_ref)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    roots = (current_root,) + ((archive_root,) if allow_archive else ())
    return _safe_managed_task_path(candidate, roots, require_exists=True)


def _all_task_paths(project_root: Path) -> list[Path]:
    paths: set[Path] = set()
    for root in (
        _managed_root(project_root, CURRENT_ROOT),
        _managed_root(project_root, ARCHIVE_ROOT),
    ):
        if root.exists():
            for candidate in root.rglob(TASK_FILENAME):
                if candidate.is_symlink():
                    continue
                try:
                    safe = _safe_managed_task_path(candidate, (root,), require_exists=True)
                except WorkflowError:
                    continue
                paths.add(safe)
    return sorted(paths)


def _repository_relative_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return "must be a non-empty string"
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        return "must be repository-relative, not absolute"
    if "\x00" in normalized:
        return "must not contain NUL"
    if any(part == ".." for part in normalized.split("/")):
        return "must not contain `..` path segments"
    return None


def _valid_sha(value: Any, pattern: re.Pattern[str], label: str) -> str | None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        return f"{label} must be a full hexadecimal SHA"
    return None


def canonical_spec_json(spec: Mapping[str, Any]) -> str:
    return json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_spec_sha256(spec: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_spec_json(spec).encode("utf-8")).hexdigest()


def _load_json_schema_validator(project_root: Path) -> Any:
    """Load the checked-in AgentTask schema for strict validation.

    Strict validation is deliberately fail-closed.  The schema is a repository
    contract, so silently falling back to the hand-written checks when the
    ``jsonschema`` dependency is unavailable would make CI report a false
    success.
    """

    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise WorkflowError(
            "jsonschema is required for `validate --strict`; "
            "install it with `pip install jsonschema` or the project dev extras."
        ) from exc

    schema_path = project_root / TASK_SCHEMA_PATH
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise WorkflowError(f"cannot read AgentTask JSON Schema: {schema_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"AgentTask JSON Schema is invalid JSON: {schema_path}: {exc}") from exc

    try:
        validator_class = jsonschema.validators.validator_for(schema)
        validator_class.check_schema(schema)
        return validator_class(schema)
    except (AttributeError, TypeError, jsonschema.exceptions.SchemaError) as exc:
        raise WorkflowError(f"AgentTask JSON Schema is invalid: {schema_path}: {exc}") from exc


def _schema_error_path(error: Any) -> str:
    path = "task"
    for part in error.absolute_path:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def _validate_json_schema(
    task: Mapping[str, Any], *, project_root: Path, validator: Any | None = None
) -> list[str]:
    validator = validator or _load_json_schema_validator(project_root)
    errors = sorted(
        validator.iter_errors(task),
        key=lambda error: (tuple(str(part) for part in error.absolute_path), error.message),
    )
    return [
        f"JSON Schema violation at {_schema_error_path(error)}: {error.message}" for error in errors
    ]


def _validate_manifest(project_root: Path, manifest: Mapping[str, Any]) -> list[str]:
    """Validate v6 additions and reuse the established manifest validator."""
    issues: list[str] = []
    if manifest.get("version") != 6:
        issues.append("manifest version must be 6")
    try:
        try:
            from scripts import render_agent_docs
        except ImportError:  # direct script execution
            import render_agent_docs
        issues.extend(render_agent_docs.validate_manifest(dict(manifest), project_root))
    except (ImportError, AttributeError, ValueError, TypeError) as exc:
        issues.append(f"manifest parser error: {exc}")
    roles = manifest.get("agent_roles")
    role_ids = {
        entry.get("id")
        for entry in (roles or [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    if "executor.code" not in role_ids:
        issues.append("manifest must declare agent role `executor.code`")
    routes = _route_map(manifest) if isinstance(manifest.get("task_routes"), list) else {}
    modify_code = routes.get("modify_code")
    if modify_code is None:
        issues.append("manifest must declare canonical route `modify_code`")
    else:
        if modify_code.get("workflow_cost") != "standard":
            issues.append("route `modify_code` workflow_cost must be standard")
        if modify_code.get("workflow_mode") != "shape_driven":
            issues.append("route `modify_code` workflow_mode must be shape_driven")
        if _route_executor_role(modify_code) != "executor.code":
            issues.append("route `modify_code` must hand off to executor.code")
        if set(modify_code.get("aliases", [])) != {"modify_context", "refactor"}:
            issues.append("route `modify_code` aliases must be exactly modify_context and refactor")
    for alias in ("modify_context", "refactor"):
        if routes.get(alias, {}).get("alias_of") != "modify_code":
            issues.append(f"route `{alias}` must alias canonical route `modify_code`")
    return issues


def validate_manifest(manifest: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> list[str]:
    """Public manifest validation API used by tests and CI wrappers."""
    return _validate_manifest(project_root, manifest)


def _string_list(value: Any, label: str, issues: list[str]) -> None:
    if not isinstance(value, list):
        issues.append(f"{label} must be a list")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            issues.append(f"{label}[{index}] must be a non-empty string")


def _validate_approval(
    approval: Any, plan_sha: str | None, spec_sha: str, issues: list[str]
) -> None:
    if not isinstance(approval, dict):
        issues.append("status.approval must be a mapping")
        return
    if not approval:
        return
    evidence = approval.get("evidence", approval.get("approval_evidence"))
    if evidence is None:
        issues.append("status.approval must include evidence")
    bound = approval.get("plan_sha256", approval.get("spec_sha256"))
    if bound is None:
        issues.append("status.approval evidence must include plan_sha256")
    elif not isinstance(bound, str) or bound != (plan_sha or spec_sha):
        issues.append("status.approval evidence is not bound to current plan_sha256")
    if isinstance(evidence, list):
        for index, item in enumerate(evidence):
            if isinstance(item, dict):
                item_sha = item.get("plan_sha256", item.get("spec_sha256"))
                if item_sha is not None and item_sha != (plan_sha or spec_sha):
                    issues.append(f"status.approval.evidence[{index}] has a stale plan_sha256")
    elif isinstance(evidence, dict):
        item_sha = evidence.get("plan_sha256", evidence.get("spec_sha256"))
        if item_sha is not None and item_sha != (plan_sha or spec_sha):
            issues.append("status.approval.evidence has a stale plan_sha256")


EXECUTION_EVIDENCE_FIELDS = frozenset(
    {
        "evidence",
        "execution_report",
        "task_report",
        "report",
        "summary",
        "result",
        "results",
        "verification",
        "actions_taken",
        "commands_run",
        "command_results",
        "changed_paths",
        "actual_changes",
        "artifact",
    }
)


def _value_is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value) and any(_value_is_present(item) for item in value.values())
    if isinstance(value, list | tuple | set):
        return bool(value) and any(_value_is_present(item) for item in value)
    if isinstance(value, bool):
        return value
    return True


def _has_execution_evidence(execution: Any) -> bool:
    if not isinstance(execution, Mapping):
        return False
    return any(
        field in execution and _value_is_present(execution[field])
        for field in EXECUTION_EVIDENCE_FIELDS
    )


def _nested_record_value(record: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in record and _value_is_present(record[key]):
            return record[key]
    for nested_key in ("review_report", "evidence"):
        nested = record.get(nested_key)
        if isinstance(nested, Mapping):
            value = _nested_record_value(nested, keys)
            if _value_is_present(value):
                return value
    return None


def _review_plan_sha(review: Mapping[str, Any]) -> Any:
    return _nested_record_value(review, ("plan_sha256", "spec_sha256"))


def _gate_statuses(gate_results: Any) -> dict[str, list[str]]:
    statuses: dict[str, list[str]] = {}

    def add(name: Any, status: Any) -> None:
        if not isinstance(name, str) or not name.strip():
            return
        if not isinstance(status, str) or not status.strip():
            return
        statuses.setdefault(name.strip(), []).append(status.strip().upper())

    if isinstance(gate_results, Mapping):
        for name, result in gate_results.items():
            if isinstance(result, Mapping):
                result = result.get("status", result.get("result", result.get("state")))
            add(name, result)
    elif isinstance(gate_results, list):
        for item in gate_results:
            if isinstance(item, Mapping):
                name = item.get("gate", item.get("name", item.get("id")))
                status = item.get("status", item.get("result", item.get("state")))
                add(name, status)
            elif isinstance(item, str):
                match = re.match(
                    r"^\s*(?P<name>.+?)\s*(?::|=|->|\s+)\s*(?P<status>PASS|FAIL)\s*$",
                    item,
                    re.IGNORECASE,
                )
                if match:
                    add(match.group("name"), match.group("status"))
    return statuses


def _validate_completion_evidence(
    spec: Mapping[str, Any], status: Mapping[str, Any], issues: list[str]
) -> None:
    shape = spec.get("workflow_shape")
    state = status.get("state")
    execution = status.get("execution")

    if shape == "staged" and state in {"reviewing", "completed"}:
        if not _has_execution_evidence(execution):
            issues.append("staged task requires execution evidence before reviewing/completed")

    if shape == "compact" and state == "completed" and not _has_execution_evidence(execution):
        issues.append("compact task requires execution/task report evidence before completed")

    if shape != "staged" or state != "completed":
        return

    review = status.get("review")
    if not isinstance(review, Mapping) or not review:
        issues.append("staged task requires review evidence before completed")
        return

    reviewer = _nested_record_value(review, ("reviewer_actor", "reviewer", "actor"))
    if not isinstance(reviewer, str) or not reviewer.strip():
        issues.append("staged task review requires a non-empty reviewer actor")

    decision = _nested_record_value(review, ("decision",))
    if not isinstance(decision, str) or decision.strip().lower() not in {
        "approved",
        "completed",
    }:
        issues.append("staged task review decision must be completed/approved")

    plan_sha = status.get("plan_sha256")
    bound_sha = _review_plan_sha(review)
    if not isinstance(plan_sha, str) or not SHA256_RE.fullmatch(plan_sha):
        issues.append("staged task review requires the current status.plan_sha256")
    elif bound_sha != plan_sha:
        issues.append("staged task review plan_sha256 must bind the current status.plan_sha256")

    required_gates = spec.get("required_gates")
    if not isinstance(required_gates, list):
        return
    gate_results = _nested_record_value(review, ("gate_results", "gates"))
    statuses = _gate_statuses(gate_results)
    for gate in required_gates:
        if not isinstance(gate, str) or not gate.strip():
            continue
        gate_name = gate.strip()
        observed = statuses.get(gate_name, [])
        if not observed or any(result != "PASS" for result in observed):
            issues.append(f"required gate `{gate_name}` must have a PASS result before completed")

    transitions = status.get("transitions")
    final_transition = transitions[-1] if isinstance(transitions, list) and transitions else None
    assignment = spec.get("assignment")
    reviewer_role = assignment.get("reviewer_role") if isinstance(assignment, Mapping) else None
    allowed_actors = {"reviewer"}
    if isinstance(reviewer_role, str) and reviewer_role.strip():
        allowed_actors.add(reviewer_role.strip())
    transition_actor = (
        final_transition.get("actor") if isinstance(final_transition, Mapping) else None
    )
    if transition_actor not in allowed_actors:
        expected = " or ".join(sorted(allowed_actors))
        issues.append(
            "staged reviewing -> completed transition requires reviewer actor " f"({expected})"
        )


def _lifecycle_transitions(manifest: Mapping[str, Any]) -> set[tuple[str, str]]:
    lifecycle = manifest.get("lifecycle")
    entries = lifecycle.get("transitions", []) if isinstance(lifecycle, dict) else []
    result: set[tuple[str, str]] = set()
    if isinstance(entries, list):
        for entry in entries:
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("from"), str)
                and isinstance(entry.get("to"), str)
            ):
                result.add((entry["from"], entry["to"]))
    if result:
        return result
    return {
        ("created", "planning"),
        ("created", "executing"),
        ("created", "completed"),
        ("planning", "awaiting_user_input"),
        ("planning", "awaiting_approval"),
        ("planning", "ready_for_execution"),
        ("planning", "blocked"),
        ("planning", "cancelled"),
        ("awaiting_user_input", "planning"),
        ("awaiting_approval", "ready_for_execution"),
        ("awaiting_approval", "blocked"),
        ("awaiting_approval", "cancelled"),
        ("ready_for_execution", "executing"),
        ("executing", "reviewing"),
        ("executing", "completed"),
        ("executing", "blocked"),
        ("executing", "failed"),
        ("executing", "cancelled"),
        ("reviewing", "completed"),
        ("reviewing", "rework_required"),
        ("reviewing", "blocked"),
        ("reviewing", "failed"),
        ("reviewing", "cancelled"),
        ("rework_required", "executing"),
        ("rework_required", "planning"),
        ("blocked", "planning"),
        ("blocked", "executing"),
        ("blocked", "cancelled"),
    }


def validate_task(
    task: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    task_path: Path | None = None,
    project_root: Path = PROJECT_ROOT,
    strict: bool = False,
    _schema_validator: Any | None = None,
) -> list[str]:
    """Return structural, route, lifecycle, scope, and digest issues."""
    issues: list[str] = []
    if task.get("api_version") != API_VERSION:
        issues.append(f"api_version must be {API_VERSION}")
    if task.get("kind") != KIND:
        issues.append("kind must be AgentTask")

    metadata = task.get("metadata")
    if not isinstance(metadata, dict):
        issues.append("metadata must be a mapping")
        metadata = {}
    for key in ("id", "generation", "created_at", "updated_at"):
        if key not in metadata:
            issues.append(f"metadata missing {key}")
    task_id = metadata.get("id")
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        issues.append("metadata.id is not a valid task id")
    generation = metadata.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        issues.append("metadata.generation must be a positive integer")
    for key in ("created_at", "updated_at"):
        if key in metadata and (not isinstance(metadata[key], str) or not metadata[key].strip()):
            issues.append(f"metadata.{key} must be a non-empty string")

    if task_path is not None:
        current_root = project_root / CURRENT_ROOT
        archive_root = project_root / ARCHIVE_ROOT
        if task_path.name != TASK_FILENAME or not (
            _is_within(task_path, current_root) or _is_within(task_path, archive_root)
        ):
            issues.append("task path is outside the managed current/archive roots")
        else:
            if isinstance(task_id, str) and task_path.parent.name != task_id:
                issues.append("task directory must match metadata.id")
            if _is_within(task_path, archive_root) and not ARCHIVE_YEAR_RE.fullmatch(
                task_path.parent.parent.name
            ):
                issues.append("archived task must be below archive/<YYYY>/<id>/task.yaml")

    spec = task.get("spec")
    if not isinstance(spec, dict):
        issues.append("spec must be a mapping")
        spec = {}
    required_spec = (
        "goal",
        "route",
        "workflow_cost",
        "workflow_shape",
        "risk_level",
        "scope",
        "acceptance_criteria",
        "required_gates",
        "assignment",
    )
    for key in required_spec:
        if key not in spec:
            issues.append(f"spec missing {key}")
    for key in ("goal", "route"):
        if key in spec and (not isinstance(spec[key], str) or not spec[key].strip()):
            issues.append(f"spec.{key} must be a non-empty string")
    route: dict[str, Any] | None = None
    if isinstance(spec.get("route"), str):
        try:
            route, _ = resolve_route(manifest, spec["route"])
        except WorkflowError as exc:
            issues.append(str(exc))
    cost = spec.get("workflow_cost")
    if cost not in VALID_COSTS:
        issues.append("spec.workflow_cost must be light, standard, or strict")
    shape = spec.get("workflow_shape")
    if shape not in VALID_SHAPES:
        issues.append("spec.workflow_shape must be direct, compact, or staged")
    elif cost in VALID_COSTS and shape not in _allowed_shapes(manifest, cost):
        issues.append(f"workflow_shape `{shape}` is not allowed for workflow_cost `{cost}`")
    if route is not None and cost in VALID_COSTS:
        route_cost = route.get("workflow_cost")
        if route_cost in VALID_COSTS and _cost_rank(cost) < _cost_rank(route_cost):
            issues.append(
                f"workflow_cost `{cost}` cannot be lower than route `{route.get('task')}` default `{route_cost}`"
            )
    if spec.get("risk_level") not in VALID_RISK_LEVELS:
        issues.append("spec.risk_level must be low, medium, or high")
    _string_list(spec.get("acceptance_criteria"), "spec.acceptance_criteria", issues)
    _string_list(spec.get("required_gates"), "spec.required_gates", issues)
    if not isinstance(spec.get("assignment"), dict):
        issues.append("spec.assignment must be a mapping")

    scope = spec.get("scope")
    if not isinstance(scope, dict):
        issues.append("spec.scope must be a mapping")
        scope = {}
    if sha_issue := _valid_sha(scope.get("base_sha"), SHA1_RE, "spec.scope.base_sha"):
        issues.append(sha_issue)
    allowed_paths = scope.get("allowed_paths")
    if not isinstance(allowed_paths, list):
        issues.append("spec.scope.allowed_paths must be a list")
    elif not allowed_paths:
        issues.append("spec.scope.allowed_paths must contain at least one path")
    else:
        for index, value in enumerate(allowed_paths):
            if path_issue := _repository_relative_path(value):
                issues.append(f"spec.scope.allowed_paths[{index}] {path_issue}")

    status = task.get("status")
    if not isinstance(status, dict):
        issues.append("status must be a mapping")
        status = {}
    required_status = (
        "state",
        "transitions",
        "plan_sha256",
        "execution",
        "review",
        "approval",
        "handoff",
    )
    for key in required_status:
        if key not in status:
            issues.append(f"status missing {key}")
    state = status.get("state")
    if state not in VALID_STATES:
        issues.append(f"status.state must be one of {sorted(VALID_STATES)}")
    transitions = status.get("transitions")
    if not isinstance(transitions, list):
        issues.append("status.transitions must be a list")
        transitions = []
    allowed_transitions = _lifecycle_transitions(manifest)
    replay_state = "created"
    for index, entry in enumerate(transitions):
        if not isinstance(entry, dict):
            issues.append(f"status.transitions[{index}] must be a mapping")
            continue
        if entry.get("from") is not None and entry.get("from") != replay_state:
            issues.append(f"status.transitions[{index}].from does not match lifecycle history")
        entry_at = entry.get("at")
        if not isinstance(entry_at, str) or not entry_at.strip():
            issues.append(f"status.transitions[{index}].at must be a non-empty string")
        entry_to = entry.get("to")
        if entry_to not in VALID_STATES:
            issues.append(f"status.transitions[{index}].to is not a valid state")
            continue
        if (replay_state, entry_to) not in allowed_transitions:
            issues.append(f"invalid lifecycle transition: {replay_state} -> {entry_to}")
        if (
            replay_state == "rework_required"
            and entry_to == "planning"
            and entry.get("scope_changed") is not True
        ):
            issues.append("rework_required -> planning requires scope_changed=true")
        replay_state = entry_to
    if state in VALID_STATES and replay_state != state:
        issues.append("status.state does not match the last transition")

    plan_sha = status.get("plan_sha256")
    if plan_sha is not None and (
        not isinstance(plan_sha, str) or not SHA256_RE.fullmatch(plan_sha)
    ):
        issues.append("status.plan_sha256 must be null or a 64-character hexadecimal SHA")
    spec_sha = canonical_spec_sha256(spec)
    if isinstance(plan_sha, str) and SHA256_RE.fullmatch(plan_sha) and plan_sha != spec_sha:
        issues.append("status.plan_sha256 does not match the current canonical spec")
    if state in READY_OR_LATER_STATES and plan_sha is None:
        issues.append(f"status.plan_sha256 is required in state `{state}`")
    for key in ("execution", "review", "approval", "handoff"):
        if not isinstance(status.get(key), dict):
            issues.append(f"status.{key} must be a mapping")
    _validate_approval(status.get("approval"), plan_sha, spec_sha, issues)
    if route is not None and isinstance(spec.get("assignment"), dict):
        executor_role = spec["assignment"].get("executor_role", spec["assignment"].get("executor"))
        expected_role = _route_executor_role(route)
        if executor_role is not None and executor_role != expected_role:
            issues.append(
                f"spec.assignment executor role `{executor_role}` does not match route role `{expected_role}`"
            )
    _validate_completion_evidence(spec, status, issues)
    if strict:
        issues.extend(
            _validate_json_schema(
                task,
                project_root=project_root,
                validator=_schema_validator,
            )
        )
    return issues


def _parse_json_mapping(raw: str | None, label: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{label} must decode to a JSON object")
    return value


def _approval_value(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _resolve_task_id_argument(task_id: str | None, option_id: str | None) -> str:
    value = option_id or task_id
    if not value:
        raise WorkflowError("an id is required")
    return _validate_task_id(value)


def _git_head(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise WorkflowError("cannot determine git HEAD; pass --base-sha explicitly") from exc
    return result.stdout.strip()


def init_task(args: argparse.Namespace, project_root: Path) -> Path:
    manifest = _load_manifest(project_root)
    manifest_issues = _validate_manifest(project_root, manifest)
    if manifest_issues:
        raise WorkflowError("manifest is invalid:\n" + "\n".join(f"- {x}" for x in manifest_issues))
    task_id = _resolve_task_id_argument(args.task_id, args.id)
    path = project_root / CURRENT_ROOT / task_id / TASK_FILENAME
    if path.exists():
        raise WorkflowError(f"task already exists: {path}")
    route, _ = resolve_route(manifest, args.route)
    route_cost = route.get("workflow_cost")
    cost = args.workflow_cost or route_cost
    if cost not in VALID_COSTS:
        raise WorkflowError("workflow cost must be light, standard, or strict")
    if route_cost in VALID_COSTS and _cost_rank(cost) < _cost_rank(route_cost):
        raise WorkflowError(f"workflow cost cannot be lower than route default `{route_cost}`")
    shape = args.workflow_shape or _default_shape(manifest, cost)
    if shape not in _allowed_shapes(manifest, cost):
        raise WorkflowError(f"workflow shape `{shape}` is not allowed for workflow cost `{cost}`")
    base_sha = args.base_sha or _git_head(project_root)
    if issue := _valid_sha(base_sha, SHA1_RE, "base_sha"):
        raise WorkflowError(issue)
    allowed_paths = args.allowed_path or []
    if not allowed_paths:
        raise WorkflowError("scope requires at least one --allowed-path")
    path_issues = []
    for index, value in enumerate(allowed_paths):
        if issue := _repository_relative_path(value):
            path_issues.append(f"allowed_paths[{index}] {issue}")
    if path_issues:
        raise WorkflowError("invalid scope:\n" + "\n".join(path_issues))
    now = _now()
    task: dict[str, Any] = {
        "api_version": API_VERSION,
        "kind": KIND,
        "metadata": {"id": task_id, "generation": 1, "created_at": now, "updated_at": now},
        "spec": {
            "goal": args.goal,
            "route": route["task"],
            "workflow_cost": cost,
            "workflow_shape": shape,
            "risk_level": args.risk_level,
            "scope": {"base_sha": base_sha.lower(), "allowed_paths": allowed_paths},
            "acceptance_criteria": args.acceptance_criteria or [],
            "required_gates": args.required_gate or _route_gates(route),
            "assignment": {
                "planner_role": "planner",
                "executor_role": _route_executor_role(route),
                "reviewer_role": "reviewer",
            },
        },
        "status": {
            "state": "created",
            "transitions": [],
            "plan_sha256": None,
            "execution": {},
            "review": {},
            "approval": {},
            "handoff": {},
        },
    }
    issues = validate_task(task, manifest=manifest, task_path=path, project_root=project_root)
    if issues:
        raise WorkflowError("new task is invalid:\n" + "\n".join(f"- {x}" for x in issues))
    _dump_yaml(path, task)
    return path


def _default_actor(current: str) -> str:
    if current == "reviewing":
        return "reviewer"
    if current in {"planning", "awaiting_user_input", "awaiting_approval", "ready_for_execution"}:
        return "planner"
    if current in {"executing", "blocked", "rework_required"}:
        return "executor"
    return "system"


def transition_task(args: argparse.Namespace, project_root: Path) -> Path:
    manifest = _load_manifest(project_root)
    manifest_issues = _validate_manifest(project_root, manifest)
    if manifest_issues:
        raise WorkflowError("manifest is invalid:\n" + "\n".join(f"- {x}" for x in manifest_issues))
    path = _task_path(args.task_id, project_root, allow_archive=False)
    task = _load_yaml(path)
    current_status = task.get("status") if isinstance(task.get("status"), dict) else {}
    current = current_status.get("state")
    target = args.to_state or args.to_option
    if current not in VALID_STATES:
        raise WorkflowError("current task has an invalid status.state")
    if target not in VALID_STATES:
        raise WorkflowError(f"target state must be one of {sorted(VALID_STATES)}")
    if (current, target) not in _lifecycle_transitions(manifest):
        raise WorkflowError(f"invalid lifecycle transition: {current} -> {target}")
    scope_changed = bool(args.scope_changed)
    if scope_changed and (current, target) != ("rework_required", "planning"):
        raise WorkflowError("scope_changed is only valid for rework_required -> planning")
    if (current, target) == ("rework_required", "planning") and not scope_changed:
        raise WorkflowError("rework_required -> planning requires --scope-changed")
    if current == "rework_required" and target == "executing" and scope_changed:
        raise WorkflowError("scope_changed rework must return to planning")
    spec = _as_mapping(task.get("spec"), "spec")
    shape = spec.get("workflow_shape")
    if (current, target) == ("created", "completed") and shape != "direct":
        raise WorkflowError("created -> completed is only valid for direct workflow_shape")
    if (current, target) == ("created", "executing") and shape != "compact":
        raise WorkflowError("created -> executing is only valid for compact workflow_shape")
    if (current, target) == ("executing", "completed") and shape != "compact":
        raise WorkflowError("executing -> completed is only valid for compact workflow_shape")
    if (current, target) == ("reviewing", "completed"):
        assignment = spec.get("assignment")
        reviewer_role = assignment.get("reviewer_role") if isinstance(assignment, Mapping) else None
        allowed_actors = {"reviewer"}
        if isinstance(reviewer_role, str) and reviewer_role.strip():
            allowed_actors.add(reviewer_role.strip())
        transition_actor = args.actor or _default_actor(current)
        if transition_actor not in allowed_actors:
            expected = " or ".join(sorted(allowed_actors))
            raise WorkflowError(
                "reviewing -> completed requires reviewer actor "
                f"({expected}); got `{transition_actor}`"
            )

    issues = validate_task(task, manifest=manifest, task_path=path, project_root=project_root)
    ignored_on_replan = {
        "status.plan_sha256 does not match the current canonical spec",
        "status.approval must include evidence",
        "status.approval evidence must include plan_sha256",
        "status.approval evidence is not bound to current plan_sha256",
    }
    only_replan_issues = all(
        x in ignored_on_replan or x.startswith("status.approval.evidence[") for x in issues
    )
    if issues and not (scope_changed and only_replan_issues):
        raise WorkflowError("task is invalid:\n" + "\n".join(f"- {x}" for x in issues))

    status = _as_mapping(task["status"], "status")
    if scope_changed:
        metadata = _as_mapping(task["metadata"], "metadata")
        metadata["generation"] = int(metadata["generation"]) + 1
        for key in ("plan_sha256", "execution", "review", "approval", "handoff"):
            status[key] = None if key == "plan_sha256" else {}
    spec_digest = canonical_spec_sha256(spec)
    if (
        target in {"executing", "completed", "awaiting_approval", "ready_for_execution"}
        and status.get("plan_sha256") is None
    ):
        status["plan_sha256"] = spec_digest
    if target == "ready_for_execution":
        status["plan_sha256"] = spec_digest
        approval = status.get("approval")
        if current == "awaiting_approval":
            if args.approval_json is not None:
                status["approval"] = _parse_json_mapping(args.approval_json, "--approval-json")
                approval = status["approval"]
            elif args.approval_evidence is not None:
                evidence = _approval_value(args.approval_evidence)
                status["approval"] = {
                    "evidence": evidence if isinstance(evidence, list) else [evidence],
                    "plan_sha256": spec_digest,
                    "approved_at": _now(),
                    "actor": args.actor or "approver",
                }
                approval = status["approval"]
            if not isinstance(approval, dict) or not approval.get("evidence"):
                raise WorkflowError(
                    "awaiting_approval -> ready_for_execution requires approval evidence"
                )
            if approval.get("plan_sha256", approval.get("spec_sha256")) != spec_digest:
                raise WorkflowError("approval evidence must bind current plan_sha256")
        elif args.approval_json is not None or args.approval_evidence is not None:
            if args.approval_json is not None:
                status["approval"] = _parse_json_mapping(args.approval_json, "--approval-json")
            else:
                evidence = _approval_value(args.approval_evidence)
                status["approval"] = {
                    "evidence": evidence if isinstance(evidence, list) else [evidence],
                    "plan_sha256": spec_digest,
                    "approved_at": _now(),
                    "actor": args.actor or "approver",
                }
    if args.execution_json is not None:
        status["execution"] = _parse_json_mapping(args.execution_json, "--execution-json") or {}
    if args.review_json is not None:
        status["review"] = _parse_json_mapping(args.review_json, "--review-json") or {}
    if args.handoff_json is not None:
        status["handoff"] = _parse_json_mapping(args.handoff_json, "--handoff-json") or {}
    history = status.get("transitions")
    if not isinstance(history, list):
        raise WorkflowError("status.transitions must be a list")
    event: dict[str, Any] = {
        "from": current,
        "to": target,
        "at": _now(),
        "actor": args.actor or _default_actor(current),
    }
    if args.condition:
        event["condition"] = args.condition
    if scope_changed:
        event["scope_changed"] = True
    history.append(event)
    status["state"] = target
    _as_mapping(task["metadata"], "metadata")["updated_at"] = event["at"]
    final_issues = validate_task(task, manifest=manifest, task_path=path, project_root=project_root)
    if final_issues:
        raise WorkflowError(
            "transition would produce an invalid task:\n"
            + "\n".join(f"- {x}" for x in final_issues)
        )
    _dump_yaml(path, task)
    return path


def validate_paths(
    paths: Iterable[Path], project_root: Path, *, strict: bool
) -> list[tuple[Path, list[str]]]:
    manifest = _load_manifest(project_root)
    manifest_issues = _validate_manifest(project_root, manifest)
    schema_validator = _load_json_schema_validator(project_root) if strict else None
    results: list[tuple[Path, list[str]]] = []
    if manifest_issues:
        results.append((project_root / MANIFEST_PATH, manifest_issues))
    for path in paths:
        try:
            task = _load_yaml(path)
            issues = validate_task(
                task,
                manifest=manifest,
                task_path=path,
                project_root=project_root,
                strict=strict,
                _schema_validator=schema_validator,
            )
        except WorkflowError as exc:
            issues = [str(exc)]
        results.append((path, issues))
    return results


def _archive_destination(project_root: Path, year: str, task_id: str) -> Path:
    """Build an archive destination while rejecting symlinked path components."""

    repository_root = project_root.resolve()
    archive_root = _managed_root(repository_root, ARCHIVE_ROOT)
    destination = archive_root / year / task_id / TASK_FILENAME
    if not _is_within(destination, archive_root):
        raise WorkflowError("archive destination escapes the archive root")

    relative_parts = destination.relative_to(archive_root).parts
    cursor = archive_root
    for part in relative_parts[:-1]:
        cursor /= part
        if cursor.is_symlink():
            raise WorkflowError(f"archive destination contains a symlink: {cursor}")
        if cursor.exists() and not cursor.is_dir():
            raise WorkflowError(f"archive destination parent is not a directory: {cursor}")
        if not _is_within(cursor, archive_root):
            raise WorkflowError("archive destination parent escapes the archive root")

    if destination.is_symlink() or os.path.lexists(destination):
        raise WorkflowError(f"archive destination already exists: {destination}")
    return destination


def archive_task(args: argparse.Namespace, project_root: Path) -> Path:
    manifest = _load_manifest(project_root)
    manifest_issues = _validate_manifest(project_root, manifest)
    if manifest_issues:
        raise WorkflowError("manifest is invalid:\n" + "\n".join(f"- {x}" for x in manifest_issues))
    source = _task_path(args.task_id, project_root, allow_archive=False)
    task = _load_yaml(source)
    issues = validate_task(
        task, manifest=manifest, task_path=source, project_root=project_root, strict=True
    )
    if issues:
        raise WorkflowError("cannot archive invalid task:\n" + "\n".join(f"- {x}" for x in issues))
    status = task.get("status")
    state = status.get("state") if isinstance(status, dict) else None
    if state not in TERMINAL_STATES:
        raise WorkflowError("only completed, failed, or cancelled tasks can be archived")
    year = _validate_archive_year(args.year or datetime.now(timezone.utc).strftime("%Y"))
    task_id = task["metadata"]["id"]
    destination = _archive_destination(project_root, year, task_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Re-check after creating parents so a pre-existing or raced symlink cannot
    # redirect the move outside the archive root.
    destination = _archive_destination(project_root, year, task_id)
    shutil.move(str(source), str(destination))
    try:
        source.parent.rmdir()
    except OSError:
        pass
    return destination


def route_info(manifest: Mapping[str, Any], route_name: str) -> dict[str, Any]:
    route, was_alias = resolve_route(manifest, route_name)
    cost = route.get("workflow_cost") if route.get("workflow_cost") in VALID_COSTS else "standard"
    return {
        "requested_route": route_name,
        "canonical_route": route.get("task"),
        "is_alias": was_alias,
        "aliases": _route_aliases(manifest, route),
        "summary": route.get("summary", ""),
        "workflow_cost": cost,
        "default_workflow_shape": _default_shape(manifest, cost),
        "allowed_workflow_shapes": sorted(_allowed_shapes(manifest, cost)),
        "rework_owner_default": route.get("rework_owner_default"),
        "handoff_sequence": route.get("handoff_sequence", []),
        "primary_doc": route.get("primary_doc"),
        "profile_doc": route.get("profile_doc"),
        "blocking_gates": _route_gates(route),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", "--root", type=Path, default=PROJECT_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    route_parser = subparsers.add_parser("route-info", help="show canonical route metadata")
    route_parser.add_argument("route")

    init_parser = subparsers.add_parser("init", help="create a current AgentTask record")
    init_parser.add_argument("task_id", nargs="?")
    init_parser.add_argument("--id", dest="id")
    init_parser.add_argument("--goal", required=True)
    init_parser.add_argument("--route", default="modify_code")
    init_parser.add_argument("--workflow-cost", choices=sorted(VALID_COSTS))
    init_parser.add_argument("--workflow-shape", choices=sorted(VALID_SHAPES))
    init_parser.add_argument("--risk-level", choices=sorted(VALID_RISK_LEVELS), default="low")
    init_parser.add_argument("--base-sha")
    init_parser.add_argument("--allowed-path", action="append", default=[])
    init_parser.add_argument("--acceptance-criteria", "--acceptance", action="append")
    init_parser.add_argument("--required-gate", "--gate", action="append")

    transition_parser = subparsers.add_parser("transition", help="record one lifecycle transition")
    transition_parser.add_argument("task_id")
    transition_parser.add_argument("to_state", nargs="?")
    transition_parser.add_argument("--to", dest="to_option")
    transition_parser.add_argument("--actor")
    transition_parser.add_argument("--condition")
    transition_parser.add_argument("--scope-changed", action="store_true")
    transition_parser.add_argument("--approval-evidence")
    transition_parser.add_argument("--approval-json")
    transition_parser.add_argument("--execution-json")
    transition_parser.add_argument("--review-json")
    transition_parser.add_argument("--handoff-json")

    validate_parser = subparsers.add_parser("validate", help="validate tasks and manifest")
    validate_parser.add_argument("task_id", nargs="?")
    validate_parser.add_argument("--all", action="store_true")
    validate_parser.add_argument("--strict", action="store_true")
    validate_parser.add_argument("--json", action="store_true", dest="as_json")

    archive_parser = subparsers.add_parser("archive", help="archive a terminal task")
    archive_parser.add_argument("task_id")
    archive_parser.add_argument("--year")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    project_root = args.project_root.resolve()
    try:
        if args.command == "route-info":
            manifest = _load_manifest(project_root)
            issues = _validate_manifest(project_root, manifest)
            if issues:
                raise WorkflowError("manifest is invalid:\n" + "\n".join(f"- {x}" for x in issues))
            print(json.dumps(route_info(manifest, args.route), ensure_ascii=False, indent=2))
            return 0
        if args.command == "init":
            path = init_task(args, project_root)
            print(
                json.dumps(
                    {"id": path.parent.name, "path": str(path.relative_to(project_root))},
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "transition":
            path = transition_task(args, project_root)
            task = _load_yaml(path)
            print(
                json.dumps(
                    {
                        "id": task["metadata"]["id"],
                        "state": task["status"]["state"],
                        "generation": task["metadata"]["generation"],
                        "plan_sha256": task["status"].get("plan_sha256"),
                        "path": str(path.relative_to(project_root)),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "validate":
            if args.all:
                paths = _all_task_paths(project_root)
            elif args.task_id:
                paths = [_task_path(args.task_id, project_root)]
            else:
                raise WorkflowError("validate requires a task id or --all")
            results = validate_paths(paths, project_root, strict=args.strict)
            failures = [(path, issues) for path, issues in results if issues]
            if args.as_json:
                print(
                    json.dumps(
                        [
                            {"path": str(path.relative_to(project_root)), "issues": issues}
                            for path, issues in results
                        ],
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                for path, issues in results:
                    print(f"{'INVALID' if issues else 'VALID'} {path.relative_to(project_root)}")
                    for issue in issues:
                        print(f"  - {issue}")
            return 1 if failures else 0
        if args.command == "archive":
            path = archive_task(args, project_root)
            print(json.dumps({"path": str(path.relative_to(project_root))}, ensure_ascii=False))
            return 0
        raise WorkflowError(f"unknown command: {args.command}")
    except (WorkflowError, OSError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
