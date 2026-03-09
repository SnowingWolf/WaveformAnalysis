import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.filtering import FilteredWaveformsPlugin
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
    HIT_DTYPE,
    HitFinderPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.standard import WaveformsPlugin
from waveform_analysis.core.processing.dtypes import create_record_dtype
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
    assert peaks_large["hit_height"][0] > peaks_small["hit_height"][0]


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


def test_filtered_waveforms_fs_auto_from_adapter():
    """测试 filtered_waveforms 从 adapter 自动获取采样率"""
    adapter_name = "test_adapter_filter"
    _register_test_adapter(adapter_name, sampling_rate_hz=1e9)
    try:
        dtype = create_record_dtype(64)
        st_waveforms = np.zeros(1, dtype=dtype)
        st_waveforms["wave"][0] = np.linspace(0, 1, 64)
        config = {
            "filtered_waveforms": {
                "filter_type": "BW",
                "lowcut": 0.1,
                "highcut": 0.4,
                "daq_adapter": adapter_name,
            }
        }
        ctx = DummyContext(config, {"st_waveforms": st_waveforms})
        plugin = FilteredWaveformsPlugin()

        result = plugin.compute(ctx, "run_001")

        assert isinstance(result, np.ndarray)
        assert result.shape[0] == 1
    finally:
        unregister_adapter(adapter_name)


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
        "timestamp",
        "dt",
        "event_length",
        "channel",
        "wave",
    )
    assert st["wave"].shape == (2, 4)
    np.testing.assert_array_equal(st["event_length"], np.array([4, 2], dtype=np.int32))
    np.testing.assert_array_equal(st["channel"], np.array([0, 1], dtype=np.int16))
    np.testing.assert_array_equal(st["timestamp"], np.array([40000, 80000], dtype=np.int64))
    np.testing.assert_array_equal(st["dt"], np.array([4, 4], dtype=np.int32))
    assert np.all(np.isnan(st["baseline_upstream"]))
    assert int(st["wave"][1, 2]) == 0
