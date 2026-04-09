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
from waveform_analysis.core.processing.records_builder import (
    RECORDS_DTYPE,
    build_records_from_st_waveforms,
)


def _make_st_waveforms(n_events=1, wave_len=64):
    dtype = create_record_dtype(wave_len)
    data = np.zeros(n_events, dtype=dtype)
    data["baseline"] = 100.0
    data["timestamp"] = 1_000_000
    data["record_id"] = np.arange(n_events, dtype=np.int64)
    data["channel"] = 0
    data["dt"] = 2
    data["event_length"] = wave_len
    data["wave"] = 100
    return data


def _make_records_view():
    records = np.zeros(1, dtype=RECORDS_DTYPE)
    records["baseline"] = 100.0
    records["timestamp"] = 123_456
    records["board"] = 5
    records["channel"] = 2
    records["dt"] = 2
    records["event_length"] = 8
    records["wave_offset"] = 0
    wave_pool = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)
    return RecordsView(records, wave_pool)


def _compute_threshold_hits(plugin, ctx, run_id="run_001"):
    source = ctx.get_config(plugin, "wave_source")
    use_filtered = bool(ctx.get_config(plugin, "use_filtered"))
    if source == "records":
        return plugin.compute(ctx, run_id)

    waveform_data = (
        ctx.get_data(run_id, "filtered_waveforms")
        if use_filtered
        else ctx.get_data(run_id, "st_waveforms")
    )
    if waveform_data is None:
        return plugin.compute(ctx, run_id)

    if (
        "dt" not in (waveform_data.dtype.names or ())
        and ctx.get_config(plugin, "dt") is None
        and ctx.config.get("sampling_interval_ns") is None
    ):
        return plugin.compute(ctx, run_id)

    bundle_input = waveform_data
    names = bundle_input.dtype.names or ()
    if "board" not in names:
        augmented_dtype = np.dtype(bundle_input.dtype.descr + [("board", "i2")])
        augmented = np.zeros(bundle_input.shape, dtype=augmented_dtype)
        for name in names:
            augmented[name] = bundle_input[name]
        augmented["board"] = 0
        bundle_input = augmented

    default_dt = (
        int(bundle_input["dt"][0])
        if "dt" in (bundle_input.dtype.names or ()) and len(bundle_input)
        else int(ctx.get_config(plugin, "dt") or 1)
    )
    bundle = build_records_from_st_waveforms(bundle_input, default_dt_ns=default_dt)
    with patch(
        "waveform_analysis.core.plugins.builtin.cpu.records.get_records_bundle", return_value=bundle
    ):
        return plugin.compute(ctx, run_id)


def test_threshold_hit_dtype_matches_advanced_peak_dtype():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=0)
    ctx = DummyContext({"threshold": 10.0}, {"st_waveforms": st})

    result = _compute_threshold_hits(plugin, ctx)

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
            "left_extension": 0,
            "right_extension": 0,
            "dt": 2,
        },
        {"st_waveforms": st},
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 2
    assert np.all(result["record_id"] == 0)
    assert np.all(result["channel"] == 0)
    assert np.all(result["width"] == 3.0)
    assert np.all(result["dt"] == 2)
    np.testing.assert_array_equal(result["edge_start"], np.array([5, 15], dtype=np.int32))
    np.testing.assert_array_equal(result["edge_end"], np.array([8, 18], dtype=np.int32))


def test_threshold_hit_no_event_length_truncation():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    st[0]["event_length"] = 8
    st[0]["wave"][20:23] = 75

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "left_extension": 0,
            "right_extension": 0,
        },
        {"st_waveforms": st},
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 1
    assert int(result[0]["position"]) >= 20


def test_threshold_hit_empty_input():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=0, wave_len=16)
    ctx = DummyContext({}, {"st_waveforms": st})

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 0
    assert result.dtype == THRESHOLD_HIT_DTYPE


def test_threshold_hit_extension_applied():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    st[0]["wave"][10:12] = 80

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "left_extension": 2,
            "right_extension": 3,
        },
        {"st_waveforms": st},
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 1
    assert int(result[0]["edge_start"]) == 8
    assert int(result[0]["edge_end"]) == 15
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
        },
        {
            "st_waveforms": st,
            "filtered_waveforms": filtered,
        },
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 1
    assert int(result[0]["position"]) >= 12


def test_threshold_hit_wave_source_records_depends_on_records_and_wave_pool():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext({"wave_source": "records", "use_filtered": True}, {})
    assert plugin.resolve_depends_on(ctx) == ["records", "wave_pool"]


def test_threshold_hit_reads_records_view_when_wave_source_records():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
            "left_extension": 0,
            "right_extension": 0,
            "dt": 2,
        },
        {},
    )
    rv = _make_records_view()

    with patch("waveform_analysis.core.records_view", return_value=rv) as mocked:
        result = _compute_threshold_hits(plugin, ctx)

    assert mocked.call_count == 1
    assert len(result) == 1
    assert int(result[0]["board"]) == 5
    assert int(result[0]["channel"]) == 2
    assert int(result[0]["record_id"]) == 0
    assert int(result[0]["edge_start"]) == 2
    assert int(result[0]["edge_end"]) == 6


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
        result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 0
    assert result.dtype == THRESHOLD_HIT_DTYPE


def test_threshold_hit_rejects_boardless_channel_config_keys():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    st[0]["board"] = 0
    st[0]["channel"] = 1
    st[0]["wave"][6:9] = 80

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "channel_config": {
                "run_001": {
                    "1": {"threshold": 5.0},
                }
            },
        },
        {"st_waveforms": st},
    )

    with pytest.raises(ValueError, match="Invalid channel key"):
        _compute_threshold_hits(plugin, ctx)


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
            "channel_config": {
                "run_001": {
                    "0:0": {"threshold": 25.0},
                    "0:1": {"threshold": 5.0},
                }
            },
        },
        {"st_waveforms": st},
    )

    result = _compute_threshold_hits(plugin, ctx)

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
            "left_extension": 0,
            "right_extension": 0,
        },
        {"st_waveforms": st},
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 2
    assert {(int(row["board"]), int(row["channel"])) for row in result} == {(0, 1), (1, 1)}


def test_threshold_hit_computes_rise_time_and_fall_time_from_threshold_window():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=16)
    st[0]["wave"][4:9] = [80, 70, 60, 70, 80]

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "left_extension": 0,
            "right_extension": 0,
            "dt": 2,
        },
        {"st_waveforms": st},
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 1
    assert float(result[0]["rise_time"]) == 4.0
    assert float(result[0]["fall_time"]) == 4.0


def test_threshold_hit_rise_fall_time_use_threshold_region_not_extensions():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=16)
    st[0]["wave"][4:9] = [80, 70, 60, 70, 80]

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "left_extension": 2,
            "right_extension": 3,
            "dt": 2,
        },
        {"st_waveforms": st},
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 1
    assert int(result[0]["edge_start"]) == 2
    assert int(result[0]["edge_end"]) == 12
    assert float(result[0]["rise_time"]) == 4.0
    assert float(result[0]["fall_time"]) == 4.0


def test_threshold_hit_accepts_deprecated_sampling_interval_ns_with_warning():
    plugin = ThresholdHitPlugin()
    dtype = np.dtype(
        [
            ("baseline", "f8"),
            ("timestamp", "i8"),
            ("record_id", "i8"),
            ("channel", "i2"),
            ("event_length", "i4"),
            ("wave", "i2", (16,)),
        ]
    )
    st = np.zeros(1, dtype=dtype)
    st[0]["baseline"] = 100.0
    st[0]["timestamp"] = 1_000_000
    st[0]["record_id"] = 0
    st[0]["channel"] = 0
    st[0]["event_length"] = 16
    st[0]["wave"] = 100
    st[0]["wave"][4:7] = 80

    ctx = DummyContext(
        {"threshold": 10.0, "sampling_interval_ns": 2.0},
        {"st_waveforms": st},
    )

    with pytest.warns(DeprecationWarning, match="sampling_interval_ns"):
        result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 1
    assert int(result[0]["dt"]) == 2


def test_threshold_hit_requires_dt_when_input_lacks_dt_and_config_missing():
    plugin = ThresholdHitPlugin()
    dtype = np.dtype(
        [
            ("baseline", "f8"),
            ("timestamp", "i8"),
            ("record_id", "i8"),
            ("channel", "i2"),
            ("event_length", "i4"),
            ("wave", "i2", (16,)),
        ]
    )
    st = np.zeros(1, dtype=dtype)
    st[0]["baseline"] = 100.0
    st[0]["timestamp"] = 1_000_000
    st[0]["record_id"] = 0
    st[0]["channel"] = 0
    st[0]["event_length"] = 16
    st[0]["wave"] = 100
    st[0]["wave"][4:7] = 80

    ctx = DummyContext({"threshold": 10.0}, {"st_waveforms": st})

    with pytest.raises(ValueError, match="missing required field 'dt'"):
        _compute_threshold_hits(plugin, ctx)
