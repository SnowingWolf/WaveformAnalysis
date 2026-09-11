import json
from types import SimpleNamespace

import numpy as np
import pytest

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


def _comparison_report(*, factor=1.0, hash_suffix="", variance=0.05, target=None):
    compute_targets = {}
    baseline_times = {
        "peaklet_components": 100.0,
        "peaklets": 100.0,
        "peaklet_waveforms": 100.0,
        "peaklet_features": 100.0,
    }
    for target_name, elapsed in baseline_times.items():
        compute_targets[target_name] = {
            "elapsed_sec": {
                "median": elapsed * factor,
                "range_over_median": variance,
            },
            "incremental_peak_rss_bytes": {"median": 1000.0},
            "golden_consistent": True,
            "golden_sha256": f"hash-{target_name}{hash_suffix}",
        }
    report = {
        "summary": {
            "compute": {
                "targets": compute_targets,
                "total_compute_sec": {"range_over_median": variance},
                "incremental_peak_rss_bytes": {"median": 1000.0},
            },
            "end-to-end": {
                "elapsed_sec": {
                    "median": 100.0 * factor,
                    "range_over_median": variance,
                }
            },
        }
    }
    if target is not None:
        report["target"] = target
        report["targets"] = [target]
    return report


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


def test_runtime_environment_records_worktree_diff_hash():
    environment = benchmark._runtime_environment()

    assert environment["git_sha"]
    assert len(environment["git_diff_sha256"]) == 64


def test_validate_offset_pool_contract_reports_pair_and_rejects_out_of_bounds():
    waveforms = np.zeros(2, dtype=[("wave_offset", "i8"), ("wave_length", "i4")])
    waveforms["wave_offset"] = [0, 2]
    waveforms["wave_length"] = [2, 1]
    pool = np.arange(3, dtype=np.float32)

    pair = benchmark.paired_output_summary(waveforms, pool)

    assert pair["paired_output"]["dtype"] == "<f4"
    assert pair["paired_output"]["shape"] == [3]
    assert pair["offset_pool_contract"]["valid"] is True
    assert pair["offset_pool_contract"]["max_referenced_end"] == 3

    waveforms[1]["wave_offset"] = 3
    with pytest.raises(ValueError, match="outside its pool"):
        benchmark.validate_offset_pool_contract(waveforms, pool)


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


def test_aggregate_samples_preserves_target_dtype_and_paired_pool_contract():
    index = np.zeros(1, dtype=[("wave_offset", "i8"), ("wave_length", "i4")])
    pool = np.arange(2, dtype=np.float32)
    index["wave_length"] = 2
    pair = benchmark.paired_output_summary(index, pool)
    samples = []
    for repeat in range(2):
        samples.append(
            {
                "mode": "compute",
                "targets": {
                    "peaklet_waveforms": {
                        "elapsed_sec": 1.0 + repeat * 0.01,
                        "rss": {"incremental_peak_bytes": 10},
                        "output": benchmark.array_summary(index),
                        **pair,
                    }
                },
                "total_compute_sec": 1.0 + repeat * 0.01,
            }
        )

    summary = benchmark.aggregate_samples(samples)
    target_summary = summary["targets"]["peaklet_waveforms"]

    assert target_summary["dtype"] == index.dtype.descr
    assert target_summary["shape"] == [1]
    assert target_summary["paired_output"]["golden_consistent"] is True
    assert target_summary["offset_pool_contract"]["valid"] is True


def test_aggregate_samples_reports_target_aware_rss_at_top_level():
    samples = []
    for rss_bytes in (100, 200, 300):
        sample = _fake_sample("compute")
        target_result = sample["targets"]["peaklet_waveforms"]
        target_result["rss"]["incremental_peak_bytes"] = rss_bytes
        sample["targets"] = {"peaklet_waveforms": target_result}
        sample["target"] = "peaklet_waveforms"
        sample["total_compute_sec"] = target_result["elapsed_sec"]
        samples.append(sample)

    summary = benchmark.aggregate_samples(samples)

    assert summary["incremental_peak_rss_bytes"]["median"] == 200


def test_aggregate_samples_preserves_waveform_phase_diagnostics():
    samples = []
    for repeat in range(3):
        sample = _fake_sample("compute")
        target_result = sample["targets"]["peaklet_waveforms"]
        target_result["diagnostics"] = {
            "phase_timings": {"index_build": 1.0 + repeat, "save_cache": 0.0},
            "fallback_peaklets": 0,
            "used_compact_hmc": False,
            "save_cache_applicable": False,
        }
        sample["targets"] = {"peaklet_waveforms": target_result}
        sample["target"] = "peaklet_waveforms"
        sample["total_compute_sec"] = target_result["elapsed_sec"]
        samples.append(sample)

    summary = benchmark.aggregate_samples(samples)
    diagnostics = summary["targets"]["peaklet_waveforms"]["diagnostics"]

    assert diagnostics["phase_timings"]["index_build"]["median"] == 2.0
    assert diagnostics["phase_timings"]["save_cache"]["median"] == 0.0
    assert diagnostics["fallback_peaklets"] == [0, 0, 0]
    assert diagnostics["save_cache_applicable"] is False


def test_compare_reports_scopes_performance_checks_to_selected_target():
    baseline = _comparison_report(target="peaklet_waveforms")
    current = _comparison_report(factor=0.5, target="peaklet_waveforms")
    current["summary"]["compute"]["targets"] = {
        "peaklet_waveforms": current["summary"]["compute"]["targets"]["peaklet_waveforms"]
    }

    comparison = benchmark.compare_reports(current, baseline)

    assert comparison["passed"] is True
    assert {check["target"] for check in comparison["checks"] if check["target"]} <= {
        "peaklet_waveforms",
        "total_compute",
        "end-to-end",
    }


def test_compare_reports_fails_target_scope_mismatch():
    current = _comparison_report(factor=0.5, target="peaklet_waveforms")
    baseline = _comparison_report(target="peaklet_features")

    comparison = benchmark.compare_reports(current, baseline)

    assert comparison["passed"] is False
    scope_checks = [check for check in comparison["checks"] if check["name"] == "target_scope"]
    assert len(scope_checks) == 1
    assert scope_checks[0]["passed"] is False


def test_compare_reports_fails_target_set_mismatch():
    current = _comparison_report(factor=0.5)
    baseline = _comparison_report()
    current["targets"] = ["peaklet_waveforms"]

    comparison = benchmark.compare_reports(current, baseline)

    assert comparison["passed"] is False
    assert any(
        check["name"] == "target_scope" and not check["passed"] for check in comparison["checks"]
    )


def test_compare_reports_passes_all_thresholds():
    baseline = _comparison_report()
    current = _comparison_report(factor=0.5)

    comparison = benchmark.compare_reports(current, baseline)

    assert comparison["passed"] is True
    assert all(check["passed"] for check in comparison["checks"])


def test_compare_reports_rejects_waveform_fallback_peaklets():
    baseline = _comparison_report(target="peaklet_waveforms")
    current = _comparison_report(factor=0.5, target="peaklet_waveforms")
    current_target = current["summary"]["compute"]["targets"]["peaklet_waveforms"]
    current_target["diagnostics"] = {"fallback_peaklets": [0, 2, 0]}

    comparison = benchmark.compare_reports(current, baseline)

    assert comparison["passed"] is False
    assert any(
        check["name"] == "fallback_peaklets" and not check["passed"]
        for check in comparison["checks"]
    )


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


def _write_waveform_manifest(tmp_path, *, use_filtered=False, include_lineage=True):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    names = list(benchmark.DIRECT_PEAKLET_WAVEFORM_DEPENDENCIES)
    if use_filtered:
        names[-1] = "wave_pool_filtered"
    stems = {}
    for index, name in enumerate(names):
        value = np.arange(index + 1, dtype=np.float32)
        np.save(cache_root / f"{name}.npy", value)
        stems[name] = {
            "path": f"{name}.npy",
            "dtype": value.dtype.str,
            "shape": list(value.shape),
        }
    manifest = {
        "cache_root": "cache",
        "stems": stems,
        "config": {"peaklet_waveforms": {"use_filtered": use_filtered}},
    }
    if include_lineage:
        manifest["lineage"] = {name: {"cache_key": f"{name}-00196"} for name in names}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_direct_manifest_target_validation_checks_dynamic_pool_and_lineage(tmp_path):
    manifest_path = _write_waveform_manifest(tmp_path, use_filtered=True)

    arrays, config, metadata = benchmark._load_direct_manifest_with_metadata(
        manifest_path,
        target="peaklet_waveforms",
        config={},
    )

    assert metadata["required_dependencies"][-1] == "wave_pool_filtered"
    assert set(metadata["lineage"]) == set(metadata["required_dependencies"])
    assert config["peaklet_waveforms"]["use_filtered"] is True
    assert all(not value.flags.writeable for value in arrays.values())


def test_direct_manifest_target_validation_rejects_missing_lineage(tmp_path):
    manifest_path = _write_waveform_manifest(tmp_path, include_lineage=False)

    with pytest.raises(ValueError, match="lineage"):
        benchmark._load_direct_manifest_with_metadata(
            manifest_path,
            target="peaklet_waveforms",
            config={},
        )


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


def test_direct_waveform_target_preloads_all_dependencies_and_reuses_pair(monkeypatch):
    names = benchmark.DIRECT_PEAKLET_WAVEFORM_DEPENDENCIES
    index = np.zeros(
        2,
        dtype=[
            ("peak_id", "i8"),
            ("wave_offset", "i8"),
            ("wave_length", "i4"),
        ],
    )
    index["wave_offset"] = [0, 2]
    index["wave_length"] = [2, 1]
    pool = np.arange(3, dtype=np.float32)
    source = {name: np.zeros(1, dtype=np.int64) for name in names}
    events = []

    def fake_load(_path, *, target=None, config=None):
        assert target == "peaklet_waveforms"
        assert config == {}
        metadata = {
            "required_dependencies": list(names),
            "lineage": {name: {"key": name} for name in names},
        }
        return source, {}, metadata

    class FakeContext:
        def __init__(self, data, config):
            self.data = data
            self._plugins = {
                "peaklet_waveforms": SimpleNamespace(
                    _last_waveform_diagnostics={
                        "phase_timings": {
                            "index_build": 1.0,
                            "expand_components": 2.0,
                            "lexsort": 3.0,
                            "materialize_output": 4.0,
                        },
                        "fallback_peaklets": 0,
                        "used_compact_hmc": False,
                    }
                )
            }

        def get_data(self, run_id, name, **_kwargs):
            events.append((id(self), run_id, name))
            if name in self.data:
                return self.data[name]
            if name == "peaklet_waveforms":
                self.data[name] = index
                self.data["peaklet_waveform_pool"] = pool
                return index
            if name == "peaklet_waveform_pool":
                return self.data[name]
            raise KeyError(name)

    monkeypatch.setattr(benchmark, "_load_direct_manifest_with_metadata", fake_load)
    monkeypatch.setattr(benchmark, "DirectCacheContext", FakeContext)
    monkeypatch.setattr(benchmark, "gc", SimpleNamespace(collect=lambda: None))
    monkeypatch.setattr(benchmark, "PeakRssSampler", _NoopRssSampler)

    report = benchmark.run_direct_compute(
        run_id="run_test",
        manifest_path="unused",
        config={},
        target="peaklet_waveforms",
    )

    assert list(report["targets"]) == ["peaklet_waveforms"]
    assert report["targets"]["peaklet_waveforms"]["dependencies"] == list(names)
    assert report["targets"]["peaklet_waveforms"]["paired_output"]["shape"] == [3]
    assert report["targets"]["peaklet_waveforms"]["offset_pool_contract"]["valid"] is True
    diagnostics = report["targets"]["peaklet_waveforms"]["diagnostics"]
    assert diagnostics["phase_timings"]["save_cache"] == 0.0
    assert diagnostics["save_cache_applicable"] is False
    assert [event[2] for event in events] == [
        *names,
        "peaklet_waveforms",
        *names,
        "peaklet_waveforms",
        "peaklet_waveform_pool",
    ]


class _NoopRssSampler:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def to_dict(self):
        return {"incremental_peak_bytes": 0}


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
        return _fake_sample(mode)

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


def test_cli_extends_unstable_repeats_to_five_in_main_process(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    output_path = tmp_path / "report.json"
    calls = []

    def fake_worker(*, args, mode, repeat_index, output_path):
        calls.append((mode, repeat_index))
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
            "--mode",
            "compute",
            "--json-out",
            str(output_path),
        ]
    )

    assert result == 0
    assert calls == [("compute", index) for index in range(5)]
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["repeats"] == 5
    assert report["repeat_policy"]["auto_extended"] is True
    assert report["repeat_policy"]["extension_owner"] == "main_process"


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
