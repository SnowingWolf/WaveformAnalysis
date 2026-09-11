import json
from pathlib import Path
import subprocess
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run(cmd):
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)


def test_assess_change_impact_cli_writes_json(tmp_path):
    out_json = tmp_path / "impact.json"
    result = _run(
        [
            sys.executable,
            "scripts/assess_change_impact.py",
            "--base",
            "HEAD",
            "--json-out",
            str(out_json),
        ]
    )

    # high-risk change returns 1; no/high can both happen depending on current diff.
    assert result.returncode in (0, 1)
    assert out_json.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "records" in payload
    assert "risk_counts" in payload


@pytest.mark.slow
def test_schema_compat_check_cli_with_smoke(tmp_path):
    out_json = tmp_path / "schema.json"
    result = _run(
        [
            sys.executable,
            "scripts/schema_compat_check.py",
            "--base",
            "HEAD",
            "--run-smoke",
            "--json-out",
            str(out_json),
        ]
    )

    # non-zero is possible when contract issues are intentionally surfaced.
    assert result.returncode in (0, 1)
    assert out_json.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "dtype_changes" in payload
    assert "smoke_result" in payload


@pytest.mark.slow
def test_performance_regression_check_cli_runs(tmp_path):
    out_json = tmp_path / "perf.json"
    result = _run(
        [
            sys.executable,
            "scripts/performance_regression_check.py",
            "--base",
            "HEAD",
            "--targets",
            "st_waveforms,hit,hit_threshold",
            "--repeats",
            "1",
            "--time-threshold-pct",
            "500",
            "--mem-threshold-pct",
            "500",
            "--json-out",
            str(out_json),
        ]
    )

    assert result.returncode == 0
    assert out_json.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "before" in payload
    assert "after" in payload
    assert "comparison" in payload
    assert "hit_threshold" in payload["before"]
    assert "hit_threshold" in payload["after"]
    assert payload["before"]["hit_threshold"]["input"] == {
        "n_channels": 2,
        "n_events": 1200,
        "n_samples": 512,
        "total_samples": 1228800,
    }
    assert payload["before"]["hit_threshold"]["output"]["rows"] >= 1
    assert (
        payload["before"]["hit_threshold"]["output"] == payload["after"]["hit_threshold"]["output"]
    )


def test_performance_benchmark_uses_representative_workload_and_reports_output_size():
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
        from scripts import performance_regression_check

        assert "SYNTHETIC_N_EVENTS = 1200" in performance_regression_check.BENCH_SNIPPET
        assert "SYNTHETIC_N_SAMPLES = 512" in performance_regression_check.BENCH_SNIPPET
        namespace = {"__name__": "benchmark_contract_test"}
        exec(performance_regression_check.BENCH_SNIPPET, namespace)
        assert (
            namespace["SYNTHETIC_N_CHANNELS"]
            * namespace["SYNTHETIC_N_EVENTS"]
            * namespace["SYNTHETIC_N_SAMPLES"]
            == 1_228_800
        )
        summary = namespace["summarize_target_output"]([1, 2, 3])
        assert summary == {"rows": 3}
    finally:
        monkeypatch.undo()


def test_performance_regression_check_defaults_to_five_repeats(monkeypatch):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    from scripts import performance_regression_check

    repeats_seen = {}

    def fake_run_base(base, targets, repeats):
        repeats_seen["base"] = repeats
        return {}, "a" * 40

    def fake_run_current(targets, repeats):
        repeats_seen["current"] = repeats
        return {}

    def fake_compare(base_report, current_report, time_threshold_pct, mem_threshold_pct):
        return {
            "rows": [],
            "regressions": [],
            "time_threshold_pct": time_threshold_pct,
            "mem_threshold_pct": mem_threshold_pct,
        }

    monkeypatch.setattr(performance_regression_check, "_run_base", fake_run_base)
    monkeypatch.setattr(performance_regression_check, "_run_current", fake_run_current)
    monkeypatch.setattr(performance_regression_check, "compare", fake_compare)

    monkeypatch.setattr(sys, "argv", ["performance_regression_check.py", "--base", "HEAD"])
    assert performance_regression_check.main() == 0
    assert repeats_seen == {"base": 5, "current": 5}


def test_release_artifact_sync_defaults_to_five_perf_repeats(monkeypatch):
    from scripts import release_artifact_sync

    captured = {}

    def fake_run_release_sync(**kwargs):
        captured.update(kwargs)
        return {"base": kwargs["base"], "overall_ok": True, "checks": []}

    monkeypatch.setattr(release_artifact_sync, "run_release_sync", fake_run_release_sync)

    monkeypatch.setattr(sys, "argv", ["release_artifact_sync.py", "--base", "HEAD"])
    assert release_artifact_sync.main() == 0
    assert captured["perf_repeats"] == 5


def test_performance_compare_uses_median_and_ignores_sub_megabyte_noise(monkeypatch):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    from scripts.performance_regression_check import compare

    before = {
        "target": {
            "avg_time_sec": 1.0,
            "max_time_sec": 1.0,
            "avg_peak_mem_mb": 0.08,
            "max_peak_mem_mb": 0.08,
            "median_time_sec": 1.0,
            "median_peak_mem_mb": 0.08,
        }
    }
    after = {
        "target": {
            "avg_time_sec": 1.2,
            "max_time_sec": 1.2,
            "avg_peak_mem_mb": 0.12,
            "max_peak_mem_mb": 0.12,
            "median_time_sec": 0.99,
            "median_peak_mem_mb": 0.12,
        }
    }

    report = compare(before, after, time_threshold_pct=10.0, mem_threshold_pct=15.0)

    assert report["regressions"] == []
    assert report["rows"][0]["time_delta_pct"] == pytest.approx(-1.0)


def test_release_artifact_sync_key_tests_run_full_pytest(monkeypatch):
    from scripts import release_artifact_sync

    commands = []

    def fake_run(cmd, cwd=release_artifact_sync.PROJECT_ROOT):
        commands.append(cmd)
        return 0, "", ""

    monkeypatch.setattr(release_artifact_sync, "_run", fake_run)

    ok, detail = release_artifact_sync._run_key_tests("HEAD")

    assert ok
    assert detail["schema_smoke_rc"] == 0
    assert detail["full_pytest_rc"] == 0
    assert commands == [
        [
            sys.executable,
            "scripts/schema_compat_check.py",
            "--base",
            "HEAD",
            "--run-smoke",
        ],
        [
            sys.executable,
            "-m",
            "pytest",
        ],
    ]


def test_performance_base_worktree_failure_is_blocking(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    from scripts import performance_regression_check

    base_sha = "a" * 40

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["git", "rev-parse", "--verify"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=base_sha + "\n", stderr="")
        if cmd[:3] == ["git", "worktree", "add"]:
            return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="cannot add worktree")
        raise AssertionError(f"unexpected command: {cmd}")

    def forbid_current_fallback(*args, **kwargs):
        raise AssertionError("current benchmark must not replace a failed baseline")

    monkeypatch.setattr(performance_regression_check.subprocess, "run", fake_run)
    monkeypatch.setattr(performance_regression_check, "_run_benchmark", forbid_current_fallback)
    monkeypatch.setattr(performance_regression_check.tempfile, "mkdtemp", lambda **_: str(tmp_path))

    with pytest.raises(RuntimeError, match="failed to create performance baseline worktree"):
        performance_regression_check._run_base("v1.5.0", ["hit"], 1)


def test_performance_current_uses_fresh_shared_benchmark_subprocess(monkeypatch):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    from scripts import performance_regression_check

    captured = {}

    def fake_run(cmd, cwd, env):
        captured.update(cmd=cmd, cwd=cwd, env=env)
        return {"hit_threshold": {"avg_time_sec": 1.0, "avg_peak_mem_mb": 1.0}}

    monkeypatch.setattr(performance_regression_check, "_run_subprocess_json", fake_run)

    report = performance_regression_check._run_current(["hit_threshold"], repeats=5)

    assert report["hit_threshold"]["avg_time_sec"] == 1.0
    assert captured["cmd"][:2] == [sys.executable, "-c"]
    assert captured["cmd"][2] == performance_regression_check.BENCH_SNIPPET
    assert captured["cwd"] == performance_regression_check.PROJECT_ROOT
    assert json.loads(captured["env"]["QUALITY_TARGETS_JSON"]) == ["hit_threshold"]
    assert captured["env"]["QUALITY_REPEATS"] == "5"
    assert captured["env"]["PYTHONHASHSEED"] == "0"


def test_performance_compare_marks_missing_target_as_blocking():
    from scripts.performance_regression_check import compare

    report = compare(
        {"records": {"avg_time_sec": 1.0, "avg_peak_mem_mb": 1.0}},
        {},
        time_threshold_pct=10.0,
        mem_threshold_pct=15.0,
    )

    assert report["regressions"] == [
        {
            "target": "records",
            "status": "missing",
            "reason": "missing benchmark data",
        }
    ]


def test_performance_benchmark_contract_guards_empty_hit_threshold_output(monkeypatch):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    from scripts import performance_regression_check

    namespace = {"__name__": "benchmark_contract_test"}
    exec(performance_regression_check.BENCH_SNIPPET, namespace)

    with pytest.raises(RuntimeError, match="empty output is not a valid benchmark"):
        namespace["validate_target_output"]("hit_threshold", [])


def test_performance_base_uses_resolved_sha_in_detached_worktree(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    from scripts import performance_regression_check

    base_sha = "d" * 40
    baseline_root = tmp_path / "baseline"
    baseline_root.mkdir()
    worktree_commands = []

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["git", "rev-parse", "--verify"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=base_sha + "\n", stderr="")
        if cmd[:3] == ["git", "worktree", "add"]:
            worktree_commands.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:3] == ["git", "worktree", "remove"]:
            worktree_commands.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    def fake_benchmark(cmd, cwd, env):
        assert cwd == baseline_root / "worktree"
        assert json.loads(env["QUALITY_TARGETS_JSON"]) == ["hit"]
        assert env["QUALITY_REPEATS"] == "1"
        return {"hit": {"avg_time_sec": 1.0, "avg_peak_mem_mb": 1.0}}

    monkeypatch.setattr(performance_regression_check.subprocess, "run", fake_run)
    monkeypatch.setattr(
        performance_regression_check.tempfile, "mkdtemp", lambda **_: str(baseline_root)
    )
    monkeypatch.setattr(performance_regression_check, "_run_subprocess_json", fake_benchmark)

    report, resolved_sha = performance_regression_check._run_base("v1.5.0", ["hit"], 1)

    assert resolved_sha == base_sha
    assert report["hit"]["avg_time_sec"] == 1.0
    assert worktree_commands[0] == [
        "git",
        "worktree",
        "add",
        "--detach",
        str(baseline_root / "worktree"),
        base_sha,
    ]
    assert worktree_commands[1][:4] == ["git", "worktree", "remove", "--force"]


def test_performance_cleanup_failure_does_not_mask_benchmark_failure(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    from scripts import performance_regression_check

    base_sha = "c" * 40
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        if cmd[:3] == ["git", "rev-parse", "--verify"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=base_sha + "\n", stderr="")
        if cmd[:3] == ["git", "worktree", "add"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if len(cmd) >= 2 and cmd[:2] == [sys.executable, "-c"]:
            return subprocess.CompletedProcess(
                cmd, 7, stdout="benchmark output", stderr="benchmark failed"
            )
        if cmd[:3] == ["git", "worktree", "remove"]:
            return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="cleanup failed")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(performance_regression_check.subprocess, "run", fake_run)
    monkeypatch.setattr(performance_regression_check.tempfile, "mkdtemp", lambda **_: str(tmp_path))

    with pytest.raises(RuntimeError, match="command failed") as exc_info:
        performance_regression_check._run_base("v1.5.0", ["hit"], 1)

    assert "cleanup failed" not in str(exc_info.value)
    assert commands[1][:3] == ["git", "worktree", "add"]
    assert commands[2][:2] == [sys.executable, "-c"]
    assert commands[3][:3] == ["git", "worktree", "remove"]


def test_performance_report_records_resolved_baseline_sha(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    from scripts import performance_regression_check

    base_sha = "b" * 40
    empty_comparison = {
        "rows": [],
        "regressions": [],
        "time_threshold_pct": 10.0,
        "mem_threshold_pct": 15.0,
    }
    monkeypatch.setattr(
        performance_regression_check,
        "_run_base",
        lambda base, targets, repeats: ({}, base_sha),
    )
    monkeypatch.setattr(performance_regression_check, "_run_current", lambda **kwargs: {})
    monkeypatch.setattr(
        performance_regression_check, "compare", lambda **kwargs: dict(empty_comparison)
    )
    out_json = tmp_path / "perf.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "performance_regression_check.py",
            "--base",
            "v1.5.0",
            "--json-out",
            str(out_json),
        ],
    )

    assert performance_regression_check.main() == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["base"] == "v1.5.0"
    assert payload["base_sha"] == base_sha


def test_release_artifact_sync_keeps_legacy_reference_pages_allowed(tmp_path):
    from scripts import release_artifact_sync

    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    (expected / "INDEX.md").write_text("index\n", encoding="utf-8")
    (actual / "INDEX.md").write_text("index\n", encoding="utf-8")
    (actual / "s1_s2.md").write_text("legacy compatibility page\n", encoding="utf-8")

    assert release_artifact_sync._compare_docs(expected, actual) == []

    (actual / "unexpected.md").write_text("not allow-listed\n", encoding="utf-8")
    assert release_artifact_sync._compare_docs(expected, actual) == ["多余文档: unexpected.md"]
