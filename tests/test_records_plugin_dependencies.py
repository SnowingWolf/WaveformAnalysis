import numpy as np

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.cpu.records import RecordsPlugin, get_records_bundle
from waveform_analysis.core.processing.dtypes import create_record_dtype


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
