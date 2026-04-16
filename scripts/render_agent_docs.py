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
    primary_doc: str
    profile_doc: str | None
    secondary_docs: list[str]
    commands: list[str]
    blocking_gates: list[str]
    completion_contract: list[str]
    aliases: list[str]
    read_order: list[str]
    alias_of: str | None

    @property
    def is_alias(self) -> bool:
        return self.alias_of is not None


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
                primary_doc=_as_str(raw, "primary_doc", required=not bool(raw.get("alias_of"))),
                profile_doc=_as_optional_str(raw, "profile_doc"),
                secondary_docs=_as_str_list(raw, "secondary_docs"),
                commands=_as_str_list(raw, "commands"),
                blocking_gates=_as_str_list(raw, "blocking_gates"),
                completion_contract=_as_str_list(raw, "completion_contract"),
                aliases=_as_str_list(raw, "aliases"),
                read_order=_as_str_list(raw, "read_order"),
                alias_of=_as_optional_str(raw, "alias_of"),
            )
        )
    return routes


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


def validate_manifest(data: dict[str, Any], project_root: Path = PROJECT_ROOT) -> list[str]:
    issues: list[str] = []
    routes = _normalize_routes(data)
    route_names = {route.task for route in routes}

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
            if route.summary or route.primary_doc or route.profile_doc or route.read_order:
                issues.append(
                    f"Alias route `{route.task}` must not redefine summary/primary_doc/profile_doc/read_order"
                )
            continue

        if not route.summary:
            issues.append(f"Route `{route.task}` missing summary")
        if not route.primary_doc:
            issues.append(f"Route `{route.task}` missing primary_doc")
        if not route.profile_doc:
            issues.append(f"Route `{route.task}` missing profile_doc")
        if not route.read_order:
            issues.append(f"Route `{route.task}` missing read_order")

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


def build_generated_sections(data: dict[str, Any]) -> dict[str, str]:
    routes = _normalize_routes(data)
    canonical_routes = [route for route in routes if not route.is_alias]

    return {
        "supported_routes": _render_supported_routes(canonical_routes),
        "route_catalog": _render_route_catalog(canonical_routes),
        "quick_links": _render_quick_links(data, canonical_routes),
        "recommended_read_order": _render_recommended_read_order(data, canonical_routes),
        "protocol_index": _render_protocol_index(data),
        "route_profile_index": _render_route_profile_index(canonical_routes),
        "adapter_index": _render_adapter_index(data),
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


def _render_profile_summary(route: Route) -> str:
    lines = [
        "## Use When",
        f"- {route.summary}",
        "",
        "## Route",
        f"- `task`: `{route.task}`",
        f"- `primary_doc`: `{route.primary_doc}`",
    ]
    if route.profile_doc:
        lines.append(f"- `profile_doc`: `{route.profile_doc}`")
    if route.aliases:
        alias_text = ", ".join(f"`{alias}`" for alias in route.aliases)
        lines.append(f"- `aliases`: {alias_text}")
    lines.extend(["", "## Blocking Gates"])
    lines.extend(f"- `{gate}`" for gate in route.blocking_gates)
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
