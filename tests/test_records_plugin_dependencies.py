from unittest.mock import patch

import numpy as np
import pytest

from tests.daq_adapter_helpers import make_v1725_single_wave_blob
from tests.utils import FakeContext
from waveform_analysis.core import Context
from waveform_analysis.core.plugins.builtin.cpu.records import (
    RecordsPlugin,
    WavePoolPlugin,
    _apply_records_polarity,
    get_records_bundle,
    get_records_bundle_cache_key,
)
from waveform_analysis.core.processing.records_builder import RecordsBundle, RecordsBundleRef


def _make_raw_files():
    return [["ch1_0.csv"], ["ch0_0.csv"]]


def test_records_depends_on_raw_files_for_vx2730():
    plugin = RecordsPlugin()
    ctx = FakeContext(config={"daq_adapter": "vx2730"})

    assert plugin.resolve_depends_on(ctx) == ["raw_files"]


def test_records_depends_on_raw_files_for_v1725():
    plugin = RecordsPlugin()
    ctx = FakeContext(config={"daq_adapter": "v1725"})

    assert plugin.resolve_depends_on(ctx) == ["raw_files"]


def test_records_can_depend_on_st_waveforms_for_vx2730():
    plugin = RecordsPlugin()
    ctx = FakeContext(config={"daq_adapter": "vx2730", "records": {"input_source": "st_waveforms"}})

    assert plugin.resolve_depends_on(ctx) == ["st_waveforms"]


def test_records_rejects_st_waveforms_source_for_v1725():
    plugin = RecordsPlugin()
    ctx = FakeContext(config={"daq_adapter": "v1725", "records": {"input_source": "st_waveforms"}})

    with pytest.raises(ValueError, match="not supported for v1725"):
        plugin.resolve_depends_on(ctx)


def test_wave_pool_depends_on_same_upstream_as_records():
    plugin = WavePoolPlugin()
    ctx = FakeContext(config={"daq_adapter": "vx2730"})

    assert plugin.resolve_depends_on(ctx) == ["raw_files"]


def test_wave_pool_uses_records_input_source_when_records_registered():
    records_plugin = RecordsPlugin()
    wave_pool_plugin = WavePoolPlugin()
    ctx = FakeContext(
        config={"daq_adapter": "vx2730", "records": {"input_source": "st_waveforms"}},
        plugins={"records": records_plugin, "wave_pool": wave_pool_plugin},
    )

    assert wave_pool_plugin.resolve_depends_on(ctx) == ["st_waveforms"]


def test_get_records_bundle_reuses_raw_files_for_non_v1725():
    plugin = RecordsPlugin()
    fake_bundle = RecordsBundle(
        records=np.zeros(2, dtype=plugin.output_dtype),
        wave_pool=np.array([5, 6, 7, 8, 1, 2, 3, 4], dtype=np.uint16),
    )
    ctx = FakeContext(
        config={
            "daq_adapter": "vx2730",
            "records": {
                "parse_engine": "polars",
                "n_jobs": 4,
                "chunksize": 2048,
                "use_process_pool": True,
                "channel_workers": 2,
                "channel_executor": "process",
            },
        },
        data={"raw_files": _make_raw_files()},
        plugins={"records": plugin},
    )

    with patch(
        "waveform_analysis.core.plugins.builtin.cpu.records.build_records_from_raw_files",
        return_value=fake_bundle,
    ) as mocked:
        bundle = get_records_bundle(ctx, "run_001")

    assert mocked.call_count == 1
    assert mocked.call_args.args[0] == _make_raw_files()
    assert mocked.call_args.kwargs["parse_engine"] == "polars"
    assert mocked.call_args.kwargs["n_jobs"] == 4
    assert mocked.call_args.kwargs["chunksize"] == 2048
    assert mocked.call_args.kwargs["use_process_pool"] is True
    assert mocked.call_args.kwargs["channel_workers"] == 2
    assert mocked.call_args.kwargs["channel_executor"] == "process"
    np.testing.assert_array_equal(bundle.wave_pool, fake_bundle.wave_pool)


def test_get_records_bundle_can_use_st_waveforms_for_non_v1725():
    plugin = RecordsPlugin()
    st_waveforms = np.zeros(2, dtype=[("wave", np.uint16, 4)])
    fake_bundle = RecordsBundle(
        records=np.zeros(2, dtype=plugin.output_dtype),
        wave_pool=np.array([1, 2, 3, 4], dtype=np.uint16),
    )
    ctx = FakeContext(
        config={
            "daq_adapter": "vx2730",
            "records": {
                "input_source": "st_waveforms",
                "records_part_size": 128,
            },
        },
        data={"st_waveforms": st_waveforms},
        plugins={"records": plugin},
    )

    with patch(
        "waveform_analysis.core.plugins.builtin.cpu.records.build_records_from_st_waveforms_sharded",
        return_value=fake_bundle,
    ) as mocked:
        bundle = get_records_bundle(ctx, "run_001")

    assert mocked.call_count == 1
    assert mocked.call_args.args[0] is st_waveforms
    assert mocked.call_args.kwargs["part_size"] == 128
    assert mocked.call_args.kwargs["default_dt_ns"] == 2
    np.testing.assert_array_equal(bundle.wave_pool, fake_bundle.wave_pool)


def test_apply_records_polarity_assigns_by_unique_hardware_channel(monkeypatch):
    records = np.zeros(6, dtype=RecordsPlugin().output_dtype)
    records["board"] = [0, 0, 0, 1, 1, 2]
    records["channel"] = [0, 0, 1, 0, 0, 0]
    bundle = RecordsBundle(records=records, wave_pool=np.zeros(0, dtype=np.uint16))

    from waveform_analysis.core.hardware.channel import HardwareChannel

    captured = {}

    def fake_lookup(_context, _run_id, boards, channels):
        captured["n_lookup_rows"] = len(boards)
        return {
            HardwareChannel(0, 0): "negative",
            HardwareChannel(1, 0): "positive",
        }

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records._build_polarity_lookup",
        fake_lookup,
    )

    result = _apply_records_polarity(object(), "run_001", bundle)

    assert result is bundle
    assert captured["n_lookup_rows"] == len(records)
    np.testing.assert_array_equal(
        records["polarity"],
        np.array(["negative", "negative", "unknown", "positive", "positive", "unknown"]),
    )


def test_get_records_bundle_cache_hit_skips_stale_bundle_cleanup(monkeypatch):
    plugin = RecordsPlugin()
    ctx = FakeContext(config={"daq_adapter": "vx2730"}, plugins={"records": plugin})
    cached_bundle = RecordsBundle(
        records=np.zeros(1, dtype=plugin.output_dtype),
        wave_pool=np.array([1, 2], dtype=np.uint16),
    )
    cache_key = get_records_bundle_cache_key(ctx, "run_001")
    ctx._set_data("run_001", cache_key, cached_bundle)

    cleanup_calls = []

    def fail_cleanup(*_args):
        cleanup_calls.append(True)
        raise AssertionError("cleanup should not run on cache hit")

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records._cleanup_stale_bundles",
        fail_cleanup,
    )

    assert get_records_bundle(ctx, "run_001") is cached_bundle
    assert cleanup_calls == []


def test_wave_pool_plugin_reuses_shared_bundle_builder(tmp_path):
    run_id = "run_001"
    ctx = Context(storage_dir=str(tmp_path / "shared_bundle"), config={"daq_adapter": "vx2730"})
    ctx.register(RecordsPlugin(), WavePoolPlugin())
    ctx._set_data(run_id, "raw_files", _make_raw_files())

    fake_bundle = RecordsBundle(
        records=np.zeros(2, dtype=ctx.get_plugin("records").output_dtype),
        wave_pool=np.array([1, 2, 3, 4], dtype=np.uint16),
    )

    with patch(
        "waveform_analysis.core.plugins.builtin.cpu.records.build_records_from_raw_files",
        return_value=fake_bundle,
    ) as mocked:
        records = ctx.get_data(run_id, "records")
        wave_pool = ctx.get_data(run_id, "wave_pool")

    assert mocked.call_count == 1
    np.testing.assert_array_equal(records, fake_bundle.records)
    np.testing.assert_array_equal(wave_pool, fake_bundle.wave_pool)


def test_v1725_records_plugins_default_to_disk_backed_memmaps(tmp_path):
    run_id = "run_001"
    raw = tmp_path / "test_raw_b0_seg0.bin"
    raw.write_bytes(make_v1725_single_wave_blob(channel=0, timestamp=10, baseline=100))

    ctx = Context(
        storage_dir=str(tmp_path / "storage"),
        config={"daq_adapter": "v1725", "show_progress": False},
    )
    ctx.register(RecordsPlugin(), WavePoolPlugin())
    ctx._set_data(run_id, "raw_files", [[str(raw)]])

    records = ctx.get_data(run_id, "records")
    wave_pool = ctx.get_data(run_id, "wave_pool")

    assert isinstance(records, np.memmap)
    assert isinstance(wave_pool, np.memmap)
    bundle_key = get_records_bundle_cache_key(ctx, run_id)
    assert isinstance(ctx._results[(run_id, bundle_key)], RecordsBundleRef)
    np.testing.assert_array_equal(records["timestamp"], np.array([40_000]))
    np.testing.assert_array_equal(wave_pool, np.array([11, 12], dtype=np.uint16))

    ctx.clear_cache_for(run_id, "records", clear_disk=False, verbose=False)


def test_clear_records_or_wave_pool_also_clears_internal_bundle_cache(tmp_path):
    run_id = "run_001"

    for target in ("records", "wave_pool"):
        ctx = Context(storage_dir=str(tmp_path / target), config={"daq_adapter": "vx2730"})
        ctx.register(RecordsPlugin(), WavePoolPlugin())
        bundle_key = get_records_bundle_cache_key(ctx, run_id)
        ctx._set_data(run_id, "records", np.zeros(0, dtype=ctx.get_plugin("records").output_dtype))
        ctx._set_data(run_id, "wave_pool", np.zeros(0, dtype=np.uint16))
        ctx._set_data(
            run_id,
            bundle_key,
            RecordsBundle(
                records=np.zeros(0, dtype=ctx.get_plugin("records").output_dtype),
                wave_pool=np.zeros(0, dtype=np.uint16),
            ),
        )

        ctx.clear_cache_for(run_id, target, clear_disk=False, verbose=False)

        assert (run_id, bundle_key) not in ctx._results
