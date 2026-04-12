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
from waveform_analysis.core.processing.records_builder import RecordsBundle


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


def test_wave_pool_depends_on_same_upstream_as_records():
    plugin = WavePoolPlugin()
    ctx = FakeContext(config={"daq_adapter": "vx2730"})

    assert plugin.resolve_depends_on(ctx) == ["raw_files"]


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
