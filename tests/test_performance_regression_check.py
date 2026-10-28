"""Fail-closed checks for the isolated performance benchmark runner."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import _quality_common
from scripts import performance_regression_check as performance


def _sample(time_sec=1.0, mem_mb=0.0, count=1):
    return {
        "sample_count": count,
        "samples": [{"time_sec": time_sec, "peak_mem_mb": mem_mb} for _ in range(count)],
        "avg_time_sec": time_sec,
        "max_time_sec": time_sec,
        "median_time_sec": time_sec,
        "avg_peak_mem_mb": mem_mb,
        "max_peak_mem_mb": mem_mb,
        "median_peak_mem_mb": mem_mb,
    }


@pytest.mark.parametrize(
    ("before", "after", "targets"),
    [({}, {}, None), ({"hit": _sample()}, {}, None), ({}, {}, ["hit"])],
)
def test_compare_missing_targets_cannot_pass(before, after, targets):
    report = performance.compare(before, after, 10.0, 15.0, expected_targets=targets)

    assert not report["valid"]
    assert report["errors"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("median_time_sec", 0.0),
        ("avg_time_sec", float("nan")),
        ("max_time_sec", float("inf")),
        ("median_peak_mem_mb", -0.1),
        ("max_peak_mem_mb", float("nan")),
        ("sample_count", 0),
        ("sample_count", 2),
        ("sample_count", True),
        ("samples", []),
        ("samples", [{"time_sec": 0.0, "peak_mem_mb": 0.0}]),
    ],
)
def test_compare_rejects_invalid_measurements(field, value):
    after = _sample()
    after[field] = value

    report = performance.compare({"hit": _sample()}, {"hit": after}, 10.0, 15.0, expected_repeats=1)

    assert not report["valid"]
    assert report["rows"][0]["status"] == "invalid"


def test_compare_accepts_zero_memory_and_detects_growth_from_zero():
    before = {"hit": _sample()}
    unchanged = performance.compare(before, before, 10.0, 15.0)
    assert unchanged["valid"]
    assert unchanged["regressions"] == []

    growth = performance.compare(before, {"hit": _sample(mem_mb=2.0)}, 10.0, 15.0)
    assert growth["valid"]
    assert growth["regressions"][0]["mem_delta_pct"] is None
    json.dumps(growth, allow_nan=False)


def test_base_worktree_failure_does_not_run_current_checkout(monkeypatch):
    monkeypatch.setattr(performance, "_git_output", lambda *args: "a" * 40)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, "", "permission denied")

    monkeypatch.setattr(performance.subprocess, "run", fake_run)
    monkeypatch.setattr(
        performance, "_run_checkout", lambda *args, **kwargs: pytest.fail("unexpected benchmark")
    )

    with pytest.raises(RuntimeError, match="base worktree unavailable.*permission denied"):
        performance._run_base("HEAD", ["hit"], 1)

    assert len(calls) == 1
    assert calls[0][:4] == ["git", "worktree", "add", "--detach"]


@pytest.mark.parametrize(
    "options",
    [
        ["--repeats", "0"],
        ["--repeats", "-1"],
        ["--targets", "hit,hit"],
        ["--time-threshold-pct", "nan"],
        ["--mem-threshold-pct", "inf"],
        ["--time-threshold-pct", "-1"],
    ],
)
def test_invalid_cli_options_stop_before_benchmark(monkeypatch, options):
    monkeypatch.setattr(sys, "argv", ["performance_regression_check.py", *options])
    monkeypatch.setattr(
        performance, "_run_base", lambda *args, **kwargs: pytest.fail("unexpected benchmark")
    )

    with pytest.raises(SystemExit) as error:
        performance.main()

    assert error.value.code == 2


@pytest.mark.parametrize("repeats", [0, -1])
def test_benchmark_rejects_no_samples(repeats):
    with pytest.raises(ValueError, match="repeats must be positive"):
        _quality_common.benchmark_hot_targets(["hit"], repeats=repeats)


def test_benchmark_stops_tracemalloc_when_target_fails(tmp_path, monkeypatch):
    class BrokenContext:
        def get_data(self, run_id, target):
            raise RuntimeError("target computation failed")

    monkeypatch.setattr(_quality_common, "_build_context", lambda **kwargs: BrokenContext())
    with pytest.raises(RuntimeError, match="target computation failed"):
        _quality_common.benchmark_hot_targets(["hit"], repeats=1)

    assert not _quality_common.tracemalloc.is_tracing()


@pytest.fixture
def isolated_repository(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    package = repo / "waveform_analysis"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("timing = 1.0\n", encoding="utf-8")
    for args in (
        ["init", "--quiet"],
        ["add", "waveform_analysis/__init__.py"],
        [
            "-c",
            "user.name=Perf Test",
            "-c",
            "user.email=perf@example.invalid",
            "commit",
            "-qm",
            "base",
        ],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)

    harness = tmp_path / "harness.py"
    harness.write_text(
        "def benchmark_hot_targets(targets, repeats):\n"
        "    import waveform_analysis\n"
        "    value = waveform_analysis.timing\n"
        "    return {target: {\n"
        "        'sample_count': repeats,\n"
        "        'samples': [{'time_sec': value, 'peak_mem_mb': 0.0}] * repeats,\n"
        "        'avg_time_sec': value, 'max_time_sec': value, 'median_time_sec': value,\n"
        "        'avg_peak_mem_mb': 0.0, 'max_peak_mem_mb': 0.0, 'median_peak_mem_mb': 0.0,\n"
        "    } for target in targets}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(performance, "PROJECT_ROOT", repo)
    monkeypatch.setattr(performance, "BENCHMARK_HARNESS", harness)
    return repo, harness


def test_both_sides_import_their_checkout_and_record_provenance(
    tmp_path, monkeypatch, isolated_repository
):
    repo, harness = isolated_repository
    (repo / "waveform_analysis/__init__.py").write_text("timing = 2.0\n", encoding="utf-8")
    foreign = tmp_path / "foreign" / "waveform_analysis"
    foreign.mkdir(parents=True)
    (foreign / "__init__.py").write_text("raise RuntimeError('wrong source')\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(foreign.parent))
    before, base_source = performance._run_base("HEAD", ["hit"], 1)
    after, current_source = performance._run_current(["hit"], 1)

    assert before["hit"]["median_time_sec"] == 1.0
    assert after["hit"]["median_time_sec"] == 2.0
    assert base_source["commit"] == current_source["commit"]
    assert not base_source["dirty"]
    assert current_source["dirty"]
    for source in (base_source, current_source):
        assert source["harness"] == str(harness)
        assert source["executable"] == sys.executable
        assert source["python_version"] == sys.version
        assert source["module_paths"]["waveform_analysis"] == str(
            Path(source["checkout"]) / "waveform_analysis/__init__.py"
        )
    worktrees = subprocess.check_output(
        ["git", "worktree", "list", "--porcelain"], cwd=repo, text=True
    )
    assert worktrees.count("worktree ") == 1


def test_runner_rejects_modules_outside_checkout(tmp_path, isolated_repository):
    repo, harness = isolated_repository
    foreign = tmp_path / "foreign" / "waveform_analysis"
    foreign.mkdir(parents=True)
    (foreign / "__init__.py").write_text("timing = 1.0\n", encoding="utf-8")
    harness.write_text(
        f"import sys\nsys.path.insert(0, {str(foreign.parent)!r})\n"
        + harness.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="outside checkout"):
        performance._run_current(["hit"], 1)


def test_missing_base_fails_before_current_benchmark(monkeypatch, isolated_repository, capsys):
    monkeypatch.setattr(sys, "argv", ["performance_regression_check.py", "--base", "missing-ref"])
    monkeypatch.setattr(
        performance, "_run_current", lambda *args, **kwargs: pytest.fail("unexpected benchmark")
    )

    assert performance.main() == 2
    assert "ERROR:" in capsys.readouterr().err


def test_main_fails_for_a_target_missing_on_both_sides(monkeypatch, isolated_repository):
    monkeypatch.setattr(sys, "argv", ["performance_regression_check.py", "--targets", "hit"])
    source = {
        "commit": "a" * 40,
        "checkout": "/repo",
        "dirty": False,
        "executable": sys.executable,
        "module_paths": {"waveform_analysis": "/repo/waveform_analysis/__init__.py"},
    }
    monkeypatch.setattr(performance, "_run_base", lambda *args, **kwargs: ({}, source))
    monkeypatch.setattr(performance, "_run_current", lambda *args, **kwargs: ({}, source))

    assert performance.main() == 2
