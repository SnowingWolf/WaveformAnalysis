import sys

import numpy as np
import pytest

from scripts import benchmark_system_workload as benchmark


def test_input_budget_rejects_empty_and_large_files(tmp_path):
    raw_dir = tmp_path / "00700" / "RAW"
    raw_dir.mkdir(parents=True)
    path = raw_dir / "raw.bin"
    path.touch()
    with pytest.raises(ValueError, match="nonempty"):
        benchmark.input_metadata(path)
    with path.open("wb") as stream:
        stream.truncate(benchmark.MAX_INPUT_BYTES + 1)
    with pytest.raises(ValueError, match="at most"):
        benchmark.input_metadata(path)


def test_exact_comparison_preserves_nan_positions_order_and_dtype():
    source = np.array([(1, np.nan), (2, 1.0)], dtype=[("id", "i8"), ("value", "f8")])
    benchmark.assert_exact_payload(source.copy(), source)
    for changed in (source[::-1], source.astype([("id", "i4"), ("value", "f8")])):
        with pytest.raises(AssertionError):
            benchmark.assert_exact_payload(changed, source)
    changed = source.copy()
    changed["value"][0] = 0
    with pytest.raises(AssertionError, match="values"):
        benchmark.assert_exact_payload(changed, source)


def test_main_refuses_existing_output_directory(tmp_path):
    raw_dir = tmp_path / "00700" / "RAW"
    raw_dir.mkdir(parents=True)
    raw = raw_dir / "raw.bin"
    raw.write_bytes(b"not parsed in this boundary test")
    with pytest.raises(FileExistsError):
        benchmark.main(["--raw-file", str(raw), "--output-dir", str(tmp_path)])


def test_watchdog_stops_a_worker_at_the_time_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "MAX_WORKER_SECONDS", 0.05)
    result = benchmark._watch_worker(
        [sys.executable, "-c", "import time; time.sleep(5)"], tmp_path, None
    )
    assert result["limit_exceeded"] == "worker_wall_time"
    assert result["returncode"] != 0
    assert result["wall_seconds_including_imports"] < 2


def test_input_requires_the_v1725_run_layout(tmp_path):
    raw = tmp_path / "raw.bin"
    raw.write_bytes(b"unused")
    with pytest.raises(ValueError, match="<run_id>/RAW"):
        benchmark.input_metadata(raw)


def test_watchdog_cleans_up_when_interrupted(tmp_path, monkeypatch):
    original_popen = benchmark.subprocess.Popen
    children = []

    def record_child(*args, **kwargs):
        child = original_popen(*args, **kwargs)
        children.append(child)
        return child

    def interrupt(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(benchmark.subprocess, "Popen", record_child)
    monkeypatch.setattr(benchmark.time, "sleep", interrupt)
    with pytest.raises(KeyboardInterrupt):
        benchmark._watch_worker(
            [sys.executable, "-c", "import time; time.sleep(5)"], tmp_path, None
        )
    assert children[0].poll() is not None
