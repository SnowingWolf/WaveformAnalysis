from unittest.mock import patch

import numpy as np

from tests.utils import FakeContext
from waveform_analysis.core import Context
from waveform_analysis.core.plugins.builtin.cpu.records import (
    RecordsPlugin,
    WavePoolPlugin,
    get_records_bundle,
    get_records_bundle_cache_key,
)
from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import RecordsBundle


def _make_st_waveforms() -> np.ndarray:
    data = np.zeros(2, dtype=create_record_dtype(4))
    data["timestamp"] = [200, 100]
    data["board"] = [0, 0]
    data["channel"] = [1, 0]
    data["baseline"] = [10.0, 20.0]
    data["record_id"] = [2, 1]
    data["event_length"] = [4, 4]
    data["wave"] = np.array([[1, 2, 3, 4], [5, 6, 7, 8]], dtype=np.int16)
    return data


def test_records_depends_on_st_waveforms_for_vx2730():
    plugin = RecordsPlugin()
    ctx = FakeContext(config={"daq_adapter": "vx2730"})

    assert plugin.resolve_depends_on(ctx) == ["st_waveforms"]


def test_records_depends_on_raw_files_for_v1725():
    plugin = RecordsPlugin()
    ctx = FakeContext(config={"daq_adapter": "v1725"})

    assert plugin.resolve_depends_on(ctx) == ["raw_files"]


def test_wave_pool_depends_on_same_upstream_as_records():
    plugin = WavePoolPlugin()
    ctx = FakeContext(config={"daq_adapter": "vx2730"})

    assert plugin.resolve_depends_on(ctx) == ["st_waveforms"]


def test_get_records_bundle_reuses_st_waveforms_for_non_v1725():
    plugin = RecordsPlugin()
    st_waveforms = _make_st_waveforms()
    ctx = FakeContext(
        config={"daq_adapter": "vx2730"},
        data={"st_waveforms": st_waveforms},
        plugins={"records": plugin},
    )

    bundle = get_records_bundle(ctx, "run_001")

    np.testing.assert_array_equal(bundle.records["timestamp"], np.array([100, 200], dtype=np.int64))
    np.testing.assert_array_equal(bundle.records["record_id"], np.array([1, 2], dtype=np.int64))
    np.testing.assert_array_equal(
        bundle.wave_pool, np.array([5, 6, 7, 8, 1, 2, 3, 4], dtype=np.uint16)
    )


def test_wave_pool_plugin_reuses_shared_bundle_builder(tmp_path):
    run_id = "run_001"
    ctx = Context(storage_dir=str(tmp_path / "shared_bundle"), config={"daq_adapter": "vx2730"})
    ctx.register(RecordsPlugin(), WavePoolPlugin())
    ctx._set_data(run_id, "st_waveforms", _make_st_waveforms())

    fake_bundle = RecordsBundle(
        records=np.zeros(2, dtype=ctx.get_plugin("records").output_dtype),
        wave_pool=np.array([1, 2, 3, 4], dtype=np.uint16),
    )

    with patch(
        "waveform_analysis.core.plugins.builtin.cpu.records.build_records_from_st_waveforms_sharded",
        return_value=fake_bundle,
    ) as mocked:
        records = ctx.get_data(run_id, "records")
        wave_pool = ctx.get_data(run_id, "wave_pool")

    assert mocked.call_count == 1
    np.testing.assert_array_equal(records, fake_bundle.records)
    np.testing.assert_array_equal(wave_pool, fake_bundle.wave_pool)


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
