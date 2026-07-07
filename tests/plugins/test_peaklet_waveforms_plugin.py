import numpy as np
import pytest

from tests.plugins.test_peaklets_plugin import _make_hit, make_peaklet_context
from tests.utils import DummyContext, make_records
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
    PEAKLET_WAVEFORMS_DTYPE,
    PeakletComponentsPlugin,
    PeakletPlugin,
    PeakletWaveformPlugin,
    PeakletWaveformPoolPlugin,
)
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
)
from waveform_analysis.core.plugins.builtin.peaks.peaklets import (
    PEAKLET_COMPONENTS_DTYPE,
    PEAKLET_DTYPE,
    _build_hmc_csr,
    _build_peaklet_component_csr,
)


def _compute_peaklets_and_components(ctx):
    peaklets = PeakletPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklets"] = peaklets
    components = PeakletComponentsPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklet_components"] = components
    return peaklets, components


def _make_cross_record_waveform_context(*, config=None):
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=3, edge_end=5),
            _make_hit(record_id=1, board=0, channel=0, edge_start=2, edge_end=4),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    merged = np.zeros(1, dtype=HIT_MERGED_DTYPE)
    merged[0]["merged_id"] = 0
    merged[0]["time_start"] = 6000
    merged[0]["time_end"] = 12000
    merged[0]["sample_start"] = -1
    merged[0]["sample_end"] = -1
    merged[0]["dt"] = 2
    merged[0]["record_id"] = 0
    merged[0]["component_count"] = 2
    merged[0]["is_single_record"] = False

    hit_merged_components = np.array(
        [(0, 0), (0, 1)],
        dtype=HIT_MERGED_COMPONENTS_DTYPE,
    )
    peaklets = np.array(
        [(6000, 12000, 9000, 2, 1, 0, 1)],
        dtype=PEAKLET_DTYPE,
    )
    components = np.array([(0, 0)], dtype=PEAKLET_COMPONENTS_DTYPE)

    records = make_records(n_records=2, event_length=10, baseline=100.0, dt=2)
    records["timestamp"] = [0, 4000]
    records["polarity"] = "negative"
    wave_pool = np.array(
        [
            100,
            100,
            100,
            80,
            70,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            60,
            50,
            100,
            100,
            100,
            100,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    return DummyContext(
        {
            "use_filtered": False,
            "debug_numba": True,
            "log_waveform_diagnostics": False,
            **(config or {}),
        },
        {
            "hit_threshold": hits,
            "hit_merged": merged,
            "hit_merged_components": hit_merged_components,
            "peaklets": peaklets,
            "peaklet_components": components,
            "records": records,
            "wave_pool": wave_pool,
        },
    )


def test_peaklet_waveforms_cross_record_uses_component_hits_from_each_record():
    ctx = _make_cross_record_waveform_context()

    waveforms = PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    assert waveforms.dtype == PEAKLET_WAVEFORMS_DTYPE
    assert len(waveforms) == 1
    assert int(waveforms[0]["peak_id"]) == 0
    assert int(waveforms[0]["time_start"]) == 6000
    assert int(waveforms[0]["time_end"]) == 12000
    assert int(waveforms[0]["dt"]) == 2
    assert int(waveforms[0]["wave_offset"]) == 0
    assert int(waveforms[0]["wave_length"]) == 3
    np.testing.assert_allclose(pool, np.array([20.0, 70.0, 50.0], dtype=np.float32))


def test_peaklet_waveforms_cross_record_mixed_dt_raises_from_numba_path():
    ctx = _make_cross_record_waveform_context()
    ctx._data["records"]["dt"] = [2, 4]

    with pytest.raises(ValueError, match="mixed dt"):
        PeakletWaveformPlugin().compute(ctx, "run_001")


def test_peaklet_waveforms_debug_numba_raises_instead_of_fallback():
    ctx = _make_cross_record_waveform_context()
    records = ctx._data["records"]
    ctx._data["records"] = records[[name for name in records.dtype.names if name != "dt"]]

    with pytest.raises(KeyError, match="records dt"):
        PeakletWaveformPlugin().compute(ctx, "run_001")


def test_peaklet_waveform_csr_helpers_mark_empty_groups():
    components = np.array([(0, 2), (2, 3), (0, 1)], dtype=PEAKLET_COMPONENTS_DTYPE)
    grouped_merged, starts, ends = _build_peaklet_component_csr(components, 4)

    np.testing.assert_array_equal(grouped_merged, np.array([2, 1, 3], dtype=np.int64))
    np.testing.assert_array_equal(starts, np.array([0, -1, 2, -1], dtype=np.int64))
    np.testing.assert_array_equal(ends, np.array([2, -1, 3, -1], dtype=np.int64))

    hmc = np.array([(1, 4), (0, 2), (1, 5)], dtype=HIT_MERGED_COMPONENTS_DTYPE)
    grouped_hits, hmc_starts, hmc_ends = _build_hmc_csr(hmc, 4)

    np.testing.assert_array_equal(grouped_hits, np.array([2, 4, 5], dtype=np.int64))
    np.testing.assert_array_equal(hmc_starts, np.array([0, 1, -1, -1], dtype=np.int64))
    np.testing.assert_array_equal(hmc_ends, np.array([1, 3, -1, -1], dtype=np.int64))


def test_peaklet_waveforms_align_and_sum_hit_merged_absolute_windows():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=3, edge_end=5),
            _make_hit(record_id=1, board=0, channel=1, edge_start=4, edge_end=6),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    wave_pool = np.array(
        [
            100,
            100,
            100,
            80,
            70,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            90,
            80,
            100,
            100,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    ctx = make_peaklet_context(hits, wave_pool)
    _compute_peaklets_and_components(ctx)

    waveforms = PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    assert waveforms.dtype == PEAKLET_WAVEFORMS_DTYPE
    assert len(waveforms) == 1
    assert int(waveforms[0]["time_start"]) == 6000
    assert int(waveforms[0]["time_end"]) == 12000
    assert int(waveforms[0]["dt"]) == 2
    assert int(waveforms[0]["wave_offset"]) == 0
    assert int(waveforms[0]["wave_length"]) == 3
    np.testing.assert_allclose(pool, np.array([20.0, 40.0, 20.0], dtype=np.float32))


def test_peaklet_waveforms_reject_components_misaligned_with_peaklets():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=3),
            _make_hit(record_id=1, board=0, channel=1, edge_start=1, edge_end=3),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 100, dtype=np.uint16))
    peaklets, components = _compute_peaklets_and_components(ctx)
    assert int(peaklets[0]["component_count"]) == 2
    ctx._data["peaklet_components"] = components[:1]

    with pytest.raises(ValueError, match="inconsistent with peaklets"):
        PeakletWaveformPlugin().compute(ctx, "run_001")


def test_peaklet_waveforms_apply_positive_and_negative_polarity_and_clip_negative_signal():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=4),
            _make_hit(record_id=1, board=0, channel=1, edge_start=1, edge_end=4),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    wave_pool = np.array(
        [
            100,
            80,
            130,
            70,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            120,
            80,
            140,
            100,
            100,
            100,
            100,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    ctx = make_peaklet_context(hits, wave_pool)
    ctx._data["records"]["polarity"] = ["negative", "positive"]
    _compute_peaklets_and_components(ctx)

    PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    np.testing.assert_allclose(pool, np.array([40.0, 0.0, 70.0], dtype=np.float32))


def test_peaklet_waveforms_use_filtered_pool_when_configured():
    hits = np.array(
        [_make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=3)],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(10, 100, dtype=np.uint16), use_filtered=True)
    ctx._data["wave_pool_filtered"] = np.array(
        [100, 50, 40, 100, 100, 100, 100, 100, 100, 100], dtype=np.uint16
    )
    _compute_peaklets_and_components(ctx)

    PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    np.testing.assert_allclose(pool, np.array([50.0, 60.0], dtype=np.float32))


def test_peaklet_waveforms_mixed_dt_in_one_peaklet_raises():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=3, dt=2),
            _make_hit(record_id=1, board=0, channel=1, edge_start=1, edge_end=3, dt=4),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 90, dtype=np.uint16), time_window_ns=10.0)
    ctx._data["records"]["dt"] = [2, 4]
    _compute_peaklets_and_components(ctx)

    with pytest.raises(ValueError, match="mixed dt"):
        PeakletWaveformPlugin().compute(ctx, "run_001")


def test_peaklet_waveforms_empty_peaklets_return_empty_index_and_pool():
    ctx = make_peaklet_context(
        np.zeros(0, dtype=THRESHOLD_HIT_DTYPE),
        np.zeros(0, dtype=np.uint16),
    )
    ctx._data["peaklets"] = PeakletPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklet_components"] = PeakletComponentsPlugin().compute_array(ctx, "run_001")

    waveforms = PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    assert len(waveforms) == 0
    assert waveforms.dtype == PEAKLET_WAVEFORMS_DTYPE
    assert pool.dtype == np.float32
    assert len(pool) == 0
