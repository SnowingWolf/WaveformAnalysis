import numpy as np

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.records import RecordsPlugin
from waveform_analysis.core.plugins.builtin.records._compute import (
    get_records_bundle_cache_key,
)
from waveform_analysis.core.plugins.builtin.wave_pool import WavePoolPlugin
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE
from waveform_analysis.core.processing.records_builder import RecordsBundle


def test_wave_pool_returns_pool_from_cached_bundle():
    plugin = WavePoolPlugin()
    bundle = RecordsBundle(
        records=np.zeros(1, dtype=RECORDS_DTYPE),
        wave_pool=np.array([1, 2, 3], dtype=np.uint16),
    )
    ctx = FakeContext(config={"daq_adapter": "vx2730"}, plugins={"wave_pool": plugin})
    cache_key = get_records_bundle_cache_key(ctx, "run_001")
    ctx._set_data("run_001", cache_key, bundle)

    out = plugin.compute(ctx, "run_001")

    assert out.dtype == np.uint16
    np.testing.assert_array_equal(out, np.array([1, 2, 3], dtype=np.uint16))


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
