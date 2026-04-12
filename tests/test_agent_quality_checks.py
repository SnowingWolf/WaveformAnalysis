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
            "st_waveforms,hit",
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
