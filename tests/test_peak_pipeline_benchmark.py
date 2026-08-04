import json
from types import SimpleNamespace

import numpy as np

from scripts import benchmark_peak_pipeline as benchmark


def _fake_sample(mode, elapsed_offset=0.0):
    targets = {}
    for index, target in enumerate(benchmark.PIPELINE_TARGETS):
        output = {
            "row_count": index + 1,
            "nbytes": (index + 1) * 8,
            "golden": {"golden_sha256": f"hash-{target}"},
        }
        if mode == "compute":
            targets[target] = {
                "elapsed_sec": index + 1.0 + elapsed_offset,
                "rss": {"incremental_peak_bytes": 100 + index},
                "output": output,
            }
        else:
            targets[target] = output
    payload = {"mode": mode, "targets": targets}
    if mode == "compute":
        payload["total_compute_sec"] = sum(item["elapsed_sec"] for item in targets.values())
    else:
        payload["elapsed_sec"] = 10.0 + elapsed_offset
        payload["rss"] = {"incremental_peak_bytes": 1000 + elapsed_offset}
    return payload


def _comparison_report(*, factor=1.0, hash_suffix="", variance=0.05):
    compute_targets = {}
    baseline_times = {
        "peaklet_components": 100.0,
        "peaklets": 100.0,
        "peaklet_waveforms": 100.0,
        "peaklet_features": 100.0,
    }
    for target, elapsed in baseline_times.items():
        compute_targets[target] = {
            "elapsed_sec": {
                "median": elapsed * factor,
                "range_over_median": variance,
            },
            "golden_consistent": True,
            "golden_sha256": f"hash-{target}{hash_suffix}",
        }
    return {
        "summary": {
            "compute": {
                "targets": compute_targets,
                "total_compute_sec": {"range_over_median": variance},
            },
            "end-to-end": {
                "elapsed_sec": {
                    "median": 100.0 * factor,
                    "range_over_median": variance,
                }
            },
        }
    }


def test_chunked_hash_is_stable_and_sensitive_to_content():
    first = np.arange(40, dtype=np.int64).reshape(10, 4)
    same = first.copy()
    changed = first.copy()
    changed[-1, -1] += 1

    first_hash = benchmark.chunked_hash(first, chunk_bytes=32)
    same_hash = benchmark.chunked_hash(same, chunk_bytes=32)
    changed_hash = benchmark.chunked_hash(changed, chunk_bytes=32)

    assert first_hash["golden_sha256"] == same_hash["golden_sha256"]
    assert first_hash["golden_sha256"] != changed_hash["golden_sha256"]
    assert len(first_hash["chunk_hashes"]) == 10
    assert first_hash["shape"] == [10, 4]


def test_aggregate_samples_reports_median_range_and_golden_consistency():
    samples = [_fake_sample("compute", offset) for offset in (0.0, 1.0, 2.0)]

    summary = benchmark.aggregate_samples(samples)

    first = summary["targets"][benchmark.PIPELINE_TARGETS[0]]
    assert first["elapsed_sec"]["median"] == 2.0
    assert first["elapsed_sec"]["range_over_median"] == 1.0
    assert first["golden_consistent"] is True
    assert summary["total_compute_sec"]["median"] > 0


def test_aggregate_samples_uses_targets_from_report():
    sample = _fake_sample("compute")
    sample["targets"] = {"custom": sample["targets"][benchmark.PIPELINE_TARGETS[0]]}
    sample["total_compute_sec"] = sample["targets"]["custom"]["elapsed_sec"]

    summary = benchmark.aggregate_samples([sample])

    assert list(summary["targets"]) == ["custom"]


def test_compare_reports_passes_all_thresholds():
    baseline = _comparison_report()
    current = _comparison_report(factor=0.5)

    comparison = benchmark.compare_reports(current, baseline)

    assert comparison["passed"] is True
    assert all(check["passed"] for check in comparison["checks"])


def test_compare_reports_fails_performance_threshold():
    baseline = _comparison_report()
    current = _comparison_report(factor=0.5)
    current["summary"]["compute"]["targets"]["peaklets"]["elapsed_sec"]["median"] = 70.0

    comparison = benchmark.compare_reports(current, baseline)

    failed = [check for check in comparison["checks"] if not check["passed"]]
    assert comparison["passed"] is False
    assert any(
        check["name"] == "compute_improvement" and check["target"] == "peaklets" for check in failed
    )


def test_compare_reports_fails_golden_mismatch():
    comparison = benchmark.compare_reports(
        _comparison_report(factor=0.5, hash_suffix="-changed"),
        _comparison_report(),
    )

    assert comparison["passed"] is False
    assert any(
        check["name"] == "golden_hash" and not check["passed"] for check in comparison["checks"]
    )


def test_compare_reports_fails_variance_gate():
    comparison = benchmark.compare_reports(
        _comparison_report(factor=0.5, variance=0.11),
        _comparison_report(),
    )

    assert comparison["passed"] is False
    assert any(
        check["name"] == "variance" and not check["passed"] for check in comparison["checks"]
    )


def test_load_config_accepts_custom_config_wrapper(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"run_id": "ignored", "custom_config": {"daq_adapter": "vx2730"}}),
        encoding="utf-8",
    )

    assert benchmark.load_config(config_path) == {"daq_adapter": "vx2730"}


def test_direct_manifest_loads_memmap_and_context_stores_fresh_output(tmp_path):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    source = np.arange(6, dtype=np.int64)
    np.save(cache_root / "hit_merged.npy", source)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cache_root": "cache",
                "stems": {"hit_merged": "hit_merged.npy"},
                "config": {"peaklets": {"dt": 4}},
            }
        ),
        encoding="utf-8",
    )

    arrays, config = benchmark.load_direct_manifest(manifest_path)
    output_dir = tmp_path / "fresh"
    context = benchmark.DirectCacheContext(arrays, config, output_dir=output_dir)
    result = np.arange(3, dtype=np.float32)
    context._set_data("run", "result", result)

    assert isinstance(arrays["hit_merged"], np.memmap)
    np.testing.assert_array_equal(arrays["hit_merged"], source)
    assert context.get_data("run", "result") is result
    np.testing.assert_array_equal(np.load(output_dir / "result.npy"), result)


def test_direct_stage_removes_golden_target_and_executes_plugin():
    golden = np.arange(2, dtype=np.int64)
    computed = np.arange(3, dtype=np.int64)
    calls = []

    class FakePlugin:
        def compute(self, _context, run_id):
            calls.append(run_id)
            return computed

    stage_data = benchmark._direct_stage_data({"peaklet_components": golden}, "peaklet_components")
    context = benchmark.DirectCacheContext(stage_data)
    context._plugins["peaklet_components"] = FakePlugin()

    result = context.get_data("run", "peaklet_components")

    assert calls == ["run"]
    assert result is computed
    assert result is not golden


def test_direct_end_to_end_removes_all_derived_golden_arrays():
    data = {
        target: np.zeros(1, dtype=np.int64)
        for target in (*benchmark.DIRECT_PIPELINE_TARGETS, "peaklet_waveform_pool")
    }
    data["hit_merged"] = np.ones(1, dtype=np.int64)

    stage_data = benchmark._direct_end_to_end_data(data)

    assert set(stage_data) == {"hit_merged"}


def test_cli_runs_each_mode_repeat_in_an_independent_worker(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    output_path = tmp_path / "report.json"
    calls = []

    def fake_worker(*, args, mode, repeat_index, output_path):
        calls.append((mode, repeat_index, output_path.name))
        return _fake_sample(mode, float(repeat_index))

    monkeypatch.setattr(benchmark, "_run_worker_subprocess", fake_worker)

    result = benchmark.main(
        [
            "--run-id",
            "run_test",
            "--storage-dir",
            str(tmp_path / "storage"),
            "--config-json",
            str(config_path),
            "--repeats",
            "2",
            "--mode",
            "both",
            "--json-out",
            str(output_path),
        ]
    )

    assert result == 0
    assert calls == [
        ("compute", 0, "compute-0.json"),
        ("compute", 1, "compute-1.json"),
        ("end-to-end", 0, "end-to-end-0.json"),
        ("end-to-end", 1, "end-to-end-1.json"),
    ]
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["summary"]["compute"]["mode"] == "compute"
    assert report["summary"]["end-to-end"]["mode"] == "end-to-end"


def test_comparison_cli_returns_nonzero_and_writes_itemized_report(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    comparison_path = tmp_path / "comparison.json"
    baseline_path.write_text(json.dumps(_comparison_report()), encoding="utf-8")
    current_path.write_text(json.dumps(_comparison_report(factor=0.9)), encoding="utf-8")

    result = benchmark.main(
        [
            "--baseline-report",
            str(baseline_path),
            "--current-report",
            str(current_path),
            "--comparison-json-out",
            str(comparison_path),
        ]
    )

    assert result == 1
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert comparison["passed"] is False
    assert comparison["checks"]


def test_compute_only_preloads_direct_dependencies_before_timing(monkeypatch):
    events = []

    class FakePlugin:
        def resolve_depends_on(self, _ctx, run_id=None):
            assert run_id == "run_test"
            return ["dependency"]

        def compute(self, _ctx, run_id):
            events.append(("compute", run_id))
            return np.zeros(2, dtype=np.int64)

    class FakeContext:
        profiler = SimpleNamespace(durations={}, counts={})

        def get_plugin(self, _target):
            return FakePlugin()

        def get_data(self, run_id, target):
            events.append(("preload", run_id, target))
            return np.zeros(1, dtype=np.int64)

    monkeypatch.setattr(benchmark, "PIPELINE_TARGETS", ("target",))
    monkeypatch.setattr(benchmark, "build_context", lambda *_args: FakeContext())
    monkeypatch.setattr(benchmark, "_resolved_config_summary", lambda _ctx: {})
    monkeypatch.setattr(benchmark, "_lineage_summary", lambda _ctx: {})

    report = benchmark.run_compute_only(run_id="run_test", storage_dir="unused", config={})

    assert events == [
        ("preload", "run_test", "dependency"),
        ("compute", "run_test"),
        ("preload", "run_test", "dependency"),
        ("compute", "run_test"),
    ]
    assert report["targets"]["target"]["output"]["row_count"] == 2
