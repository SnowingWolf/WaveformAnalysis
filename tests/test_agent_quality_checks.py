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
            "tests/",
        ],
    ]


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
