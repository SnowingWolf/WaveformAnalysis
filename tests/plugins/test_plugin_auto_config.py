import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.filtering import FilteredWaveformsPlugin
from waveform_analysis.core.plugins.builtin.cpu.standard import (
    HitFinderPlugin,
    WaveformsPlugin,
)
from waveform_analysis.core.processing.dtypes import PEAK_DTYPE, create_record_dtype
from waveform_analysis.utils.formats import (
    FLAT_LAYOUT,
    ColumnMapping,
    DAQAdapter,
    FormatSpec,
    GenericCSVReader,
    TimestampUnit,
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
    ctx = DummyContext({}, {"st_waveforms": st_waveforms})
    plugin = HitFinderPlugin()
    hits = plugin.compute(ctx, "run_001", threshold=1.0)
    assert len(hits) == 0
    assert hits.dtype == np.dtype(PEAK_DTYPE)


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
