import numpy as np
import pytest

from tests.plugins.test_peaklets_plugin import _make_hit, make_peaklet_context
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
    PEAKLET_WAVEFORMS_DTYPE,
    PeakletComponentsPlugin,
    PeakletPlugin,
    PeakletWaveformPlugin,
    PeakletWaveformPoolPlugin,
)


def _compute_peaklets_and_components(ctx):
    peaklets = PeakletPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklets"] = peaklets
    components = PeakletComponentsPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklet_components"] = components
    return peaklets, components


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
