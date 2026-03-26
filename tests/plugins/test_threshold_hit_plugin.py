from unittest.mock import patch

import numpy as np
import pytest

from tests.utils import DummyContext
from waveform_analysis.core.data.records_view import RecordsView
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import (
    THRESHOLD_HIT_DTYPE,
    ThresholdHitPlugin,
)
from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import RECORDS_DTYPE


def _make_st_waveforms(n_events=1, wave_len=64):
    dtype = create_record_dtype(wave_len)
    data = np.zeros(n_events, dtype=dtype)
    data["baseline"] = 100.0
    data["timestamp"] = 1_000_000
    data["record_id"] = np.arange(n_events, dtype=np.int64)
    data["channel"] = 0
    data["event_length"] = wave_len
    data["wave"] = 100
    return data


def _make_records_view():
    records = np.zeros(1, dtype=RECORDS_DTYPE)
    records["baseline"] = 100.0
    records["timestamp"] = 123_456
    records["board"] = 5
    records["channel"] = 2
    records["event_length"] = 8
    records["wave_offset"] = 0
    wave_pool = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)
    return RecordsView(records, wave_pool)


def test_threshold_hit_dtype_matches_advanced_peak_dtype():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=0)
    ctx = DummyContext({"threshold": 10.0}, {"st_waveforms": st})

    result = plugin.compute(ctx, "run_001")

    assert result.dtype == THRESHOLD_HIT_DTYPE
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
    assert np.all(result["record_id"] == 0)
    assert np.all(result["channel"] == 0)
    assert np.all(result["width"] == 3.0)


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
    assert int(result[0]["position"]) >= 20


def test_threshold_hit_empty_input():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=0, wave_len=16)
    ctx = DummyContext({}, {"st_waveforms": st})

    result = plugin.compute(ctx, "run_001")

    assert len(result) == 0
    assert result.dtype == THRESHOLD_HIT_DTYPE


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


def test_threshold_hit_uses_st_waveforms_polarity_field():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    st[0]["polarity"] = "positive"
    st[0]["wave"][10:13] = 120

    ctx = DummyContext({"threshold": 10.0, "polarity": "negative"}, {"st_waveforms": st})
    result = plugin.compute(ctx, "run_001")

    assert len(result) == 1


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
    assert float(result[0]["edge_start"]) == 8.0
    assert float(result[0]["edge_end"]) == 15.0
    assert float(result[0]["width"]) == 7.0


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
    assert int(result[0]["position"]) >= 12


def test_threshold_hit_wave_source_records_depends_on_records():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext({"wave_source": "records", "use_filtered": True}, {})
    assert plugin.resolve_depends_on(ctx) == ["records"]


def test_threshold_hit_reads_records_view_when_wave_source_records():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
            "polarity": "negative",
            "left_extension": 0,
            "right_extension": 0,
            "sampling_interval_ns": 2.0,
        },
        {},
    )
    rv = _make_records_view()

    with patch("waveform_analysis.core.records_view", return_value=rv) as mocked:
        result = plugin.compute(ctx, "run_001")

    assert mocked.call_count == 1
    assert len(result) == 1
    assert int(result[0]["board"]) == 5
    assert int(result[0]["channel"]) == 2
    assert int(result[0]["record_id"]) == 0


def test_threshold_hit_records_polarity_field_overrides_config():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
            "polarity": "negative",
            "left_extension": 0,
            "right_extension": 0,
            "sampling_interval_ns": 2.0,
        },
        {},
    )
    rv = _make_records_view()
    rv.records["polarity"] = ["positive"]
    rv.wave_pool = np.array([100, 100, 120, 120, 120, 120, 100, 100], dtype=np.uint16)

    with patch("waveform_analysis.core.records_view", return_value=rv):
        result = plugin.compute(ctx, "run_001")

    assert len(result) == 1


def test_threshold_hit_records_negative_polarity_uses_normalized_signal():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
            "polarity": "positive",
            "left_extension": 0,
            "right_extension": 0,
            "sampling_interval_ns": 2.0,
        },
        {},
    )
    rv = _make_records_view()
    rv.records["polarity"] = ["negative"]

    with patch("waveform_analysis.core.records_view", return_value=rv):
        result = plugin.compute(ctx, "run_001")

    assert len(result) == 1


def test_threshold_hit_records_unknown_polarity_falls_back_to_config():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
            "polarity": "negative",
            "left_extension": 0,
            "right_extension": 0,
            "sampling_interval_ns": 2.0,
        },
        {},
    )
    rv = _make_records_view()
    rv.records["polarity"] = ["unknown"]

    with patch("waveform_analysis.core.records_view", return_value=rv):
        result = plugin.compute(ctx, "run_001")

    assert len(result) == 1


def test_threshold_hit_records_empty_returns_empty():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
        },
        {},
    )
    empty_records = np.zeros(0, dtype=RECORDS_DTYPE)
    rv = RecordsView(empty_records, np.zeros(0, dtype=np.uint16))

    with patch("waveform_analysis.core.records_view", return_value=rv):
        result = plugin.compute(ctx, "run_001")

    assert len(result) == 0
    assert result.dtype == THRESHOLD_HIT_DTYPE


def test_threshold_hit_channel_config_overrides_polarity():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    st[0]["board"] = 0
    st[0]["channel"] = 1
    st[0]["baseline"] = 0.0
    st[0]["wave"][10:13] = 20

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "polarity": "negative",
            "channel_config": {
                "run_001": {
                    "channels": {
                        "0:1": {
                            "polarity": "positive",
                        }
                    }
                }
            },
        },
        {"st_waveforms": st},
    )

    result = plugin.compute(ctx, "run_001")
    assert len(result) == 1
    assert int(result[0]["channel"]) == 1


def test_threshold_hit_rejects_boardless_channel_config_keys():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    st[0]["board"] = 0
    st[0]["channel"] = 1
    st[0]["wave"][6:9] = 80

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "polarity": "negative",
            "channel_config": {
                "run_001": {
                    "1": {"threshold": 5.0},
                }
            },
        },
        {"st_waveforms": st},
    )

    with pytest.raises(ValueError, match="Invalid channel key"):
        plugin.compute(ctx, "run_001")


def test_threshold_hit_channel_config_overrides_threshold_per_channel():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=2, wave_len=32)
    st[0]["board"] = 0
    st[0]["channel"] = 0
    st[1]["board"] = 0
    st[1]["channel"] = 1
    st[0]["wave"][5:8] = 88
    st[1]["wave"][6:9] = 88

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "polarity": "negative",
            "channel_config": {
                "run_001": {
                    "0:0": {"threshold": 25.0},
                    "0:1": {"threshold": 5.0},
                }
            },
        },
        {"st_waveforms": st},
    )

    result = plugin.compute(ctx, "run_001")

    assert len(result) == 1
    assert set(result["channel"].tolist()) == {1}


def test_threshold_hit_does_not_merge_same_channel_across_boards():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=2, wave_len=32)
    st[0]["board"] = 0
    st[0]["channel"] = 1
    st[1]["board"] = 1
    st[1]["channel"] = 1
    st[0]["wave"][5:8] = 80
    st[1]["wave"][15:18] = 80

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

    assert len(result) == 2
    assert {(int(row["board"]), int(row["channel"])) for row in result} == {(0, 1), (1, 1)}
