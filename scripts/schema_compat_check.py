#!/usr/bin/env python3
"""Schema compatibility checks for dtype/field changes and smoke chain."""

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

from _quality_common import SMOKE_TARGETS, run_smoke_chain

try:
    from scripts.change_scope import (
        build_scope_report,
        classify_paths,
        discover_changed_paths,
        load_task_scope,
        resolve_base,
    )
except ImportError:  # direct ``python scripts/schema_compat_check.py`` execution
    from change_scope import (  # type: ignore[no-redef]
        build_scope_report,
        classify_paths,
        discover_changed_paths,
        load_task_scope,
        resolve_base,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Stable consumer-facing fields; new fields may be added without breaking these contracts.
REQUIRED_FIELDS = {
    "records": {
        "record_id": "int64",
        "timestamp": "int64",
        "board": "int16",
        "channel": "int16",
        "dt": "int32",
        "baseline": "float64",
        "wave_offset": "int64",
        "event_length": "int32",
    },
    "hit_threshold": {
        "record_id": "int64",
        "timestamp": "int64",
        "board": "int16",
        "channel": "int16",
        "dt": "int32",
        "edge_start": "int32",
        "edge_end": "int32",
    },
    "hit_merged": {
        "merged_id": "int64",
        "record_id": "int64",
        "board": "int16",
        "channel": "int16",
        "dt": "int32",
        "time_start": "int64",
        "time_end": "int64",
        "component_offset": "int64",
        "component_count": "int32",
    },
    "peaks": {
        "peak_id": "int64",
        "time_start": "int64",
        "time_end": "int64",
        "time_peak": "int64",
        "center_time": "int64",
        "area": "float32",
        "height": "float32",
        "width": "float32",
        "width_25_75": "float32",
        "n_hits": "int32",
        "n_channels": "int32",
    },
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


def _extract_type_text(source: str, node: ast.AST) -> str:
    text = ast.get_source_segment(source, node)
    if text:
        return text.strip()
    return "<unknown>"


def _extract_dtype_fields(source: str, node: ast.AST) -> dict[str, str] | None:
    """Extract fields from np.dtype([...]) call."""
    if not isinstance(node, ast.Call):
        return None

    func = node.func
    is_dtype = False
    if isinstance(func, ast.Attribute):
        is_dtype = func.attr == "dtype"
    elif isinstance(func, ast.Name):
        is_dtype = func.id == "dtype"

    if not is_dtype or not node.args:
        return None

    first = node.args[0]
    if not isinstance(first, ast.List | ast.Tuple):
        return None

    fields: dict[str, str] = {}
    for elt in first.elts:
        if not isinstance(elt, ast.Tuple) or len(elt.elts) < 2:
            continue
        name_node = elt.elts[0]
        type_node = elt.elts[1]
        if isinstance(name_node, ast.Constant) and isinstance(name_node.value, str):
            fields[name_node.value] = _extract_type_text(source, type_node)

    return fields or None


def _parse_dtype_defs(source: str) -> dict[str, dict[str, str]]:
    tree = ast.parse(source)
    result: dict[str, dict[str, str]] = {}

    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name):
            continue

        fields = _extract_dtype_fields(source, stmt.value)
        if fields:
            result[target.id] = fields

    return result


def _changed_python_files(base: str, task: str | Path | None = None) -> list[str]:
    effective_base = resolve_base(base, task, project_root=PROJECT_ROOT)
    paths = discover_changed_paths(effective_base, project_root=PROJECT_ROOT)
    paths = tuple(
        path
        for path in paths
        if (
            path.startswith("waveform_analysis/")
            or path.startswith("scripts/")
            or path.startswith("tests/")
        )
        and path.endswith(".py")
    )
    if task is not None:
        task_scope = load_task_scope(task, project_root=PROJECT_ROOT)
        paths, _out_of_scope = classify_paths(paths, task_scope.allowed_paths)
    return sorted(set(paths))


def _build_dtype_change_report(base: str, rel_path: str) -> list[dict[str, object]]:
    old_src = _read_base_file(base, rel_path)
    new_path = PROJECT_ROOT / rel_path
    if not new_path.exists():
        return []

    new_src = new_path.read_text(encoding="utf-8")
    old_defs = _parse_dtype_defs(old_src) if old_src else {}
    new_defs = _parse_dtype_defs(new_src)

    out: list[dict[str, object]] = []

    for dtype_name in sorted(set(old_defs.keys()) | set(new_defs.keys())):
        old_fields = old_defs.get(dtype_name, {})
        new_fields = new_defs.get(dtype_name, {})
        if old_fields == new_fields:
            continue

        old_names = set(old_fields.keys())
        new_names = set(new_fields.keys())

        removed = sorted(old_names - new_names)
        added = sorted(new_names - old_names)

        type_changes = []
        for key in sorted(old_names & new_names):
            if old_fields[key] != new_fields[key]:
                type_changes.append(
                    {
                        "field": key,
                        "before": old_fields[key],
                        "after": new_fields[key],
                    }
                )

        rename_candidates = []
        used_added: set[str] = set()
        for old_name in removed:
            old_type = old_fields[old_name]
            for new_name in added:
                if new_name in used_added:
                    continue
                if new_fields[new_name] == old_type:
                    rename_candidates.append(
                        {
                            "from": old_name,
                            "to": new_name,
                            "type": old_type,
                        }
                    )
                    used_added.add(new_name)
                    break

        out.append(
            {
                "file": rel_path,
                "dtype": dtype_name,
                "removed_fields": removed,
                "added_fields": added,
                "type_changes": type_changes,
                "rename_candidates": rename_candidates,
            }
        )

    return out


def _build_migration_items(changes: list[dict[str, object]]) -> list[str]:
    items: list[str] = []
    for change in changes:
        dtype_name = change["dtype"]
        file_name = change["file"]
        for ren in change["rename_candidates"]:
            items.append(
                "{}@{}: 字段重命名候选 {} -> {} (type={})".format(
                    dtype_name,
                    file_name,
                    ren["from"],
                    ren["to"],
                    ren["type"],
                )
            )
        for field in change["removed_fields"]:
            items.append(f"{dtype_name}@{file_name}: 删除字段 {field}，请检查下游读取逻辑。")
        for field in change["added_fields"]:
            items.append(f"{dtype_name}@{file_name}: 新增字段 {field}，请确认序列化/文档同步。")
        for tc in change["type_changes"]:
            items.append(
                "{}@{}: 字段 {} 类型 {} -> {}，需评估旧缓存兼容。".format(
                    dtype_name,
                    file_name,
                    tc["field"],
                    tc["before"],
                    tc["after"],
                )
            )
    return items


def _check_product_fields(target: str, fields: dict[str, str]) -> list[str]:
    issues: list[str] = []
    for name, expected_type in REQUIRED_FIELDS[target].items():
        if name not in fields:
            issues.append(f"{target} 缺少关键字段: {name}")
        elif fields[name] != expected_type:
            issues.append(f"{target}.{name} 类型不匹配: {fields[name]} (expected {expected_type})")
    return issues


def _check_runtime_contracts() -> list[str]:
    """Check declared records/hit/peaks contracts, including the retained hit path."""
    from waveform_analysis.core.plugins.builtin.cpu import (
        HitMergePlugin,
        PeaksPlugin,
        RecordsPlugin,
        ThresholdHitPlugin,
        WaveformsPlugin,
    )

    issues: list[str] = []
    for plugin in (RecordsPlugin(), ThresholdHitPlugin(), HitMergePlugin(), PeaksPlugin()):
        fields = {name: str(plugin.output_dtype[name]) for name in plugin.output_dtype.names or ()}
        issues.extend(_check_product_fields(plugin.provides, fields))

    st_fields = set(WaveformsPlugin().output_dtype.names or ())
    missing_hit = sorted({"wave", "timestamp", "board", "channel", "record_id"} - st_fields)
    if missing_hit:
        issues.append("st_waveforms 缺少 hit 所需字段: {}".format(", ".join(missing_hit)))
    return issues


def _check_smoke_contracts(smoke: dict[str, object]) -> list[str]:
    """Reject empty or malformed output from the fixture's known nonempty pulses."""
    issues: list[str] = []
    if smoke["raw_file_groups"] <= 0:
        issues.append("raw_files 冒烟输入为空")
    for target in SMOKE_TARGETS:
        product = smoke["products"][target]
        if product["count"] <= 0:
            issues.append(f"{target} 冒烟输出为空")
        if target in REQUIRED_FIELDS:
            issues.extend(_check_product_fields(target, product["fields"]))
    return issues


def check_schema(
    base: str,
    run_smoke: bool,
    task: str | Path | None = None,
) -> dict[str, object]:
    effective_base = resolve_base(base, task, project_root=PROJECT_ROOT)
    scope_report = (
        build_scope_report(base=base, task=task, project_root=PROJECT_ROOT)
        if task is not None
        else None
    )
    files = _changed_python_files(effective_base, task=None)
    if scope_report is not None:
        allowed = set(scope_report.in_scope_paths)
        files = [path for path in files if path in allowed]

    dtype_changes: list[dict[str, object]] = []
    for rel_path in files:
        dtype_changes.extend(_build_dtype_change_report(effective_base, rel_path))

    migration_items = _build_migration_items(dtype_changes)
    contract_issues = _check_runtime_contracts()

    smoke = None
    smoke_error = None
    if run_smoke:
        try:
            smoke = run_smoke_chain()
            contract_issues.extend(_check_smoke_contracts(smoke))
        except Exception as exc:
            smoke_error = str(exc)

    return {
        "base": effective_base,
        "checked_files": files,
        "dtype_changes": dtype_changes,
        "migration_checklist": migration_items,
        "contract_issues": contract_issues,
        "smoke_result": smoke,
        "smoke_error": smoke_error,
        "scope": scope_report.to_dict() if scope_report is not None else None,
        "scope_error": scope_report.has_recorded_scope_error if scope_report is not None else False,
    }


def _print_report(report: dict[str, object]) -> None:
    print("=== schema_compat_check ===")
    print("base: {}".format(report["base"]))
    print("checked files: {}".format(len(report["checked_files"])))
    print("dtype changes: {}".format(len(report["dtype_changes"])))
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

    if report["dtype_changes"]:
        print("[dtype changes]")
        for change in report["dtype_changes"]:
            print("- {file}::{dtype}".format(**change))
            print("  removed: {}".format(", ".join(change["removed_fields"]) or "(none)"))
            print("  added: {}".format(", ".join(change["added_fields"]) or "(none)"))
            if change["type_changes"]:
                for tc in change["type_changes"]:
                    print("  type: {field} {before} -> {after}".format(**tc))
            if change["rename_candidates"]:
                for ren in change["rename_candidates"]:
                    print("  rename?: {from} -> {to} ({type})".format(**ren))
        print()

    if report["migration_checklist"]:
        print("[migration checklist]")
        for item in report["migration_checklist"]:
            print(f"- {item}")
        print()

    if report["contract_issues"]:
        print("[contract issues]")
        for item in report["contract_issues"]:
            print(f"- {item}")
        print()

    if report["smoke_result"] is not None:
        print("[smoke chain]")
        smoke = report["smoke_result"]
        print(f"raw_files={smoke['raw_file_groups']}")
        for target, product in smoke["products"].items():
            print(f"  {target}={product['count']}")
    elif report["smoke_error"]:
        print("[smoke chain]")
        print("FAILED: {}".format(report["smoke_error"]))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check dtype/schema compatibility and run smoke chain"
    )
    parser.add_argument(
        "--base", default=None, help="Git base ref (default: HEAD; task base in task mode)"
    )
    parser.add_argument(
        "--task", default=None, help="task YAML; use its stable scope base and allowed paths"
    )
    parser.add_argument(
        "--run-smoke",
        action="store_true",
        help="Run records-backed smoke chain raw_files->records/wave_pool->hit_threshold->peaks",
    )
    parser.add_argument("--json-out", default=None, help="Write report JSON to path")
    args = parser.parse_args()

    try:
        report = check_schema(base=args.base, run_smoke=args.run_smoke, task=args.task)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _print_report(report)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON report written to {out}")

    has_contract_issue = bool(report["contract_issues"])
    smoke_failed = bool(args.run_smoke and report["smoke_error"])
    return 1 if (has_contract_issue or smoke_failed or report.get("scope_error")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
