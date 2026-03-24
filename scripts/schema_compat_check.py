#!/usr/bin/env python3
"""Schema compatibility checks for dtype/field changes and smoke chain."""

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

from _quality_common import run_smoke_chain

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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


def _changed_python_files(base: str) -> list[str]:
    raw = _run_git(["diff", "--name-only", base, "--", "waveform_analysis", "scripts", "tests"])
    files = []
    for line in raw.splitlines():
        line = line.strip()
        if line.endswith(".py"):
            files.append(line)
    return sorted(set(files))


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


def _check_runtime_contracts() -> list[str]:
    """Check key runtime schema contracts for df/events chain."""
    issues: list[str] = []

    from waveform_analysis.core.plugins.builtin.cpu import WaveformsPlugin

    st_fields = set(WaveformsPlugin().output_dtype.names or ())
    required_for_df = {"timestamp", "channel"}
    required_for_hit = {"wave", "timestamp", "channel"}
    required_for_events = {"wave", "baseline", "event_length", "timestamp", "channel"}

    missing_df = sorted(required_for_df - st_fields)
    missing_hit = sorted(required_for_hit - st_fields)
    missing_events = sorted(required_for_events - st_fields)

    if missing_df:
        issues.append("st_waveforms 缺少 df 所需字段: {}".format(", ".join(missing_df)))
    if missing_hit:
        issues.append("st_waveforms 缺少 hit 所需字段: {}".format(", ".join(missing_hit)))
    if missing_events:
        issues.append("st_waveforms 缺少 df_events 所需字段: {}".format(", ".join(missing_events)))

    return issues


def check_schema(base: str, run_smoke: bool) -> dict[str, object]:
    files = _changed_python_files(base)

    dtype_changes: list[dict[str, object]] = []
    for rel_path in files:
        dtype_changes.extend(_build_dtype_change_report(base, rel_path))

    migration_items = _build_migration_items(dtype_changes)
    contract_issues = _check_runtime_contracts()

    smoke = None
    smoke_error = None
    if run_smoke:
        try:
            smoke = run_smoke_chain()
            required_events = {"event_id", "t_min", "t_max", "dt/ns", "channels", "timestamps"}
            smoke_fields = set(smoke.get("events_fields", []))
            missing_events_out = sorted(required_events - smoke_fields)
            if missing_events_out:
                contract_issues.append(
                    "df_events 输出缺少关键字段: {}".format(", ".join(missing_events_out))
                )
        except Exception as exc:
            smoke_error = str(exc)

    return {
        "base": base,
        "checked_files": files,
        "dtype_changes": dtype_changes,
        "migration_checklist": migration_items,
        "contract_issues": contract_issues,
        "smoke_result": smoke,
        "smoke_error": smoke_error,
    }


def _print_report(report: dict[str, object]) -> None:
    print("=== schema_compat_check ===")
    print("base: {}".format(report["base"]))
    print("checked files: {}".format(len(report["checked_files"])))
    print("dtype changes: {}".format(len(report["dtype_changes"])))
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
        print(
            "raw_files={raw_file_groups}, st_waveforms={st_waveforms_count}, hit={hit_count}, df={df_rows}, events={events_count}".format(
                **smoke
            )
        )
    elif report["smoke_error"]:
        print("[smoke chain]")
        print("FAILED: {}".format(report["smoke_error"]))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check dtype/schema compatibility and run smoke chain"
    )
    parser.add_argument("--base", default="HEAD", help="Git base ref (default: HEAD)")
    parser.add_argument(
        "--run-smoke",
        action="store_true",
        help="Run fixed smoke chain raw_files->st_waveforms->hit->df->events",
    )
    parser.add_argument("--json-out", default=None, help="Write report JSON to path")
    args = parser.parse_args()

    try:
        report = check_schema(base=args.base, run_smoke=args.run_smoke)
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
    return 1 if (has_contract_issue or smoke_failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
