#!/usr/bin/env python3
"""Assess plugin change impact before implementation or release."""

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = "waveform_analysis/core/plugins"


class PluginMeta:
    """Minimal plugin metadata extracted from source."""

    def __init__(
        self,
        class_name: str,
        provides: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
        output_dtype: Optional[str] = None,
        version: Optional[str] = None,
    ):
        self.class_name = class_name
        self.provides = provides
        self.depends_on = depends_on or []
        self.output_dtype = output_dtype
        self.version = version

    def to_dict(self) -> Dict[str, object]:
        return {
            "class_name": self.class_name,
            "provides": self.provides,
            "depends_on": list(self.depends_on),
            "output_dtype": self.output_dtype,
            "version": self.version,
        }


def _run_git(args: List[str], check: bool = True) -> str:
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


def _extract_string(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_depends(node: ast.AST) -> List[str]:
    values: List[str] = []
    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                values.append(elt.value)
            elif isinstance(elt, ast.Tuple) and elt.elts:
                first = elt.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    values.append(first.value)
    return values


def _extract_plugin_meta(source: str) -> Dict[str, PluginMeta]:
    tree = ast.parse(source)
    result: Dict[str, PluginMeta] = {}
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


def _read_base_file(base: str, rel_path: str) -> Optional[str]:
    result = subprocess.run(
        ["git", "show", f"{base}:{rel_path}"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _changed_plugin_files(base: str) -> List[str]:
    raw = _run_git(["diff", "--name-only", base, "--", PLUGIN_ROOT])
    files = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.endswith(".py"):
            continue
        if line:
            files.append(line)
    return sorted(set(files))


def _collect_current_plugin_graph() -> Tuple[Dict[str, PluginMeta], Dict[str, Set[str]]]:
    provider_meta: Dict[str, PluginMeta] = {}
    dep_to_consumers: Dict[str, Set[str]] = {}

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


def _collect_downstream(start_names: List[str], dep_to_consumers: Dict[str, Set[str]]) -> List[str]:
    visited: Set[str] = set()
    queue: List[str] = list(start_names)

    while queue:
        cur = queue.pop(0)
        for nxt in sorted(dep_to_consumers.get(cur, set())):
            if nxt in visited:
                continue
            visited.add(nxt)
            queue.append(nxt)

    return sorted(visited)


def _risk_level(change_keys: List[str], version_changed: bool) -> str:
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


def assess(base: str) -> Dict[str, object]:
    changed_files = _changed_plugin_files(base)
    provider_meta, dep_to_consumers = _collect_current_plugin_graph()

    records: List[Dict[str, object]] = []

    for rel_path in changed_files:
        current_path = PROJECT_ROOT / rel_path
        old_src = _read_base_file(base, rel_path)
        new_src = _read_file(current_path) if current_path.exists() else None

        old_meta = _extract_plugin_meta(old_src) if old_src else {}
        new_meta = _extract_plugin_meta(new_src) if new_src else {}

        class_names = sorted(set(old_meta.keys()) | set(new_meta.keys()))

        for cls in class_names:
            before = old_meta.get(cls)
            after = new_meta.get(cls)
            change_keys: List[str] = []

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

            notes: List[str] = []
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

    summary = {
        "base": base,
        "changed_plugin_files": changed_files,
        "changed_plugin_count": len(records),
        "risk_counts": {
            "high": len([r for r in records if r["lineage_risk"] == "high"]),
            "medium": len([r for r in records if r["lineage_risk"] == "medium"]),
            "low": len([r for r in records if r["lineage_risk"] == "low"]),
        },
        "known_providers": sorted(provider_meta.keys()),
        "records": records,
    }
    return summary


def _print_report(report: Dict[str, object]) -> None:
    print("=== assess_change_impact ===")
    print("base: {}".format(report["base"]))
    print("changed plugin files: {}".format(len(report["changed_plugin_files"])))
    print("risk counts: high={high}, medium={medium}, low={low}".format(**report["risk_counts"]))
    print()

    records = report["records"]
    if not records:
        print("No plugin contract changes detected.")
        return

    for rec in records:
        print("- {file} :: {class}".format(**rec))
        print("  changes: {}".format(", ".join(rec["changes"])))
        print("  lineage risk: {}".format(rec["lineage_risk"]))
        if rec["downstream_plugins"]:
            print("  downstream: {}".format(", ".join(rec["downstream_plugins"])))
        else:
            print("  downstream: (none)")
        if rec["notes"]:
            print("  notes: {}".format("; ".join(rec["notes"])))
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess plugin change impact and lineage risk")
    parser.add_argument("--base", default="HEAD", help="Git base ref (default: HEAD)")
    parser.add_argument("--json-out", default=None, help="Write full report JSON to path")
    args = parser.parse_args()

    try:
        report = assess(args.base)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _print_report(report)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON report written to {out}")

    high = report["risk_counts"]["high"]
    return 1 if high > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
