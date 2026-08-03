from unittest.mock import patch

import numpy as np
import pytest

from tests.utils import DummyContext
from waveform_analysis.core.data.records_view import RecordsView
from waveform_analysis.core.plugins.builtin.cpu.records_asymmetry import (
    RecordsAsymmetryMaskPlugin,
)
from waveform_analysis.core.plugins.builtin.hit import hit_finder as hit_finder_module
from waveform_analysis.core.plugins.builtin.hit.hit_finder import (
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


def _make_many_records_view(n_records=4):
    records = np.zeros(n_records, dtype=RECORDS_DTYPE)
    records["baseline"] = 100.0
    records["timestamp"] = np.arange(n_records, dtype=np.int64) * 1_000_000
    records["board"] = np.arange(n_records, dtype=np.int16) % 2
    records["channel"] = np.arange(n_records, dtype=np.int16)
    records["dt"] = 2
    records["event_length"] = 8
    records["wave_offset"] = np.arange(n_records, dtype=np.int64) * 8
    records["record_id"] = np.arange(n_records, dtype=np.int64)
    wave_pool = np.tile(
        np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16),
        n_records,
    )
    return RecordsView(records, wave_pool)


def _make_asymmetry_records_view():
    records = np.zeros(2, dtype=RECORDS_DTYPE)
    records["baseline"] = 100.0
    records["timestamp"] = np.array([123_456, 223_456], dtype=np.int64)
    records["board"] = 5
    records["channel"] = np.array([2, 3], dtype=np.int16)
    records["dt"] = 2
    records["event_length"] = 8
    records["wave_offset"] = np.array([0, 8], dtype=np.int64)
    records["record_id"] = np.array([0, 1], dtype=np.int64)
    wave_pool = np.array(
        [
            100,
            100,
            80,
            80,
            100,
            100,
            100,
            100,
            100,
            130,
            80,
            80,
            100,
            100,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    return RecordsView(records, wave_pool)


def _compute_threshold_hits(plugin, ctx, run_id="run_001"):
    source = ctx.get_config(plugin, "wave_source")
    use_filtered = bool(ctx.get_config(plugin, "use_filtered"))
    if source == "records":
        return plugin.compute_array(ctx, run_id)

    waveform_data = (
        ctx.get_data(run_id, "filtered_waveforms")
        if use_filtered
        else ctx.get_data(run_id, "st_waveforms")
    )
    if waveform_data is None:
        return plugin.compute_array(ctx, run_id)

    if (
        "dt" not in (waveform_data.dtype.names or ())
        and ctx.get_config(plugin, "dt") is None
        and ctx.config.get("sampling_interval_ns") is None
    ):
        return plugin.compute_array(ctx, run_id)

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
        return plugin.compute_array(ctx, run_id)


def test_threshold_hit_dtype_matches_advanced_peak_dtype():
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=0)
    ctx = DummyContext({"threshold": 10.0}, {"st_waveforms": st})

    result = _compute_threshold_hits(plugin, ctx)

    assert result.dtype == THRESHOLD_HIT_DTYPE
    assert set(result.dtype.names) == {
        "position",
        "edge_start",
        "edge_end",
        "width",
        "dt",
        "timestamp",
        "board",
        "channel",
        "record_id",
    }
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
    """Test wave_source='filtered_waveforms' selects filtered data"""
    plugin = ThresholdHitPlugin()
    st = _make_st_waveforms(n_events=1, wave_len=32)
    filtered = _make_st_waveforms(n_events=1, wave_len=32)
    filtered[0]["wave"][12:15] = 70

    ctx = DummyContext(
        {
            "threshold": 10.0,
            "wave_source": "filtered_waveforms",
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
    ctx = DummyContext({"wave_source": "records", "asymmetry_cut_enabled": False}, {})
    assert plugin.resolve_depends_on(ctx) == ["records", "wave_pool"]


def test_threshold_hit_records_source_enables_asymmetry_cut_by_default():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext({"wave_source": "records"}, {})

    assert ctx.get_config(plugin, "asymmetry_cut_enabled") is True
    assert plugin.resolve_depends_on(ctx) == [
        "records",
        "wave_pool",
        "records_asymmetry_mask",
    ]


def test_threshold_hit_asymmetry_cut_depends_on_mask_for_records_source():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "asymmetry_cut_enabled": True,
        },
        {},
    )

    assert plugin.resolve_depends_on(ctx) == [
        "records",
        "wave_pool",
        "records_asymmetry_mask",
    ]


def test_threshold_hit_channel_role_cut_depends_on_detector_mask_for_records_source():
    plugin = ThresholdHitPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "asymmetry_cut_enabled": True,
            "channel_role_cut_enabled": True,
        },
        {},
    )

    assert plugin.resolve_depends_on(ctx) == [
        "records",
        "wave_pool",
        "records_asymmetry_mask",
        "records_detector_mask",
    ]


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
        {
            "records": _make_records_view().records,
            "wave_pool": _make_records_view().wave_pool,
        },
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 1
    assert int(result[0]["board"]) == 5
    assert int(result[0]["channel"]) == 2
    assert int(result[0]["record_id"]) == 0
    assert int(result[0]["edge_start"]) == 2
    assert int(result[0]["edge_end"]) == 6


def test_records_asymmetry_mask_plugin_serial_and_parallel_match():
    plugin = RecordsAsymmetryMaskPlugin()
    rv = _make_asymmetry_records_view()
    data = {"records": rv.records, "wave_pool": rv.wave_pool}

    serial = plugin.compute(
        DummyContext(
            {
                "records_asymmetry_mask.asymmetry_cut_min": 0.7,
                "records_asymmetry_mask.asymmetry_parallel": False,
            },
            data,
        ),
        "run_001",
    )
    parallel = plugin.compute(
        DummyContext(
            {
                "records_asymmetry_mask.asymmetry_cut_min": 0.7,
                "records_asymmetry_mask.asymmetry_parallel": True,
                "records_asymmetry_mask.asymmetry_num_threads": 2,
            },
            data,
        ),
        "run_001",
    )

    assert serial.dtype == np.dtype(np.bool_)
    assert len(serial) == len(rv.records)
    np.testing.assert_array_equal(serial, np.array([True, False]))
    np.testing.assert_array_equal(parallel, serial)


def test_records_asymmetry_mask_cut_min_above_one_returns_all_false():
    plugin = RecordsAsymmetryMaskPlugin()
    rv = _make_asymmetry_records_view()

    mask = plugin.compute(
        DummyContext(
            {
                "records_asymmetry_mask.asymmetry_cut_min": 1.1,
            },
            {"records": rv.records, "wave_pool": rv.wave_pool},
        ),
        "run_001",
    )

    np.testing.assert_array_equal(mask, np.zeros(len(rv.records), dtype=np.bool_))


def test_threshold_hit_applies_records_asymmetry_mask_before_hit_finding():
    plugin = ThresholdHitPlugin()
    rv = _make_asymmetry_records_view()
    mask = np.array([True, False], dtype=np.bool_)
    ctx = DummyContext(
        {
            "wave_source": "records",
            "asymmetry_cut_enabled": True,
            "threshold": 10.0,
            "left_extension": 0,
            "right_extension": 0,
            "dt": 2,
        },
        {
            "records": rv.records,
            "wave_pool": rv.wave_pool,
            "records_asymmetry_mask": mask,
        },
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 1
    assert set(result["record_id"].tolist()) == {0}


def test_threshold_hit_asymmetry_mask_length_mismatch_raises():
    plugin = ThresholdHitPlugin()
    rv = _make_asymmetry_records_view()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "asymmetry_cut_enabled": True,
        },
        {
            "records": rv.records,
            "wave_pool": rv.wave_pool,
            "records_asymmetry_mask": np.array([True], dtype=np.bool_),
        },
    )

    with pytest.raises(ValueError, match="records_asymmetry_mask length mismatch"):
        _compute_threshold_hits(plugin, ctx)


def test_threshold_hit_asymmetry_mask_all_false_returns_empty_hits():
    plugin = ThresholdHitPlugin()
    rv = _make_asymmetry_records_view()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "asymmetry_cut_enabled": True,
        },
        {
            "records": rv.records,
            "wave_pool": rv.wave_pool,
            "records_asymmetry_mask": np.zeros(len(rv.records), dtype=np.bool_),
        },
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 0
    assert result.dtype == THRESHOLD_HIT_DTYPE


def test_threshold_hit_channel_role_mask_skips_veto_records():
    plugin = ThresholdHitPlugin()
    rv = _make_asymmetry_records_view()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "channel_role_cut_enabled": True,
            "threshold": 10.0,
            "left_extension": 0,
            "right_extension": 0,
            "dt": 2,
        },
        {
            "records": rv.records,
            "wave_pool": rv.wave_pool,
            "records_detector_mask": np.array([True, False], dtype=np.bool_),
        },
    )

    result = _compute_threshold_hits(plugin, ctx)

    assert len(result) == 1
    assert set(result["record_id"].tolist()) == {0}


def test_threshold_hit_channel_role_mask_length_mismatch_raises():
    plugin = ThresholdHitPlugin()
    rv = _make_asymmetry_records_view()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "channel_role_cut_enabled": True,
        },
        {
            "records": rv.records,
            "wave_pool": rv.wave_pool,
            "records_detector_mask": np.array([True], dtype=np.bool_),
        },
    )

    with pytest.raises(ValueError, match="records_detector_mask length mismatch"):
        _compute_threshold_hits(plugin, ctx)


def test_threshold_hit_numba_backend_matches_ragged_with_chunk_parallel():
    plugin = ThresholdHitPlugin()
    rv = _make_many_records_view(n_records=6)
    base_config = {
        "wave_source": "records",
        "threshold": 10.0,
        "left_extension": 0,
        "right_extension": 0,
        "parallel_chunk_size": 2,
        "parallel_min_records": 1,
        "n_workers": 2,
    }
    data = {"records": rv.records, "wave_pool": rv.wave_pool}

    ragged = plugin.compute_array(
        DummyContext({**base_config, "backend": "ragged"}, data),
        "run_001",
    )
    numba = plugin.compute_array(
        DummyContext({**base_config, "backend": "numba"}, data),
        "run_001",
    )

    np.testing.assert_array_equal(numba, ragged)


def test_threshold_hit_auto_backend_falls_back_when_numba_unavailable(monkeypatch):
    plugin = ThresholdHitPlugin()
    rv = _make_records_view()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "backend": "auto",
            "threshold": 10.0,
            "left_extension": 0,
            "right_extension": 0,
        },
        {"records": rv.records, "wave_pool": rv.wave_pool},
    )

    monkeypatch.setattr(hit_finder_module, "_NUMBA_AVAILABLE", False)

    result = plugin.compute_array(ctx, "run_001")

    assert len(result) == 1
    assert result.dtype == THRESHOLD_HIT_DTYPE


def test_threshold_hit_numba_backend_raises_when_numba_unavailable(monkeypatch):
    plugin = ThresholdHitPlugin()
    rv = _make_records_view()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "backend": "numba",
            "threshold": 10.0,
        },
        {"records": rv.records, "wave_pool": rv.wave_pool},
    )

    monkeypatch.setattr(hit_finder_module, "_NUMBA_AVAILABLE", False)

    with pytest.raises(RuntimeError, match="backend='numba' failed"):
        plugin.compute_array(ctx, "run_001")


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
    empty_wave_pool = np.zeros(0, dtype=np.uint16)
    ctx._data.update({"records": empty_records, "wave_pool": empty_wave_pool})

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


def test_threshold_hit_keeps_only_interval_fields():
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
    assert "height" not in result.dtype.names
    assert "integral" not in result.dtype.names
    assert "rise_time" not in result.dtype.names
    assert "fall_time" not in result.dtype.names
    assert int(result[0]["edge_start"]) == 4
    assert int(result[0]["edge_end"]) == 9


def test_threshold_hit_interval_extensions_do_not_compute_features():
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
    assert "rise_time" not in result.dtype.names
    assert "fall_time" not in result.dtype.names


def test_threshold_hit_accepts_deprecated_sampling_interval_ns_with_warning():
    """Test that sampling_interval_ns is no longer supported - use dt instead"""
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

    # Use 'dt' instead of deprecated 'sampling_interval_ns'
    ctx = DummyContext(
        {"threshold": 10.0, "dt": 2},
        {"st_waveforms": st},
    )

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


def test_threshold_hit_streaming_mode_with_recordsbundleref():
    """测试 RecordsBundleRef 流式处理模式"""
    from unittest.mock import MagicMock

    from waveform_analysis.core.processing.records_builder import RecordsBundle, RecordsBundleRef

    plugin = ThresholdHitPlugin()

    # 创建模拟的 RecordsBundleRef
    # 模拟 2 个 chunk，每个 chunk 有 1 条 record
    chunk1_records = np.zeros(1, dtype=RECORDS_DTYPE)
    chunk1_records["baseline"] = 100.0
    chunk1_records["timestamp"] = 1_000_000
    chunk1_records["board"] = 0
    chunk1_records["channel"] = 0
    chunk1_records["dt"] = 2
    chunk1_records["event_length"] = 8
    chunk1_records["wave_offset"] = 0
    chunk1_records["record_id"] = 0
    chunk1_wave_pool = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)
    chunk1 = RecordsBundle(chunk1_records, chunk1_wave_pool)

    chunk2_records = np.zeros(1, dtype=RECORDS_DTYPE)
    chunk2_records["baseline"] = 100.0
    chunk2_records["timestamp"] = 2_000_000
    chunk2_records["board"] = 0
    chunk2_records["channel"] = 1
    chunk2_records["dt"] = 2
    chunk2_records["event_length"] = 8
    chunk2_records["wave_offset"] = 0
    chunk2_records["record_id"] = 1
    chunk2_wave_pool = np.array([100, 100, 70, 70, 70, 70, 100, 100], dtype=np.uint16)
    chunk2 = RecordsBundle(chunk2_records, chunk2_wave_pool)

    # 创建 RecordsBundleRef mock
    bundle_ref = MagicMock(spec=RecordsBundleRef)
    bundle_ref.total_records = 2
    bundle_ref.iter_chunks = MagicMock(return_value=iter([chunk1, chunk2]))

    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
            "streaming_chunk_size": 1,
        },
        {"records": bundle_ref},
    )

    result = plugin.compute_array(ctx, "run_001")

    # 验证结果
    assert len(result) == 2  # 2 个 chunk，每个 1 个 hit
    assert result.dtype == THRESHOLD_HIT_DTYPE
    assert set(result["channel"].tolist()) == {0, 1}
    assert set(result["record_id"].tolist()) == {0, 1}


def test_threshold_hit_batch_mode_with_recordsbundle():
    """测试 RecordsBundle 批量处理模式（向后兼容）"""
    plugin = ThresholdHitPlugin()

    # 创建正式 records + wave_pool 输入
    records = np.zeros(1, dtype=RECORDS_DTYPE)
    records["baseline"] = 100.0
    records["timestamp"] = 1_000_000
    records["board"] = 0
    records["channel"] = 0
    records["dt"] = 2
    records["event_length"] = 8
    records["wave_offset"] = 0
    records["record_id"] = 0
    wave_pool = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)
    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
        },
        {"records": records, "wave_pool": wave_pool},
    )

    result = plugin.compute_array(ctx, "run_001")

    # 验证结果
    assert len(result) == 1
    assert result.dtype == THRESHOLD_HIT_DTYPE
    assert int(result[0]["channel"]) == 0


def test_threshold_hit_batched_mode_boundary():
    """测试批处理模式的边界条件（chunk_size 边界）"""
    plugin = ThresholdHitPlugin()

    # 测试 chunk_size=10，记录数分别为 9/10/11
    for n_records in [9, 10, 11]:
        records = np.zeros(n_records, dtype=RECORDS_DTYPE)
        records["baseline"] = 100.0
        records["timestamp"] = np.arange(n_records, dtype=np.int64) * 1_000_000
        records["board"] = 0
        records["channel"] = np.arange(n_records, dtype=np.int16)
        records["dt"] = 2
        records["event_length"] = 8
        records["wave_offset"] = np.arange(n_records, dtype=np.int64) * 8
        records["record_id"] = np.arange(n_records, dtype=np.int64)

        # 构建 wave_pool：每条记录有一个过阈信号
        wave_pool = np.zeros(n_records * 8, dtype=np.uint16)
        for i in range(n_records):
            wave_pool[i * 8 : i * 8 + 8] = [100, 100, 80, 80, 80, 80, 100, 100]

        ctx = DummyContext(
            {
                "wave_source": "records",
                "threshold": 10.0,
                "streaming_chunk_size": 10,  # 设置 chunk_size=10
            },
            {"records": records, "wave_pool": wave_pool},
        )

        result = plugin.compute_array(ctx, "run_001")

        # 验证结果：每条记录应该产生 1 个 hit
        assert (
            len(result) == n_records
        ), f"n_records={n_records}, expected {n_records} hits, got {len(result)}"
        assert result.dtype == THRESHOLD_HIT_DTYPE
        assert set(result["channel"].tolist()) == set(range(n_records))


def test_threshold_hit_empty_dataset():
    """测试空数据集"""
    plugin = ThresholdHitPlugin()

    # 空 RecordsBundle
    empty_records = np.zeros(0, dtype=RECORDS_DTYPE)
    empty_wave_pool = np.zeros(0, dtype=np.uint16)
    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
        },
        {"records": empty_records, "wave_pool": empty_wave_pool},
    )

    result = plugin.compute_array(ctx, "run_001")

    # 验证结果：应该返回空数组
    assert len(result) == 0
    assert result.dtype == THRESHOLD_HIT_DTYPE


def test_threshold_hit_no_hits_found():
    """测试没有找到任何 hit 的情况"""
    plugin = ThresholdHitPlugin()

    # 创建没有过阈信号的数据
    records = np.zeros(5, dtype=RECORDS_DTYPE)
    records["baseline"] = 100.0
    records["timestamp"] = np.arange(5, dtype=np.int64) * 1_000_000
    records["board"] = 0
    records["channel"] = np.arange(5, dtype=np.int16)
    records["dt"] = 2
    records["event_length"] = 8
    records["wave_offset"] = np.arange(5, dtype=np.int64) * 8
    records["record_id"] = np.arange(5, dtype=np.int64)

    # 所有波形都是平坦的，没有过阈
    wave_pool = np.full(5 * 8, 100, dtype=np.uint16)

    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
        },
        {"records": records, "wave_pool": wave_pool},
    )

    result = plugin.compute_array(ctx, "run_001")

    # 验证结果：应该返回空数组
    assert len(result) == 0
    assert result.dtype == THRESHOLD_HIT_DTYPE


def test_threshold_hit_multi_board_multi_channel():
    """测试多板卡、多通道场景"""
    plugin = ThresholdHitPlugin()

    # 创建 2 个板卡，每个板卡 2 个通道
    n_records = 4
    records = np.zeros(n_records, dtype=RECORDS_DTYPE)
    records["baseline"] = 100.0
    records["timestamp"] = np.arange(n_records, dtype=np.int64) * 1_000_000
    records["board"] = [0, 0, 1, 1]  # 板卡 0, 0, 1, 1
    records["channel"] = [0, 1, 0, 1]  # 通道 0, 1, 0, 1
    records["dt"] = 2
    records["event_length"] = 8
    records["wave_offset"] = np.arange(n_records, dtype=np.int64) * 8
    records["record_id"] = np.arange(n_records, dtype=np.int64)

    # 每条记录有一个过阈信号
    wave_pool = np.zeros(n_records * 8, dtype=np.uint16)
    for i in range(n_records):
        wave_pool[i * 8 : i * 8 + 8] = [100, 100, 80, 80, 80, 80, 100, 100]

    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
        },
        {"records": records, "wave_pool": wave_pool},
    )

    result = plugin.compute_array(ctx, "run_001")

    # 验证结果
    assert len(result) == 4
    assert result.dtype == THRESHOLD_HIT_DTYPE
    assert set(result["board"].tolist()) == {0, 1}
    assert set(result["channel"].tolist()) == {0, 1}
    # 验证每个 (board, channel) 组合都有 1 个 hit
    for board in [0, 1]:
        for channel in [0, 1]:
            mask = (result["board"] == board) & (result["channel"] == channel)
            assert np.sum(mask) == 1, f"Expected 1 hit for board={board}, channel={channel}"


def test_threshold_hit_batched_mode_large_dataset():
    """测试批处理模式处理较大数据集"""
    plugin = ThresholdHitPlugin()

    # 创建 250 条记录（超过默认 chunk_size=100）
    n_records = 250
    records = np.zeros(n_records, dtype=RECORDS_DTYPE)
    records["baseline"] = 100.0
    records["timestamp"] = np.arange(n_records, dtype=np.int64) * 1_000_000
    records["board"] = 0
    records["channel"] = np.arange(n_records, dtype=np.int16) % 8  # 8 个通道循环
    records["dt"] = 2
    records["event_length"] = 8
    records["wave_offset"] = np.arange(n_records, dtype=np.int64) * 8
    records["record_id"] = np.arange(n_records, dtype=np.int64)

    # 每条记录有一个过阈信号
    wave_pool = np.zeros(n_records * 8, dtype=np.uint16)
    for i in range(n_records):
        wave_pool[i * 8 : i * 8 + 8] = [100, 100, 80, 80, 80, 80, 100, 100]

    ctx = DummyContext(
        {
            "wave_source": "records",
            "threshold": 10.0,
            "streaming_chunk_size": 100,  # 强制使用批处理模式
        },
        {"records": records, "wave_pool": wave_pool},
    )

    result = plugin.compute_array(ctx, "run_001")

    # 验证结果
    assert len(result) == n_records
    assert result.dtype == THRESHOLD_HIT_DTYPE
    # 验证 record_id 的连续性
    assert set(result["record_id"].tolist()) == set(range(n_records))
    # 验证通道分布
    assert set(result["channel"].tolist()) == set(range(8))
