import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import ThresholdHitPlugin
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import HIT_DTYPE
from waveform_analysis.core.processing.dtypes import create_record_dtype


def _make_st_waveforms(n_events=1, wave_len=64):
    dtype = create_record_dtype(wave_len)
    data = np.zeros(n_events, dtype=dtype)
    data["baseline"] = 100.0
    data["timestamp"] = 1_000_000
    data["channel"] = 0
    data["event_length"] = wave_len
    data["wave"] = 100
    return data


def test_threshold_hit_dtype_matches_advanced_peak_dtype():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=0)
    ctx = DummyContext({"threshold": 10.0}, {"st_waveforms": st})

    result = plugin.compute(ctx, "run_001")

    assert result.dtype == HIT_DTYPE
    assert len(result) == 0


def test_threshold_hit_single_waveform_multiple_hits():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    st[0]["wave"][5:8] = 80
    st[0]["wave"][15:18] = 70

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "polarity": "negative",
            "left_extension": 0,
            "right_extension": 0,
            "sampling_interval_ns": 2.0,
        },
        {"st_waveforms": st},
    )

    result = plugin.compute(ctx, "run_001")

    assert len(result) == 2
    assert np.all(result["record_index"] == 0)
    assert np.all(result["channel"] == 0)


def test_threshold_hit_no_event_length_truncation():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    st[0]["event_length"] = 8
    st[0]["wave"][20:23] = 75

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "polarity": "negative",
            "left_extension": 0,
            "right_extension": 0,
        },
        {"st_waveforms": st},
    )

    result = plugin.compute(ctx, "run_001")

    assert len(result) == 1
    assert int(result[0]["hit_sample_idx"]) >= 20


def test_threshold_hit_empty_input():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=0, wave_len=16)
    ctx = DummyContext({}, {"st_waveforms": st})

    result = plugin.compute(ctx, "run_001")

    assert len(result) == 0
    assert result.dtype == HIT_DTYPE


def test_threshold_hit_polarity_positive_negative():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)

    st_neg = st.copy()
    st_neg[0]["wave"][10:13] = 80
    ctx_neg = DummyContext({"threshold": 10.0, "polarity": "negative"}, {"st_waveforms": st_neg})
    result_neg = plugin.compute(ctx_neg, "run_001")

    st_pos = st.copy()
    st_pos[0]["baseline"] = 0.0
    st_pos[0]["wave"][10:13] = 20
    ctx_pos = DummyContext({"threshold": 10.0, "polarity": "positive"}, {"st_waveforms": st_pos})
    result_pos = plugin.compute(ctx_pos, "run_001")

    assert len(result_neg) == 1
    assert len(result_pos) == 1


def test_threshold_hit_extension_applied():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    st[0]["wave"][10:12] = 80

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "polarity": "negative",
            "left_extension": 2,
            "right_extension": 3,
        },
        {"st_waveforms": st},
    )

    result = plugin.compute(ctx, "run_001")

    assert len(result) == 1
    assert float(result[0]["hit_left_sample_idx"]) == 8.0
    assert float(result[0]["hit_right_sample_idx"]) == 15.0


def test_threshold_hit_use_filtered_branch():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    filtered = _make_st_waveforms(n_events=1, wave_len=32)
    filtered[0]["wave"][12:15] = 70

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "use_filtered": True,
            "polarity": "negative",
        },
        {
            "st_waveforms": st,
            "filtered_waveforms": filtered,
        },
    )

    result = plugin.compute(ctx, "run_001")

    assert len(result) == 1
    assert int(result[0]["hit_sample_idx"]) >= 12
