from unittest.mock import patch

import numpy as np

from tests.utils import DummyContext, FakeContext
from waveform_analysis.core.data.records_view import RecordsView
from waveform_analysis.core.plugins.builtin.cpu.filtering import FilteredWaveformsPlugin
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
    HIT_DTYPE,
    HitFinderPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.records import RecordsPlugin
from waveform_analysis.core.plugins.builtin.cpu.standard import WaveformsPlugin
from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import RECORDS_DTYPE
from waveform_analysis.utils.formats import (
    FLAT_LAYOUT,
    ColumnMapping,
    DAQAdapter,
    FormatSpec,
    GenericCSVReader,
    TimestampUnit,
    get_adapter,
    register_adapter,
    unregister_adapter,
)


def _register_test_adapter(name, sampling_rate_hz=1e9):
    """注册测试用的 DAQ 适配器

    注意：expected_samples 已从 FormatSpec 移除，波形长度现在由插件配置或自动检测
    """
    spec = FormatSpec(
        name=f"{name}_spec",
        columns=ColumnMapping(),
        timestamp_unit=TimestampUnit.NANOSECONDS,
        sampling_rate_hz=sampling_rate_hz,
    )
    adapter = DAQAdapter(
        name=name,
        format_reader=GenericCSVReader(spec),
        directory_layout=FLAT_LAYOUT,
    )
    register_adapter(adapter)


def test_hitfinder_empty_dtype():
    dtype = create_record_dtype(5)
    st_waveforms = np.zeros(0, dtype=dtype)
    ctx = DummyContext({"use_filtered": False}, {"st_waveforms": st_waveforms})
    plugin = HitFinderPlugin()
    peaks = plugin.compute(ctx, "run_001")
    assert len(peaks) == 0
    assert peaks.dtype == HIT_DTYPE


def test_hitfinder_parallel_consistency():
    dtype = create_record_dtype(128)
    n_events = 200
    st_waveforms = np.zeros(n_events, dtype=dtype)

    for i in range(n_events):
        wave = np.ones(128, dtype=np.int16) * 100
        pulse_start = 20 + (i % 40)
        wave[pulse_start : pulse_start + 4] = 40
        st_waveforms[i]["wave"] = wave
        st_waveforms[i]["baseline"] = 100.0
        st_waveforms[i]["timestamp"] = 100_000 + i * 1000
        st_waveforms[i]["dt"] = 2
        st_waveforms[i]["event_length"] = 128
        st_waveforms[i]["channel"] = i % 2

    base_config = {
        "use_filtered": False,
        "use_derivative": False,
        "height": 5.0,
        "distance": 1,
        "prominence": 1.0,
        "width": 1,
        "threshold": None,
    }

    plugin = HitFinderPlugin()

    ctx_serial = DummyContext(
        {
            **base_config,
            "parallel": False,
        },
        {"st_waveforms": st_waveforms},
    )
    serial_result = plugin.compute(ctx_serial, "run_001")

    ctx_parallel = DummyContext(
        {
            **base_config,
            "parallel": True,
            "n_workers": 4,
            "chunk_size": 32,
            "parallel_min_events": 1,
        },
        {"st_waveforms": st_waveforms},
    )
    parallel_result = plugin.compute(ctx_parallel, "run_001")

    np.testing.assert_array_equal(parallel_result, serial_result)


def test_hitfinder_height_window_extension_effect():
    dtype = create_record_dtype(64)
    st_waveforms = np.zeros(1, dtype=dtype)

    wave = np.ones(64, dtype=np.int16) * 100
    wave[30:34] = 60  # negative pulse
    wave[38] = 130  # overshoot on the right side
    st_waveforms[0]["wave"] = wave
    st_waveforms[0]["baseline"] = 100.0
    st_waveforms[0]["timestamp"] = 100_000
    st_waveforms[0]["dt"] = 2
    st_waveforms[0]["event_length"] = 64
    st_waveforms[0]["channel"] = 0

    plugin = HitFinderPlugin()
    base_config = {
        "use_filtered": False,
        "use_derivative": False,
        "height": 5.0,
        "distance": 1,
        "prominence": 1.0,
        "width": 1,
        "threshold": None,
        "height_method": "minmax",
        "parallel": False,
    }

    ctx_small = DummyContext(
        {
            **base_config,
            "height_window_extension": 0,
        },
        {"st_waveforms": st_waveforms},
    )
    peaks_small = plugin.compute(ctx_small, "run_001")

    ctx_large = DummyContext(
        {
            **base_config,
            "height_window_extension": 8,
        },
        {"st_waveforms": st_waveforms},
    )
    peaks_large = plugin.compute(ctx_large, "run_001")

    assert len(peaks_small) > 0
    assert len(peaks_large) > 0
    assert peaks_large["height"][0] > peaks_small["height"][0]


def test_hitfinder_wave_source_records_depends_on_records_and_wave_pool():
    plugin = HitFinderPlugin()
    ctx = DummyContext({"wave_source": "records", "use_filtered": True}, {})

    assert plugin.resolve_depends_on(ctx) == ["records", "wave_pool"]


def test_hitfinder_reads_records_view_when_wave_source_records():
    plugin = HitFinderPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "use_derivative": False,
            "height": 5.0,
            "distance": 1,
            "prominence": 1.0,
            "width": 1,
            "threshold": None,
            "parallel": False,
            "dt": 2,
        },
        {},
    )

    records = np.zeros(1, dtype=RECORDS_DTYPE)
    records["baseline"] = 100.0
    records["timestamp"] = 123_456
    records["board"] = 5
    records["channel"] = 2
    records["dt"] = 2
    records["event_length"] = 8
    records["wave_offset"] = 0
    records["polarity"] = ["negative"]
    wave_pool = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)
    rv = RecordsView(records, wave_pool)

    with patch("waveform_analysis.core.records_view", return_value=rv) as mocked:
        result = plugin.compute(ctx, "run_001")

    assert mocked.call_count == 1
    assert len(result) == 1
    assert int(result[0]["board"]) == 5
    assert int(result[0]["channel"]) == 2
    assert int(result[0]["record_id"]) == 0
    assert int(result[0]["dt"]) == 2


def test_waveforms_plugin_uses_raw_files_channels(monkeypatch):
    raw_files = [["f0"], ["f1"], ["f2"], ["f3"]]
    called = {}

    def fake_load_waveforms_flat(self, raw_files, n_channels, **_kwargs):  # noqa: ARG001
        called["raw_files_len"] = len(raw_files)
        called["n_channels"] = n_channels
        return [np.zeros((0, 0)) for _ in range(n_channels)]

    monkeypatch.setattr(WaveformsPlugin, "_load_waveforms_flat", fake_load_waveforms_flat)

    plugin = WaveformsPlugin()
    config = {
        "n_channels": 4,
        "waveforms": {"n_channels": 1, "start_channel_slice": 0},
        "show_progress": False,
    }
    ctx = DummyContext(config, {"raw_files": raw_files})

    plugin.compute(ctx, "run_001")

    assert called["raw_files_len"] == 4
    assert called["n_channels"] == 4


def test_st_waveforms_lineage_uses_adapter_dtype():
    """测试 st_waveforms lineage 使用 wave_length 配置"""
    adapter_name = "test_adapter_lineage"
    _register_test_adapter(adapter_name)
    try:
        plugin = WaveformsPlugin()
        # 通过 wave_length 配置指定波形长度
        config = {"st_waveforms": {"daq_adapter": adapter_name, "wave_length": 16}}
        ctx = DummyContext(config)
        lineage = plugin.get_lineage(ctx)
        wave_field = next(item for item in lineage["dtype"] if item[0] == "wave")
        assert wave_field[2] == (16,)
    finally:
        unregister_adapter(adapter_name)


def test_filtered_waveforms_uses_explicit_fs():
    """测试 filtered_waveforms 使用显式 fs 配置"""
    dtype = create_record_dtype(64)
    st_waveforms = np.zeros(1, dtype=dtype)
    st_waveforms["wave"][0] = np.linspace(0, 1, 64)
    config = {
        "filtered_waveforms": {
            "filter_type": "BW",
            "lowcut": 0.1,
            "highcut": 0.4,
            "fs": 1.0,
        }
    }
    ctx = DummyContext(config, {"st_waveforms": st_waveforms})
    plugin = FilteredWaveformsPlugin()

    result = plugin.compute(ctx, "run_001")

    assert isinstance(result, np.ndarray)
    assert result.shape[0] == 1


def test_waveforms_plugin_v1725_outputs_standard_st_waveforms(monkeypatch):
    raw_dtype = np.dtype(
        [
            ("channel", "i2"),
            ("timestamp", "i8"),
            ("baseline", "f8"),
            ("trunc", "b1"),
            ("wave", "O"),
        ]
    )
    raw_data = np.zeros(2, dtype=raw_dtype)
    raw_data["channel"] = np.array([0, 1], dtype=np.int16)
    raw_data["timestamp"] = np.array([10, 20], dtype=np.int64)
    raw_data["baseline"] = np.array([100.0, 200.0], dtype=np.float64)
    raw_data["trunc"] = np.array([False, True], dtype=np.bool_)
    raw_data["wave"][0] = np.array([11, 12, 13, 14], dtype=np.int16)
    raw_data["wave"][1] = np.array([21, 22], dtype=np.int16)

    adapter = get_adapter("v1725")

    def fake_read_files(file_paths, show_progress=False):  # noqa: ARG001
        assert file_paths == ["dup.bin"]
        return raw_data

    monkeypatch.setattr(adapter.format_reader, "read_files", fake_read_files)

    class _Logger:
        def info(self, *_args, **_kwargs):
            return None

        def warning(self, *_args, **_kwargs):
            return None

    plugin = WaveformsPlugin()
    ctx = DummyContext(
        config={"daq_adapter": "v1725", "show_progress": False},
        data={"raw_files": [["dup.bin"], ["dup.bin"]]},
    )
    ctx.logger = _Logger()

    st = plugin.compute(ctx, "run_001")

    assert isinstance(st, np.ndarray)
    assert st.dtype.names == (
        "baseline",
        "baseline_upstream",
        "polarity",
        "timestamp",
        "record_id",
        "dt",
        "event_length",
        "board",
        "channel",
        "wave",
    )
    assert st["wave"].shape == (2, 4)
    np.testing.assert_array_equal(st["event_length"], np.array([4, 2], dtype=np.int32))
    np.testing.assert_array_equal(st["board"], np.array([0, 0], dtype=np.int16))
    np.testing.assert_array_equal(st["channel"], np.array([0, 1], dtype=np.int16))
    np.testing.assert_array_equal(st["timestamp"], np.array([40000, 80000], dtype=np.int64))
    np.testing.assert_array_equal(st["dt"], np.array([4, 4], dtype=np.int32))
    assert np.all(np.isnan(st["baseline_upstream"]))
    np.testing.assert_array_equal(st["polarity"], np.array(["unknown", "unknown"]))
    assert int(st["wave"][1, 2]) == 0


def test_waveforms_plugin_applies_channel_metadata_polarity(monkeypatch):
    raw_files = [["f0"], ["f1"]]

    def fake_load_waveforms_flat(self, raw_files, n_channels, **_kwargs):  # noqa: ARG001
        out = []
        for ch in range(n_channels):
            arr = np.zeros((1, 12))
            arr[:, 0] = 0
            arr[:, 1] = ch
            arr[:, 2] = 100 + ch
            arr[:, 7:] = 50
            out.append(arr)
        return out

    monkeypatch.setattr(WaveformsPlugin, "_load_waveforms_flat", fake_load_waveforms_flat)

    plugin = WaveformsPlugin()
    ctx = DummyContext(
        config={
            "show_progress": False,
            "channel_metadata": {
                "channels": {
                    "0:0": {"polarity": "negative"},
                    "0:1": {"polarity": "positive"},
                }
            },
        },
        data={"raw_files": raw_files},
    )

    st = plugin.compute(ctx, "run_001")

    np.testing.assert_array_equal(st["polarity"], np.array(["negative", "positive"]))


def test_records_plugin_prefers_streaming_structuring(monkeypatch):
    plugin = RecordsPlugin()
    ctx = FakeContext(
        config={"show_progress": False, "daq_adapter": "vx2730"},
        data={"raw_files": [["f0"], ["f1"]]},
        plugins={"records": plugin},
    )

    class _Logger:
        def info(self, *_args, **_kwargs):
            return None

        def warning(self, *_args, **_kwargs):
            return None

    ctx.logger = _Logger()

    st_dtype = create_record_dtype(4)
    st = np.zeros(2, dtype=st_dtype)
    st["board"] = [0, 0]
    st["channel"] = [0, 1]
    st["timestamp"] = [100, 200]
    st["baseline"] = [10.0, 20.0]
    st["event_length"] = [4, 4]
    st["dt"] = [2, 2]
    st["wave"][0] = np.array([1, 2, 3, 4], dtype=np.int16)
    st["wave"][1] = np.array([5, 6, 7, 8], dtype=np.int16)

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records._structure_waveforms_streaming",
        lambda **_kwargs: st.copy(),
    )

    def _unexpected_fallback(*_args, **_kwargs):
        raise AssertionError("should not fall back to eager waveform loading")

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records._load_waveforms_for_records",
        _unexpected_fallback,
    )

    records = plugin.compute(ctx, "run_001")

    assert len(records) == 2
    np.testing.assert_array_equal(records["timestamp"], np.array([100, 200], dtype=np.int64))
    np.testing.assert_array_equal(records["channel"], np.array([0, 1], dtype=np.int16))
    np.testing.assert_array_equal(records["dt"], np.array([2, 2], dtype=np.int32))


def test_records_plugin_falls_back_when_streaming_structuring_fails(monkeypatch):
    plugin = RecordsPlugin()
    ctx = FakeContext(
        config={"show_progress": False, "daq_adapter": "vx2730"},
        data={"raw_files": [["f0"]]},
        plugins={"records": plugin},
    )

    class _Logger:
        def info(self, *_args, **_kwargs):
            return None

        def warning(self, *_args, **_kwargs):
            return None

    ctx.logger = _Logger()

    st_dtype = create_record_dtype(4)
    st = np.zeros(1, dtype=st_dtype)
    st["board"] = [0]
    st["channel"] = [0]
    st["timestamp"] = [100]
    st["baseline"] = [10.0]
    st["event_length"] = [4]
    st["dt"] = [2]
    st["wave"][0] = np.array([1, 2, 3, 4], dtype=np.int16)

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records._structure_waveforms_streaming",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    fallback_called = {"value": False}

    def _fake_load(_context, _raw_files, _plugin, _adapter_name):
        fallback_called["value"] = True
        return []

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records._load_waveforms_for_records",
        _fake_load,
    )
    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records.WaveformStruct.structure_waveforms",
        lambda self, **_kwargs: st.copy(),
    )

    records = plugin.compute(ctx, "run_001")

    assert fallback_called["value"] is True
    assert len(records) == 1
    assert int(records["timestamp"][0]) == 100
