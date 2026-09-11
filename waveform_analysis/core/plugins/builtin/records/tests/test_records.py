import numpy as np
import pytest

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.records import RecordsPlugin
from waveform_analysis.core.plugins.builtin.records._compute import (
    get_records_bundle,
    get_records_bundle_cache_key,
)
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE
from waveform_analysis.core.processing.records_builder import RecordsBundle


def test_records_dtype_and_empty_compute():
    plugin = RecordsPlugin()
    bundle = RecordsBundle(
        records=np.zeros(0, dtype=RECORDS_DTYPE),
        wave_pool=np.zeros(0, dtype=np.uint16),
    )
    ctx = FakeContext(config={"daq_adapter": "vx2730"}, plugins={"records": plugin})
    cache_key = get_records_bundle_cache_key(ctx, "run_001")
    ctx._set_data("run_001", cache_key, bundle)

    out = plugin.compute(ctx, "run_001")

    assert out.dtype == RECORDS_DTYPE
    assert len(out) == 0


def test_records_compute_returns_cached_bundle_records():
    plugin = RecordsPlugin()
    records = np.zeros(2, dtype=RECORDS_DTYPE)
    records["timestamp"] = np.array([1000, 2000], dtype=np.int64)
    bundle = RecordsBundle(records=records, wave_pool=np.zeros(0, dtype=np.uint16))
    ctx = FakeContext(config={"daq_adapter": "vx2730"}, plugins={"records": plugin})
    cache_key = get_records_bundle_cache_key(ctx, "run_001")
    ctx._set_data("run_001", cache_key, bundle)

    out = plugin.compute(ctx, "run_001")

    np.testing.assert_array_equal(out["timestamp"], records["timestamp"])


def test_records_depends_on_raw_files_for_vx2730():
    plugin = RecordsPlugin()
    ctx = FakeContext(config={"daq_adapter": "vx2730"}, plugins={"records": plugin})

    assert plugin.resolve_depends_on(ctx) == ["raw_files"]


def test_records_can_depend_on_st_waveforms_for_vx2730():
    plugin = RecordsPlugin()
    ctx = FakeContext(
        config={"daq_adapter": "vx2730", "records": {"input_source": "st_waveforms"}},
        plugins={"records": plugin},
    )

    assert plugin.resolve_depends_on(ctx) == ["st_waveforms"]


def test_records_rejects_st_waveforms_source_for_v1725():
    plugin = RecordsPlugin()
    ctx = FakeContext(
        config={"daq_adapter": "v1725", "records": {"input_source": "st_waveforms"}},
        plugins={"records": plugin},
    )

    with pytest.raises(ValueError, match="not supported for v1725"):
        plugin.resolve_depends_on(ctx)


def test_get_records_bundle_returns_cached_bundle():
    plugin = RecordsPlugin()
    fake_bundle = RecordsBundle(
        records=np.zeros(2, dtype=RECORDS_DTYPE),
        wave_pool=np.array([1, 2, 3, 4], dtype=np.uint16),
    )
    ctx = FakeContext(config={"daq_adapter": "vx2730"}, plugins={"records": plugin})
    cache_key = get_records_bundle_cache_key(ctx, "run_001")
    ctx._set_data("run_001", cache_key, fake_bundle)

    assert get_records_bundle(ctx, "run_001") is fake_bundle
