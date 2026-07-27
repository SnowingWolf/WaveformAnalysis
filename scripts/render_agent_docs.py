#!/usr/bin/env python3
"""Render and validate generated agent-doc sections from docs/agents/index.yaml."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required for scripts/render_agent_docs.py. "
        'Install dev dependencies with `pip install -e ".[dev]"`.'
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "docs" / "agents" / "index.yaml"
BEGIN_RE = re.compile(r"<!-- BEGIN GENERATED: (?P<name>[\w_-]+) -->")
END_RE = "<!-- END GENERATED: {name} -->"


@dataclass(frozen=True)
class Route:
    task: str
    summary: str
    workflow_cost: str | None
    primary_doc: str
    profile_doc: str | None
    secondary_docs: list[str]
    commands: list[str]
    blocking_gates: list[str]
    completion_contract: list[str]
    gate_trigger_policy: list[str]
    aliases: list[str]
    read_order: list[str]
    alias_of: str | None

    @property
    def is_alias(self) -> bool:
        return self.alias_of is not None


@dataclass(frozen=True)
class AgentProfile:
    id: str
    summary: str
    applicable_routes: list[str]
    capabilities: list[str]
    planning_mode: str
    planning_host_role: str
    planning_owns_state: bool
    planning_outputs: list[str]
    executing_mode: str
    executing_owns_state: bool
    allowed_roles: list[str]
    reviewing_mode: str
    reviewing_host_role: str
    reviewing_owns_state: bool
    review_focus: list[str]
    constraints: list[str]


VALID_WORKFLOW_COSTS = {"light", "standard", "strict"}
STRICT_REQUIRED_ARTIFACTS = {"plan_brief", "execution_report", "review_report"}


def _load_manifest(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("docs/agents/index.yaml must contain a mapping")
    return data


def _normalize_routes(data: dict[str, Any]) -> list[Route]:
    routes_raw = data.get("task_routes")
    if not isinstance(routes_raw, list):
        raise ValueError("task_routes must be a list")

    routes: list[Route] = []
    seen: set[str] = set()
    for raw in routes_raw:
        if not isinstance(raw, dict):
            raise ValueError("Each route entry must be a mapping")
        task = raw.get("task")
        if not isinstance(task, str) or not task:
            raise ValueError("Each route entry must have a non-empty task")
        if task in seen:
            raise ValueError(f"Duplicate route task: {task}")
        seen.add(task)
        routes.append(
            Route(
                task=task,
                summary=_as_str(raw, "summary", required=not bool(raw.get("alias_of"))),
                workflow_cost=_as_optional_str(raw, "workflow_cost"),
                primary_doc=_as_str(raw, "primary_doc", required=not bool(raw.get("alias_of"))),
                profile_doc=_as_optional_str(raw, "profile_doc"),
                secondary_docs=_as_str_list(raw, "secondary_docs"),
                commands=_as_str_list(raw, "commands"),
                blocking_gates=_as_str_list(raw, "blocking_gates"),
                completion_contract=_as_str_list(raw, "completion_contract"),
                gate_trigger_policy=_as_str_list(raw, "gate_trigger_policy"),
                aliases=_as_str_list(raw, "aliases"),
                read_order=_as_str_list(raw, "read_order"),
                alias_of=_as_optional_str(raw, "alias_of"),
            )
        )
    return routes


def _normalize_agent_profiles(data: dict[str, Any]) -> list[AgentProfile]:
    profiles_raw = data.get("agent_profiles")
    if not isinstance(profiles_raw, list):
        raise ValueError("agent_profiles must be a list")

    profiles: list[AgentProfile] = []
    seen: set[str] = set()
    for raw in profiles_raw:
        if not isinstance(raw, dict):
            raise ValueError("Each agent profile entry must be a mapping")
        profile_id = raw.get("id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Each agent profile entry must have a non-empty id")
        if profile_id in seen:
            raise ValueError(f"Duplicate agent profile id: {profile_id}")
        seen.add(profile_id)
        phases = raw.get("phase_participation")
        if not isinstance(phases, dict):
            raise ValueError(f"Agent profile `{profile_id}` phase_participation must be a mapping")
        expected_phases = {"planning", "executing", "reviewing"}
        if set(phases) != expected_phases:
            raise ValueError(
                f"Agent profile `{profile_id}` phase_participation must contain exactly "
                "planning, executing, and reviewing"
            )
        planning = _as_mapping(phases, "planning")
        executing = _as_mapping(phases, "executing")
        reviewing = _as_mapping(phases, "reviewing")
        profiles.append(
            AgentProfile(
                id=profile_id,
                summary=_as_str(raw, "summary"),
                applicable_routes=_as_str_list(raw, "applicable_routes"),
                capabilities=_as_str_list(raw, "capabilities"),
                planning_mode=_as_str(planning, "mode"),
                planning_host_role=_as_str(planning, "host_role"),
                planning_owns_state=_as_bool(planning, "owns_state"),
                planning_outputs=_as_str_list(planning, "required_outputs"),
                executing_mode=_as_str(executing, "mode"),
                executing_owns_state=_as_bool(executing, "owns_state"),
                allowed_roles=_as_str_list(executing, "allowed_roles"),
                reviewing_mode=_as_str(reviewing, "mode"),
                reviewing_host_role=_as_str(reviewing, "host_role"),
                reviewing_owns_state=_as_bool(reviewing, "owns_state"),
                review_focus=_as_str_list(reviewing, "required_focus"),
                constraints=_as_str_list(raw, "constraints"),
            )
        )
    return profiles


def _as_str(data: dict[str, Any], key: str, *, required: bool = True) -> str:
    value = data.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Route field `{key}` must be a non-empty string")
    return value


def _as_optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Route field `{key}` must be a non-empty string when present")
    return value


def _as_str_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"Route field `{key}` must be a list of non-empty strings")
    return value


def _as_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Field `{key}` must be a mapping")
    return value


def _as_bool(data: dict[str, Any], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Field `{key}` must be a boolean")
    return value


def validate_manifest(data: dict[str, Any], project_root: Path = PROJECT_ROOT) -> list[str]:
    issues: list[str] = []
    routes = _normalize_routes(data)
    route_names = {route.task for route in routes}
    canonical_route_names = {route.task for route in routes if not route.is_alias}
    profiles = _normalize_agent_profiles(data)

    roles_raw = data.get("agent_roles")
    if not isinstance(roles_raw, list):
        issues.append("Missing top-level `agent_roles` list")
        role_names: set[str] = set()
    else:
        role_names = {
            role["id"]
            for role in roles_raw
            if isinstance(role, dict) and isinstance(role.get("id"), str)
        }

    profile_contract = data.get("agent_profile_contract")
    if not isinstance(profile_contract, dict):
        issues.append("Missing top-level `agent_profile_contract` mapping")
    else:
        for key in (
            "selection_field",
            "role_field",
            "profiles_own_lifecycle_states",
            "profile_cannot_replace_reviewer",
            "required_artifact_fields",
            "phase_contracts",
        ):
            if key not in profile_contract:
                issues.append(f"Missing agent_profile_contract.{key}")
        expected_contract_values = {
            "selection_field": "agent_profile",
            "role_field": "executor_role",
            "profiles_own_lifecycle_states": False,
            "profile_cannot_replace_reviewer": True,
        }
        for key, expected in expected_contract_values.items():
            if key in profile_contract and profile_contract[key] != expected:
                issues.append(
                    f"agent_profile_contract.{key} must be {expected!r}, "
                    f"got {profile_contract[key]!r}"
                )
        required_artifact_fields = profile_contract.get("required_artifact_fields")
        expected_artifact_fields = {
            "plan_brief": ["agent_profile", "profile_plan"],
            "execution_report": ["agent_profile"],
            "review_report": ["agent_profile", "agent_profile_review"],
        }
        if (
            required_artifact_fields is not None
            and required_artifact_fields != expected_artifact_fields
        ):
            issues.append(
                "agent_profile_contract.required_artifact_fields must map plan, execution, "
                "and review artifacts to their canonical profile fields"
            )
        expected_phase_contracts = {
            "planning": {
                "mode": "contributor",
                "owner_role": "planner",
                "artifact_field": "profile_plan",
            },
            "executing": {
                "mode": "assignee",
                "role_field": "executor_role",
                "artifact_field": "agent_profile",
            },
            "reviewing": {
                "mode": "review_subject",
                "owner_role": "reviewer",
                "artifact_field": "agent_profile_review",
            },
        }
        if (
            profile_contract.get("phase_contracts") is not None
            and profile_contract["phase_contracts"] != expected_phase_contracts
        ):
            issues.append(
                "agent_profile_contract.phase_contracts must preserve canonical planning, "
                "executing, and reviewing semantics"
            )

    for profile in profiles:
        if profile.id in role_names:
            issues.append(f"Agent profile `{profile.id}` must not reuse a lifecycle role id")
        if not profile.allowed_roles:
            issues.append(f"Agent profile `{profile.id}` missing allowed_roles")
        if not profile.applicable_routes:
            issues.append(f"Agent profile `{profile.id}` missing applicable_routes")
        if not profile.capabilities:
            issues.append(f"Agent profile `{profile.id}` missing capabilities")
        if profile.planning_mode != "contributor":
            issues.append(f"Agent profile `{profile.id}` planning.mode must be contributor")
        if profile.planning_host_role != "planner":
            issues.append(f"Agent profile `{profile.id}` planning.host_role must be planner")
        if profile.planning_owns_state:
            issues.append(f"Agent profile `{profile.id}` planning.owns_state must be False")
        if not profile.planning_outputs:
            issues.append(f"Agent profile `{profile.id}` planning missing required_outputs")
        if profile.executing_mode != "assignee":
            issues.append(f"Agent profile `{profile.id}` executing.mode must be assignee")
        if profile.executing_owns_state:
            issues.append(f"Agent profile `{profile.id}` executing.owns_state must be False")
        if profile.reviewing_mode != "review_subject":
            issues.append(f"Agent profile `{profile.id}` reviewing.mode must be review_subject")
        if profile.reviewing_host_role != "reviewer":
            issues.append(f"Agent profile `{profile.id}` reviewing.host_role must be reviewer")
        if profile.reviewing_owns_state:
            issues.append(f"Agent profile `{profile.id}` reviewing.owns_state must be False")
        if not profile.review_focus:
            issues.append(f"Agent profile `{profile.id}` reviewing missing required_focus")
        if not profile.constraints:
            issues.append(f"Agent profile `{profile.id}` missing constraints")

        unknown_roles = sorted(set(profile.allowed_roles) - role_names)
        if unknown_roles:
            issues.append(
                f"Agent profile `{profile.id}` references unknown roles: "
                + ", ".join(unknown_roles)
            )
        non_executor_roles = sorted(
            role for role in profile.allowed_roles if not role.startswith("executor.")
        )
        if non_executor_roles:
            issues.append(
                f"Agent profile `{profile.id}` may only bind executor roles: "
                + ", ".join(non_executor_roles)
            )

        unknown_routes = sorted(set(profile.applicable_routes) - canonical_route_names)
        if unknown_routes:
            issues.append(
                f"Agent profile `{profile.id}` references unknown canonical routes: "
                + ", ".join(unknown_routes)
            )
        for route_name in set(profile.applicable_routes) & canonical_route_names:
            handoff = set(_as_str_list(route_raw_by_task(data, route_name), "handoff_sequence"))
            if not handoff.intersection(profile.allowed_roles):
                issues.append(
                    f"Agent profile `{profile.id}` has no allowed role in route "
                    f"`{route_name}` handoff_sequence"
                )

    reading_contract = data.get("agent_reading_contract")
    if not isinstance(reading_contract, dict):
        issues.append("Missing top-level `agent_reading_contract` mapping")
    else:
        for key in ("preferred_machine_entry", "preferred_markdown_entry", "default_read_order"):
            if key not in reading_contract:
                issues.append(f"Missing agent_reading_contract.{key}")

    for route in routes:
        if route.is_alias:
            if route.alias_of not in route_names:
                issues.append(
                    f"Alias route `{route.task}` points to unknown route `{route.alias_of}`"
                )
            if (
                route.summary
                or route.workflow_cost
                or route.primary_doc
                or route.profile_doc
                or route.read_order
                or route.gate_trigger_policy
            ):
                issues.append(
                    f"Alias route `{route.task}` must not redefine summary/workflow_cost/"
                    "primary_doc/profile_doc/read_order/gate_trigger_policy"
                )
            continue

        if route.workflow_cost not in VALID_WORKFLOW_COSTS:
            issues.append(
                f"Route `{route.task}` has invalid workflow_cost `{route.workflow_cost}`; "
                "expected light, standard, or strict"
            )
        if not route.summary:
            issues.append(f"Route `{route.task}` missing summary")
        if not route.primary_doc:
            issues.append(f"Route `{route.task}` missing primary_doc")
        if not route.profile_doc:
            issues.append(f"Route `{route.task}` missing profile_doc")
        if not route.read_order:
            issues.append(f"Route `{route.task}` missing read_order")
        if not route.gate_trigger_policy:
            issues.append(f"Route `{route.task}` missing gate_trigger_policy")

        required_artifacts = set(
            _as_str_list(route_raw_by_task(data, route.task), "required_artifacts")
        )
        if route.workflow_cost == "strict" and not STRICT_REQUIRED_ARTIFACTS.issubset(
            required_artifacts
        ):
            missing = ", ".join(sorted(STRICT_REQUIRED_ARTIFACTS - required_artifacts))
            issues.append(f"Strict route `{route.task}` missing required_artifacts: {missing}")

        for doc_path in [
            route.primary_doc,
            route.profile_doc,
            *route.secondary_docs,
            *route.read_order,
        ]:
            if doc_path and not (project_root / doc_path).exists():
                issues.append(f"Route `{route.task}` references missing path `{doc_path}`")

        for alias in route.aliases:
            if alias not in route_names:
                issues.append(
                    f"Route `{route.task}` alias `{alias}` is not declared as an alias route"
                )

    doc_index = data.get("doc_index", [])
    if not isinstance(doc_index, list):
        issues.append("doc_index must be a list")
    else:
        for entry in doc_index:
            if not isinstance(entry, dict):
                issues.append("doc_index entries must be mappings")
                continue
            path = entry.get("path")
            if not isinstance(path, str) or not path:
                issues.append("doc_index entry missing path")
                continue
            if not (project_root / path).exists():
                issues.append(f"doc_index references missing path `{path}`")

    return issues


def route_raw_by_task(data: dict[str, Any], task: str) -> dict[str, Any]:
    routes_raw = data.get("task_routes", [])
    if not isinstance(routes_raw, list):
        return {}
    for raw in routes_raw:
        if isinstance(raw, dict) and raw.get("task") == task:
            return raw
    return {}


def build_generated_sections(data: dict[str, Any]) -> dict[str, str]:
    routes = _normalize_routes(data)
    canonical_routes = [route for route in routes if not route.is_alias]
    profiles = _normalize_agent_profiles(data)

    return {
        "supported_routes": _render_supported_routes(canonical_routes),
        "route_catalog": _render_route_catalog(canonical_routes),
        "quick_links": _render_quick_links(data, canonical_routes),
        "recommended_read_order": _render_recommended_read_order(data, canonical_routes),
        "protocol_index": _render_protocol_index(data),
        "route_profile_index": _render_route_profile_index(canonical_routes),
        "adapter_index": _render_adapter_index(data),
        "agent_profile_catalog": _render_agent_profile_catalog(profiles),
        "profile_summary_modify_plugin": _render_profile_summary(
            _find_route(canonical_routes, "modify_plugin")
        ),
        "profile_summary_retire_compat": _render_profile_summary(
            _find_route(canonical_routes, "retire_compat")
        ),
        "profile_summary_generate_docs": _render_profile_summary(
            _find_route(canonical_routes, "generate_docs")
        ),
        "profile_summary_schema_compat_check": _render_profile_summary(
            _find_route(canonical_routes, "schema_compat_check")
        ),
        "profile_summary_assess_change_impact": _render_profile_summary(
            _find_route(canonical_routes, "assess_change_impact")
        ),
        "profile_summary_release_artifact_sync": _render_profile_summary(
            _find_route(canonical_routes, "release_artifact_sync")
        ),
        "profile_summary_debug_cache": _render_profile_summary(
            _find_route(canonical_routes, "debug_cache")
        ),
        "profile_summary_run_tests": _render_profile_summary(
            _find_route(canonical_routes, "run_tests")
        ),
        "profile_summary_performance_regression_check": _render_profile_summary(
            _find_route(canonical_routes, "performance_regression_check")
        ),
    }


def _find_route(routes: list[Route], task: str) -> Route:
    for route in routes:
        if route.task == task:
            return route
    raise KeyError(task)


def _render_supported_routes(routes: list[Route]) -> str:
    lines = []
    for route in routes:
        profile = route.profile_doc or route.primary_doc
        extra = f"；profile: `{profile}`" if profile else ""
        lines.append(f"- `{route.task}`：{route.summary}；主入口：`{route.primary_doc}`{extra}")
    return "\n".join(lines)


def _render_route_catalog(routes: list[Route]) -> str:
    lines = []
    for route in routes:
        profile = route.profile_doc or route.primary_doc
        lines.append(f"- `{route.task}`：`{route.primary_doc}` -> `{profile}`")
    return "\n".join(lines)


def _render_quick_links(data: dict[str, Any], routes: list[Route]) -> str:
    lines = [
        "- 主入口（推荐）：`../../AGENTS.md`",
        "- 生命周期：`lifecycle.md`",
        "- 架构总览：`architecture.md`",
        "- 插件文档 DAG：`PLUGIN_DOCUMENTATION_DAG.md`",
        "- 插件体系：`plugins.md`",
        "- 配置与兼容：`configuration.md`",
        "- 常见工作流：`workflows.md`",
        "- 协议模板：`protocol/README.md`",
    ]
    for route in routes:
        if route.profile_doc:
            relative = route.profile_doc.removeprefix("docs/agents/")
            lines.append(f"- `{route.task}` 实例：`{relative}`")
    lines.extend(
        [
            "- 适配层说明：`adapters/skills.md`、`adapters/mcp.md`",
            "- 约定与规范：`conventions.md`",
            "- 参考索引：`references.md`",
        ]
    )
    return "\n".join(lines)


def _render_recommended_read_order(data: dict[str, Any], routes: list[Route]) -> str:
    reading_contract = data.get("agent_reading_contract", {})
    order = reading_contract.get("default_read_order", [])
    lines = [
        f"{idx}. `{path.removeprefix('docs/agents/')}`" for idx, path in enumerate(order, start=1)
    ]
    current = len(lines)
    for route in routes:
        if route.profile_doc:
            current += 1
            lines.append(f"{current}. `{route.profile_doc.removeprefix('docs/agents/')}`")
    return "\n".join(lines)


def _render_protocol_index(data: dict[str, Any]) -> str:
    doc_index = data.get("doc_index", [])
    protocol_paths = [
        entry["path"]
        for entry in doc_index
        if isinstance(entry, dict) and str(entry.get("scope")) == "protocol"
    ]
    lines = [
        "- `docs/agents/lifecycle.md`",
        "- `docs/agents/index.yaml`",
        "- `docs/agents/protocol/README.md`",
        "- `docs/agents/protocol/task-lifecycle.md`",
        "- `docs/agents/protocol/artifacts/plan_brief.md`",
        "- `docs/agents/protocol/artifacts/compat_inventory.md`",
        "- `docs/agents/protocol/artifacts/execution_report.md`",
        "- `docs/agents/protocol/artifacts/review_report.md`",
        "- `docs/agents/protocol/route-profiles/template.md`",
    ]
    seen = set(lines)
    for path in protocol_paths:
        line = f"- `{path}`"
        if line not in seen and not path.endswith("README.md"):
            lines.append(line)
            seen.add(line)
    return "\n".join(lines)


def _render_route_profile_index(routes: list[Route]) -> str:
    lines = []
    for route in routes:
        if route.profile_doc:
            lines.append(f"- `{route.profile_doc}`")
    lines.append(
        "- `release_check` 复用 `docs/agents/protocol/route-profiles/release_artifact_sync.md`"
    )
    return "\n".join(lines)


def _render_adapter_index(data: dict[str, Any]) -> str:
    doc_index = data.get("doc_index", [])
    adapter_paths = [
        entry["path"]
        for entry in doc_index
        if isinstance(entry, dict) and str(entry.get("scope")) == "adapter"
    ]
    return "\n".join(f"- `{path}`" for path in adapter_paths)


def _render_agent_profile_catalog(profiles: list[AgentProfile]) -> str:
    sections: list[str] = []
    for profile in profiles:
        roles = ", ".join(f"`{role}`" for role in profile.allowed_roles)
        routes = ", ".join(f"`{route}`" for route in profile.applicable_routes)
        capabilities = ", ".join(f"`{item}`" for item in profile.capabilities)
        planning_outputs = ", ".join(f"`{item}`" for item in profile.planning_outputs)
        review_focus = ", ".join(f"`{item}`" for item in profile.review_focus)
        sections.extend(
            [
                f"### `{profile.id}`",
                f"- {profile.summary}",
                f"- 适用 route：{routes}",
                f"- 能力：{capabilities}",
                f"- `planning`：`{profile.planning_mode}`；必需输出：{planning_outputs}",
                f"- `executing`：`{profile.executing_mode}`；可承担角色：{roles}",
                f"- `reviewing`：`{profile.reviewing_mode}`；必审项：{review_focus}",
                "- 约束：",
                *(f"  - {constraint}" for constraint in profile.constraints),
                "",
            ]
        )
    return "\n".join(sections).rstrip()


def _render_profile_summary(route: Route) -> str:
    lines = [
        "## Use When",
        f"- {route.summary}",
        "",
        "## Route",
        f"- `task`: `{route.task}`",
        f"- `workflow_cost`: `{route.workflow_cost}`",
        f"- `primary_doc`: `{route.primary_doc}`",
    ]
    if route.profile_doc:
        lines.append(f"- `profile_doc`: `{route.profile_doc}`")
    if route.aliases:
        alias_text = ", ".join(f"`{alias}`" for alias in route.aliases)
        lines.append(f"- `aliases`: {alias_text}")
    lines.extend(["", "## Blocking Gates"])
    lines.extend(f"- `{gate}`" for gate in route.blocking_gates)
    lines.extend(["", "## Gate Trigger Policy"])
    lines.extend(f"- {policy}" for policy in route.gate_trigger_policy)
    lines.extend(["", "## Canonical Commands"])
    lines.extend(f"- `{cmd}`" for cmd in route.commands)
    return "\n".join(lines)


def render_file(path: Path, sections: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    cursor = 0
    while True:
        match = BEGIN_RE.search(text, cursor)
        if match is None:
            break
        name = match.group("name")
        if name not in sections:
            raise ValueError(f"{path}: unknown generated section `{name}`")
        end_marker = END_RE.format(name=name)
        end_idx = text.find(end_marker, match.end())
        if end_idx == -1:
            raise ValueError(f"{path}: missing end marker for `{name}`")
        replacement = f"{match.group(0)}\n{sections[name]}\n{end_marker}"
        text = text[: match.start()] + replacement + text[end_idx + len(end_marker) :]
        cursor = match.start() + len(replacement)
    return text


def collect_targets(project_root: Path = PROJECT_ROOT) -> list[Path]:
    return [
        project_root / "AGENTS.md",
        project_root / "docs" / "agents" / "INDEX.md",
        project_root / "docs" / "agents" / "references.md",
        project_root / "docs" / "agents" / "adapters" / "skills.md",
        project_root / "docs" / "agents" / "protocol" / "route-profiles" / "modify_plugin.md",
        project_root / "docs" / "agents" / "protocol" / "route-profiles" / "retire_compat.md",
        project_root / "docs" / "agents" / "protocol" / "route-profiles" / "generate_docs.md",
        project_root / "docs" / "agents" / "protocol" / "route-profiles" / "schema_compat_check.md",
        project_root
        / "docs"
        / "agents"
        / "protocol"
        / "route-profiles"
        / "assess_change_impact.md",
        project_root
        / "docs"
        / "agents"
        / "protocol"
        / "route-profiles"
        / "release_artifact_sync.md",
        project_root / "docs" / "agents" / "protocol" / "route-profiles" / "debug_cache.md",
        project_root / "docs" / "agents" / "protocol" / "route-profiles" / "run_tests.md",
        project_root
        / "docs"
        / "agents"
        / "protocol"
        / "route-profiles"
        / "performance_regression_check.md",
    ]


def run_check(write: bool) -> int:
    data = _load_manifest(MANIFEST_PATH)
    issues = validate_manifest(data)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1

    sections = build_generated_sections(data)
    rc = 0
    for path in collect_targets():
        rendered = render_file(path, sections)
        current = path.read_text(encoding="utf-8")
        if write:
            if rendered != current:
                path.write_text(rendered, encoding="utf-8")
        elif rendered != current:
            print(f"OUTDATED: {path.relative_to(PROJECT_ROOT)}", file=sys.stderr)
            rc = 1
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description="Render or validate generated agent docs sections")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="Rewrite generated sections in-place")
    group.add_argument(
        "--check", action="store_true", help="Fail if generated sections are outdated"
    )
    args = parser.parse_args()
    return run_check(write=args.write)


if __name__ == "__main__":
    raise SystemExit(main())
