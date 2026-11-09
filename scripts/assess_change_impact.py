#!/usr/bin/env python3
"""Assess plugin change impact before implementation or release."""

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

import yaml

try:
    from scripts.agent_workflow import SHA1_RE, validate_task
    from scripts.change_scope import (
        build_scope_report,
        classify_paths,
        discover_changed_paths,
        load_task_scope,
        resolve_base,
    )
except ImportError:  # direct ``python scripts/assess_change_impact.py`` execution
    from agent_workflow import SHA1_RE, validate_task  # type: ignore[no-redef]
    from change_scope import (  # type: ignore[no-redef]
        build_scope_report,
        classify_paths,
        discover_changed_paths,
        load_task_scope,
        resolve_base,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = "waveform_analysis/core/plugins"
RETIREMENTS_MANIFEST = "docs/agents/plugin-retirements.yaml"


class PluginMeta:
    """Minimal plugin metadata extracted from source."""

    def __init__(
        self,
        class_name: str,
        provides: str | None = None,
        depends_on: list[str] | None = None,
        output_dtype: str | None = None,
        version: str | None = None,
    ):
        self.class_name = class_name
        self.provides = provides
        self.depends_on = depends_on or []
        self.output_dtype = output_dtype
        self.version = version

    def to_dict(self) -> dict[str, object]:
        return {
            "class_name": self.class_name,
            "provides": self.provides,
            "depends_on": list(self.depends_on),
            "output_dtype": self.output_dtype,
            "version": self.version,
        }


def _run_git(args: list[str], check: bool = True) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError("git command failed: git {}\n{}".format(" ".join(args), result.stderr))
    return result.stdout


def _is_plugin_like_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id.endswith("Plugin"):
            return True
        if isinstance(base, ast.Attribute) and base.attr.endswith("Plugin"):
            return True
    return False


def _extract_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_depends(node: ast.AST) -> list[str]:
    values: list[str] = []
    if isinstance(node, ast.List | ast.Tuple):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                values.append(elt.value)
            elif isinstance(elt, ast.Tuple) and elt.elts:
                first = elt.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    values.append(first.value)
    return values


def _extract_plugin_meta(source: str) -> dict[str, PluginMeta]:
    tree = ast.parse(source)
    result: dict[str, PluginMeta] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_plugin_like_class(node):
            continue

        meta = PluginMeta(class_name=node.name)

        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1:
                continue
            target = stmt.targets[0]
            if not isinstance(target, ast.Name):
                continue
            key = target.id

            if key == "provides":
                meta.provides = _extract_string(stmt.value)
            elif key == "depends_on":
                meta.depends_on = _extract_depends(stmt.value)
            elif key == "version":
                meta.version = _extract_string(stmt.value)
            elif key == "output_dtype":
                text = ast.get_source_segment(source, stmt.value)
                meta.output_dtype = text.strip() if text else None

        result[node.name] = meta
    return result


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_base_file(base: str, rel_path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{base}:{rel_path}"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _changed_plugin_files(base: str, task: str | Path | None = None) -> list[str]:
    effective_base = resolve_base(base, task, project_root=PROJECT_ROOT)
    paths = discover_changed_paths(effective_base, project_root=PROJECT_ROOT)
    if task is not None:
        task_scope = load_task_scope(task, project_root=PROJECT_ROOT)
        paths, _out_of_scope = classify_paths(paths, task_scope.allowed_paths)
    return sorted(
        path for path in paths if path.startswith(PLUGIN_ROOT + "/") and path.endswith(".py")
    )


def _collect_current_plugin_graph() -> tuple[dict[str, PluginMeta], dict[str, set[str]]]:
    provider_meta: dict[str, PluginMeta] = {}
    dep_to_consumers: dict[str, set[str]] = {}

    for path in (PROJECT_ROOT / PLUGIN_ROOT).rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        src = _read_file(path)
        class_metas = _extract_plugin_meta(src)
        for _, meta in class_metas.items():
            if not meta.provides:
                continue
            provider_meta[meta.provides] = meta
            for dep in meta.depends_on:
                dep_to_consumers.setdefault(dep, set()).add(meta.provides)

    return provider_meta, dep_to_consumers


def _collect_downstream(start_names: list[str], dep_to_consumers: dict[str, set[str]]) -> list[str]:
    visited: set[str] = set()
    queue: list[str] = list(start_names)

    while queue:
        cur = queue.pop(0)
        for nxt in sorted(dep_to_consumers.get(cur, set())):
            if nxt in visited:
                continue
            visited.add(nxt)
            queue.append(nxt)

    return sorted(visited)


def _risk_level(change_keys: list[str], version_changed: bool) -> str:
    key_set = set(change_keys)
    if "class_added" in key_set or "class_removed" in key_set:
        return "high"
    if "provides" in key_set:
        return "high"
    if "output_dtype" in key_set or "depends_on" in key_set:
        return "medium" if version_changed else "high"
    if "version" in key_set:
        return "low"
    return "low"


def _approved_retirements() -> dict[tuple[str, str], dict[str, object]]:
    """Validate explicit, reviewed retirements against their actual Git deletion."""
    manifest_path = PROJECT_ROOT / RETIREMENTS_MANIFEST
    if not manifest_path.exists():
        return {}
    manifest = yaml.safe_load(_read_file(manifest_path))
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "retirements"}:
        raise ValueError(f"{RETIREMENTS_MANIFEST}: expected schema_version and retirements")
    if (
        type(manifest["schema_version"]) is not int
        or manifest["schema_version"] != 1
        or not isinstance(manifest["retirements"], list)
    ):
        raise ValueError(f"{RETIREMENTS_MANIFEST}: unsupported schema or invalid retirements")
    workflow_manifest = yaml.safe_load(_read_file(PROJECT_ROOT / "docs/agents/index.yaml"))
    approved: dict[tuple[str, str], dict[str, object]] = {}
    for entry in manifest["retirements"]:
        required = {"file", "class", "provides", "removal_commit", "approval_task"}
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError(f"{RETIREMENTS_MANIFEST}: retirement must contain {sorted(required)}")
        if any(not isinstance(value, str) or not value.strip() for value in entry.values()):
            raise ValueError(f"{RETIREMENTS_MANIFEST}: retirement values must be non-empty strings")
        file, class_name = entry["file"], entry["class"]
        for key in ("file", "approval_task"):
            path = Path(entry[key])
            if path.is_absolute() or ".." in path.parts or path.as_posix() != entry[key]:
                raise ValueError(f"retirement {key} must be a canonical repository-relative path")
            if not (PROJECT_ROOT / path).resolve().is_relative_to(PROJECT_ROOT.resolve()):
                raise ValueError(f"retirement {key} must stay inside the repository")
        if not file.startswith(PLUGIN_ROOT + "/") or not file.endswith(".py"):
            raise ValueError(f"retirement file must be under {PLUGIN_ROOT}: {file}")
        identity = (file, class_name)
        if identity in approved:
            raise ValueError(f"duplicate retirement: {file}::{class_name}")
        commit = entry["removal_commit"]
        if not SHA1_RE.fullmatch(commit):
            raise ValueError("removal_commit must be a full 40-character Git SHA")
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if ancestor.returncode != 0:
            raise ValueError(f"removal_commit is not a HEAD ancestor: {commit}: {ancestor.stderr}")
        parent = _run_git(["rev-parse", f"{commit}^"]).strip()
        before_src = _read_base_file(parent, file)
        before = _extract_plugin_meta(before_src).get(class_name) if before_src else None
        after_src = _read_base_file(commit, file)
        after = _extract_plugin_meta(after_src) if after_src else {}
        if before is None or before.provides != entry["provides"] or class_name in after:
            raise ValueError(
                f"removal_commit does not remove {file}::{class_name}/{entry['provides']}"
            )
        task_path = PROJECT_ROOT / entry["approval_task"]
        task = yaml.safe_load(_read_file(task_path))
        if not isinstance(task, dict):
            raise ValueError(f"approval task must be a mapping: {entry['approval_task']}")
        issues = validate_task(
            task,
            manifest=workflow_manifest,
            task_path=task_path,
            project_root=PROJECT_ROOT,
        )
        if issues:
            raise ValueError(
                f"invalid retirement approval {entry['approval_task']}: {'; '.join(issues)}"
            )
        spec, status = task["spec"], task["status"]
        review = status["review"]
        if (
            spec["route"] not in {"retire_compat", "modify_plugin"}
            or spec["workflow_cost"] != "strict"
            or spec["workflow_shape"] != "staged"
            or status["state"] != "completed"
            or review.get("decision") != "approved"
        ):
            raise ValueError(
                "retirement approval requires a completed strict/staged retirement or plugin review"
            )
        inventory = spec.get("compat_inventory", {})
        confirmation = inventory.get("confirmation")
        if not isinstance(confirmation, str) or not confirmation.strip():
            raise ValueError("retirement approval requires explicit compat_inventory.confirmation")
        gates = review.get("gate_results", {})
        if gates.get("deletion_scope_confirmed", {}).get("status") != "PASS":
            raise ValueError("retirement approval requires deletion_scope_confirmed PASS")
        legacy_identity = f"{entry['provides']}/{class_name}"
        if not any(
            item.get("delete_action") == "remove"
            and legacy_identity
            in [value.strip() for value in item.get("legacy_form", "").split(";")]
            for item in inventory.get("items", [])
        ):
            raise ValueError(f"retirement not approved for removal: {legacy_identity}")
        approved[identity] = {**entry, "before": before.to_dict()}
    return approved


def assess(base: str, task: str | Path | None = None) -> dict[str, object]:
    retirements = _approved_retirements()
    effective_base = resolve_base(base, task, project_root=PROJECT_ROOT)
    scope_report = (
        build_scope_report(base=base, task=task, project_root=PROJECT_ROOT)
        if task is not None
        else None
    )
    changed_files = _changed_plugin_files(effective_base, task=None)
    if scope_report is not None:
        allowed = set(scope_report.in_scope_paths)
        changed_files = [path for path in changed_files if path in allowed]
    provider_meta, dep_to_consumers = _collect_current_plugin_graph()

    records: list[dict[str, object]] = []

    for rel_path in changed_files:
        current_path = PROJECT_ROOT / rel_path
        old_src = _read_base_file(effective_base, rel_path)
        new_src = _read_file(current_path) if current_path.exists() else None

        old_meta = _extract_plugin_meta(old_src) if old_src else {}
        new_meta = _extract_plugin_meta(new_src) if new_src else {}

        class_names = sorted(set(old_meta.keys()) | set(new_meta.keys()))

        for cls in class_names:
            before = old_meta.get(cls)
            after = new_meta.get(cls)
            change_keys: list[str] = []

            if before is None and after is not None:
                change_keys.append("class_added")
            elif before is not None and after is None:
                change_keys.append("class_removed")
            else:
                assert before is not None and after is not None
                if before.provides != after.provides:
                    change_keys.append("provides")
                if before.depends_on != after.depends_on:
                    change_keys.append("depends_on")
                if before.output_dtype != after.output_dtype:
                    change_keys.append("output_dtype")
                if before.version != after.version:
                    change_keys.append("version")

            if not change_keys:
                continue

            before_provides = before.provides if before else None
            after_provides = after.provides if after else None

            downstream_seed = []
            if before_provides:
                downstream_seed.append(before_provides)
            if after_provides and after_provides not in downstream_seed:
                downstream_seed.append(after_provides)

            downstream = _collect_downstream(downstream_seed, dep_to_consumers)

            version_changed = "version" in change_keys
            risk = _risk_level(change_keys, version_changed)

            notes: list[str] = []
            if "output_dtype" in change_keys and not version_changed:
                notes.append("output_dtype changed but version unchanged")
            if "depends_on" in change_keys and not version_changed:
                notes.append("depends_on changed but version unchanged")
            if "provides" in change_keys:
                notes.append("provides rename may invalidate downstream cache keys")
            if after and not after.depends_on:
                notes.append("dynamic depends_on may require manual lineage review")

            records.append(
                {
                    "file": rel_path,
                    "class": cls,
                    "changes": change_keys,
                    "before": before.to_dict() if before else None,
                    "after": after.to_dict() if after else None,
                    "downstream_plugins": downstream,
                    "lineage_risk": risk,
                    "notes": notes,
                }
            )

    for record in records:
        approval = retirements.get((record["file"], record["class"]))
        record["approved_retirement"] = (
            {key: approval[key] for key in ("removal_commit", "approval_task")}
            if approval is not None
            and record["changes"] == ["class_removed"]
            and record["before"] == approval["before"]
            and not record["downstream_plugins"]
            else None
        )

    summary = {
        "base": effective_base,
        "changed_plugin_files": changed_files,
        "changed_plugin_count": len(records),
        "risk_counts": {
            "high": len([r for r in records if r["lineage_risk"] == "high"]),
            "medium": len([r for r in records if r["lineage_risk"] == "medium"]),
            "low": len([r for r in records if r["lineage_risk"] == "low"]),
        },
        "approved_retirement_count": sum(bool(r["approved_retirement"]) for r in records),
        "unapproved_high_risk_count": sum(
            r["lineage_risk"] == "high" and not r["approved_retirement"] for r in records
        ),
        "known_providers": sorted(provider_meta.keys()),
        "records": records,
        "scope": scope_report.to_dict() if scope_report is not None else None,
        "scope_error": scope_report.has_recorded_scope_error if scope_report is not None else False,
    }
    return summary


def _print_report(report: dict[str, object]) -> None:
    print("=== assess_change_impact ===")
    print("base: {}".format(report["base"]))
    print("changed plugin files: {}".format(len(report["changed_plugin_files"])))
    print("risk counts: high={high}, medium={medium}, low={low}".format(**report["risk_counts"]))
    print("approved retirements: {}".format(report["approved_retirement_count"]))
    print("unapproved high risks: {}".format(report["unapproved_high_risk_count"]))
    scope = report.get("scope")
    if scope:
        print("in-scope changed paths: {}".format(len(scope["in_scope_paths"])))
        print(
            "out-of-scope dirty paths (reported, non-blocking): {}".format(
                len(scope["out_of_scope_paths"])
            )
        )
        for path in scope["out_of_scope_paths"]:
            print(f"  out-of-scope: {path}")
        if scope["recorded_out_of_scope_paths"]:
            print("recorded status.execution.changed_paths outside allowed_paths:")
            for path in scope["recorded_out_of_scope_paths"]:
                print(f"  ERROR: {path}")
    print()

    records = report["records"]
    if not records:
        print("No plugin contract changes detected.")
        return

    for rec in records:
        print("- {file} :: {class}".format(**rec))
        print("  changes: {}".format(", ".join(rec["changes"])))
        print("  lineage risk: {}".format(rec["lineage_risk"]))
        if rec["approved_retirement"]:
            print("  approved retirement: {}".format(rec["approved_retirement"]))
        if rec["downstream_plugins"]:
            print("  downstream: {}".format(", ".join(rec["downstream_plugins"])))
        else:
            print("  downstream: (none)")
        if rec["notes"]:
            print("  notes: {}".format("; ".join(rec["notes"])))
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess plugin change impact and lineage risk")
    parser.add_argument(
        "--base", default=None, help="Git base ref (default: HEAD; task base in task mode)"
    )
    parser.add_argument(
        "--task", default=None, help="task YAML; use its stable scope base and allowed paths"
    )
    parser.add_argument("--json-out", default=None, help="Write full report JSON to path")
    args = parser.parse_args()

    try:
        report = assess(args.base, task=args.task)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _print_report(report)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON report written to {out}")

    high = report["unapproved_high_risk_count"]
    return 1 if high > 0 or report.get("scope_error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
