#!/usr/bin/env python3
"""Unified pre-release checks for version/docs/anchors/tests/perf artifacts."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTO_DOCS_DIR = PROJECT_ROOT / "docs" / "plugins" / "reference" / "builtin" / "auto"
AGENT_DOCS_DIR = PROJECT_ROOT / "docs" / "plugins" / "reference" / "agent"


def _run(cmd: list[str], cwd: Path = PROJECT_ROOT) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _git_changed_files(base: str, pathspec: str) -> list[str]:
    rc, out, err = _run(["git", "diff", "--name-only", base, "--", pathspec])
    if rc != 0:
        raise RuntimeError(f"git diff failed: {err.strip()}")
    return [line.strip() for line in out.splitlines() if line.strip()]


def _check_version_and_changelog(base: str) -> tuple[bool, list[str], dict[str, object]]:
    issues: list[str] = []

    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, flags=re.MULTILINE)
    if not match:
        issues.append("pyproject.toml 缺少项目版本号")
        version = None
    else:
        version = match.group(1)

    changelog_path = PROJECT_ROOT / "CHANGELOG.md"
    if not changelog_path.exists():
        issues.append("CHANGELOG.md 不存在")
        changelog_text = ""
    else:
        changelog_text = changelog_path.read_text(encoding="utf-8")

    if version and changelog_text:
        if version not in changelog_text and "Unreleased" not in changelog_text:
            issues.append(f"CHANGELOG.md 未包含版本 {version} 或 Unreleased 章节")

    changed_code = _git_changed_files(base, "waveform_analysis")
    changed_changelog = _git_changed_files(base, "CHANGELOG.md")
    if changed_code and not changed_changelog:
        issues.append("检测到代码变更但 CHANGELOG.md 未更新")

    ok = not issues
    return (
        ok,
        issues,
        {
            "version": version,
            "changed_code_files": len(changed_code),
            "changelog_touched": bool(changed_changelog),
        },
    )


def _collect_markdown_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in root.rglob("*.md"):
        rel = str(path.relative_to(root))
        files[rel] = path.read_text(encoding="utf-8")
    return files


def _compare_docs(expected_dir: Path, actual_dir: Path) -> list[str]:
    mismatches: list[str] = []
    if not actual_dir.exists():
        return [f"目录不存在: {actual_dir}"]

    expected_files = _collect_markdown_files(expected_dir)
    actual_files = _collect_markdown_files(actual_dir)

    expected_keys = set(expected_files.keys())
    actual_keys = set(actual_files.keys())

    for rel in sorted(expected_keys - actual_keys):
        mismatches.append(f"缺失文档: {rel}")
    for rel in sorted(actual_keys - expected_keys):
        mismatches.append(f"多余文档: {rel}")

    for rel in sorted(expected_keys & actual_keys):
        if expected_files[rel] != actual_files[rel]:
            mismatches.append(f"内容不一致: {rel}")

    return mismatches


def _check_generated_docs_sync() -> tuple[bool, dict[str, object]]:
    detail: dict[str, object] = {
        "auto_generation_ok": False,
        "agent_generation_ok": False,
        "auto_mismatches": [],
        "agent_mismatches": [],
        "errors": [],
    }

    with tempfile.TemporaryDirectory(prefix="wa-doc-sync-") as tmpdir:
        tmp_path = Path(tmpdir)
        gen_auto = tmp_path / "auto"
        gen_agent = tmp_path / "agent"

        rc, out, err = _run(
            [
                sys.executable,
                "-m",
                "waveform_analysis.utils.cli_docs",
                "generate",
                "plugins-auto",
                "-o",
                str(gen_auto),
            ]
        )
        if rc != 0:
            detail["errors"].append(f"plugins-auto 生成失败: {err.strip() or out.strip()}")
            return False, detail
        detail["auto_generation_ok"] = True

        rc, out, err = _run(
            [
                sys.executable,
                "-m",
                "waveform_analysis.utils.cli_docs",
                "generate",
                "plugins-agent",
                "-o",
                str(gen_agent),
            ]
        )
        if rc != 0:
            detail["errors"].append(f"plugins-agent 生成失败: {err.strip() or out.strip()}")
            return False, detail
        detail["agent_generation_ok"] = True

        detail["auto_mismatches"] = _compare_docs(gen_auto, AUTO_DOCS_DIR)
        detail["agent_mismatches"] = _compare_docs(gen_agent, AGENT_DOCS_DIR)

    ok = not detail["errors"] and not detail["auto_mismatches"] and not detail["agent_mismatches"]
    return ok, detail


def _check_doc_sync_and_anchors(base: str) -> tuple[bool, dict[str, object]]:
    detail: dict[str, object] = {}

    rc, out, err = _run(["bash", "scripts/check_doc_sync.sh", base])
    detail["doc_sync_rc"] = rc
    detail["doc_sync_out"] = out[-4000:]
    detail["doc_sync_err"] = err[-4000:]
    if rc != 0:
        return False, detail

    rc, out, err = _run(
        [sys.executable, "scripts/check_doc_anchors.py", "--check-sync", "--base", base]
    )
    detail["anchors_rc"] = rc
    detail["anchors_out"] = out[-4000:]
    detail["anchors_err"] = err[-4000:]
    if rc != 0:
        return False, detail

    return True, detail


def _run_key_tests(base: str) -> tuple[bool, dict[str, object]]:
    detail: dict[str, object] = {}

    schema_cmd = [
        sys.executable,
        "scripts/schema_compat_check.py",
        "--base",
        base,
        "--run-smoke",
    ]
    rc, out, err = _run(schema_cmd)
    detail["schema_smoke_rc"] = rc
    detail["schema_smoke_out"] = out[-4000:]
    detail["schema_smoke_err"] = err[-4000:]
    if rc != 0:
        return False, detail

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_events_df_convergence.py::test_legacy_events_grouped_config_migrates_to_df_events_and_globals",
        "tests/plugins/test_channel_config_resolver.py::test_resolve_channel_configs_rejects_boardless_keys",
    ]
    rc, out, err = _run(pytest_cmd)
    detail["pytest_rc"] = rc
    detail["pytest_out"] = out[-4000:]
    detail["pytest_err"] = err[-4000:]
    if rc != 0:
        return False, detail

    return True, detail


def _run_perf_regression(
    base: str, repeats: int, time_thr: float, mem_thr: float
) -> tuple[bool, dict[str, object]]:
    cmd = [
        sys.executable,
        "scripts/performance_regression_check.py",
        "--base",
        base,
        "--repeats",
        str(repeats),
        "--time-threshold-pct",
        str(time_thr),
        "--mem-threshold-pct",
        str(mem_thr),
    ]
    rc, out, err = _run(cmd)
    return rc == 0, {
        "rc": rc,
        "out": out[-4000:],
        "err": err[-4000:],
    }


def run_release_sync(
    base: str,
    perf_repeats: int,
    time_thr: float,
    mem_thr: float,
    skip_perf: bool,
    skip_tests: bool,
) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    ok, issues, detail = _check_version_and_changelog(base)
    checks.append({"name": "version_changelog", "ok": ok, "issues": issues, "detail": detail})

    ok, detail = _check_generated_docs_sync()
    issues = []
    if detail.get("errors"):
        issues.extend(detail["errors"])
    if detail.get("auto_mismatches"):
        issues.extend(["auto: " + m for m in detail["auto_mismatches"]])
    if detail.get("agent_mismatches"):
        issues.extend(["agent: " + m for m in detail["agent_mismatches"]])
    checks.append({"name": "generated_docs_sync", "ok": ok, "issues": issues, "detail": detail})

    ok, detail = _check_doc_sync_and_anchors(base)
    issues = [] if ok else ["doc_sync/doc_anchors checks failed"]
    checks.append({"name": "doc_sync_anchors", "ok": ok, "issues": issues, "detail": detail})

    if skip_tests:
        checks.append(
            {"name": "key_tests", "ok": True, "issues": ["skipped by flag"], "detail": {}}
        )
    else:
        ok, detail = _run_key_tests(base)
        issues = [] if ok else ["key tests failed"]
        checks.append({"name": "key_tests", "ok": ok, "issues": issues, "detail": detail})

    if skip_perf:
        checks.append(
            {
                "name": "performance_regression",
                "ok": True,
                "issues": ["skipped by flag"],
                "detail": {},
            }
        )
    else:
        ok, detail = _run_perf_regression(base, perf_repeats, time_thr, mem_thr)
        issues = [] if ok else ["performance regression check failed"]
        checks.append(
            {"name": "performance_regression", "ok": ok, "issues": issues, "detail": detail}
        )

    overall_ok = all(c["ok"] for c in checks)
    return {
        "base": base,
        "overall_ok": overall_ok,
        "checks": checks,
    }


def _print_report(report: dict[str, object]) -> None:
    print("=== release_artifact_sync ===")
    print("base: {}".format(report["base"]))
    print()

    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        print("- [{}] {}".format(status, check["name"]))
        for issue in check.get("issues", []):
            print(f"  - {issue}")

    print()
    print("overall: {}".format("PASS" if report["overall_ok"] else "FAIL"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified release artifact synchronization checks")
    parser.add_argument("--base", default="HEAD", help="Git base ref (default: HEAD)")
    parser.add_argument("--perf-repeats", type=int, default=1, help="Perf check repeats")
    parser.add_argument("--time-threshold-pct", type=float, default=10.0)
    parser.add_argument("--mem-threshold-pct", type=float, default=15.0)
    parser.add_argument("--skip-perf", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--json-out", default=None, help="Write report JSON to path")
    args = parser.parse_args()

    try:
        report = run_release_sync(
            base=args.base,
            perf_repeats=args.perf_repeats,
            time_thr=args.time_threshold_pct,
            mem_thr=args.mem_threshold_pct,
            skip_perf=args.skip_perf,
            skip_tests=args.skip_tests,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _print_report(report)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON report written to {out}")

    return 0 if report["overall_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
