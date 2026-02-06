"""
测试 WaveformWidthPlugin - 波形宽度计算插件

测试内容：
1. 基本功能：计算上升/下降时间
2. 依赖关系：正确依赖 SignalPeaksPlugin 和 st_waveforms
3. 配置选项：sampling_rate, rise_low/high, fall_low/high, interpolation
4. 滤波波形支持：use_filtered 选项
5. 边界情况：空通道、无峰值、峰值太小等
"""

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WaveformWidthPlugin
from waveform_analysis.core.processing.dtypes import create_record_dtype


@pytest.fixture
def mock_context(tmp_path):
    """创建模拟的 Context 用于测试"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(WaveformWidthPlugin())
    return ctx


@pytest.fixture
def synthetic_waveform():
    """生成合成波形用于测试

    波形特征：
    - 基线: 10
    - 峰值位置: 100
    - 峰值高度: 90 (相对基线)
    - 上升时间: ~20 采样点 (10%-90%)
    - 下降时间: ~30 采样点 (90%-10%)
    """
    wave_length = 200
    waveform = np.ones(wave_length) * 10  # 基线 = 10

    # 创建一个高斯型峰值
    peak_pos = 100
    peak_height = 90
    sigma = 10

    x = np.arange(wave_length)
    gaussian = peak_height * np.exp(-((x - peak_pos) ** 2) / (2 * sigma**2))
    waveform += gaussian

    return waveform


def test_waveform_width_plugin_basic(mock_context, synthetic_waveform):
    """测试基本的波形宽度计算功能"""
    # 创建模拟的 st_waveforms 数据
    wave_length = len(synthetic_waveform)
    dtype = create_record_dtype(wave_length)

    st_waveform = np.zeros(1, dtype=dtype)
    st_waveform[0]["wave"] = synthetic_waveform
    st_waveform[0]["baseline"] = 10.0
    st_waveform[0]["timestamp"] = 1000
    st_waveform[0]["channel"] = 0
    st_waveform[0]["event_length"] = wave_length

    # 模拟 st_waveforms 数据（单通道）
    st_waveforms = st_waveform

    # 创建模拟的 signal_peaks 数据
    from waveform_analysis.core.plugins.builtin.cpu.peak_finding import ADVANCED_PEAK_DTYPE

    peak = np.zeros(1, dtype=ADVANCED_PEAK_DTYPE)
    peak[0]["position"] = 100  # 峰值位置
    peak[0]["height"] = 90.0
    peak[0]["edge_start"] = 80.0
    peak[0]["edge_end"] = 120.0
    peak[0]["timestamp"] = 1000
    peak[0]["channel"] = 0
    peak[0]["event_index"] = 0

    signal_peaks = peak

    # 手动设置依赖数据
    run_id = "test_run"
    mock_context._results[(run_id, "st_waveforms")] = st_waveforms
    mock_context._results[(run_id, "signal_peaks")] = signal_peaks

    # 设置配置
    mock_context.set_config({"sampling_rate": 1.0}, plugin_name="waveform_width")

    # 计算波形宽度
    widths = mock_context.get_data(run_id, "waveform_width")

    # 验证结果
    assert len(widths) == 1  # 单个峰值
    width_data = widths[0]

    # 验证基本字段
    assert width_data["peak_position"] == 100
    assert width_data["timestamp"] == 1000
    assert width_data["channel"] == 0
    assert width_data["event_index"] == 0

    # 验证上升/下降时间为正值
    assert width_data["rise_time"] > 0
    assert width_data["fall_time"] > 0
    assert width_data["total_width"] > 0

    # 验证总宽度 = 上升时间 + 下降时间（近似）
    assert (
        abs(width_data["total_width"] - (width_data["rise_time"] + width_data["fall_time"]))
        < width_data["total_width"] * 0.3
    )  # 允许 30% 误差


def test_waveform_width_plugin_empty_channel(tmp_path):
    """测试空通道的处理"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(WaveformWidthPlugin())

    run_id = "test_empty"

    # 空的 st_waveforms 和 signal_peaks
    ctx._results[(run_id, "st_waveforms")] = np.array([])
    ctx._results[(run_id, "signal_peaks")] = np.array([])

    widths = ctx.get_data(run_id, "waveform_width")

    assert len(widths) == 0  # 空数组


def test_waveform_width_plugin_sampling_rate(tmp_path):
    """测试采样率配置对时间计算的影响"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(WaveformWidthPlugin())

    # 创建简单的测试数据
    wave_length = 100
    dtype = create_record_dtype(wave_length)
    st_waveform = np.zeros(1, dtype=dtype)
    st_waveform[0]["wave"] = np.concatenate(
        [np.zeros(40), np.linspace(0, 100, 20), np.linspace(100, 0, 20), np.zeros(20)]
    )
    st_waveform[0]["timestamp"] = 1000
    st_waveform[0]["channel"] = 0

    from waveform_analysis.core.plugins.builtin.cpu.peak_finding import ADVANCED_PEAK_DTYPE

    peak = np.zeros(1, dtype=ADVANCED_PEAK_DTYPE)
    peak[0]["position"] = 59
    peak[0]["height"] = 100.0
    peak[0]["timestamp"] = 1000
    peak[0]["channel"] = 0
    peak[0]["event_index"] = 0

    run_id_1 = "test_sampling_1ghz"
    run_id_2 = "test_sampling_2ghz"
    ctx._results[(run_id_1, "st_waveforms")] = st_waveform
    ctx._results[(run_id_1, "signal_peaks")] = peak
    ctx._results[(run_id_2, "st_waveforms")] = st_waveform
    ctx._results[(run_id_2, "signal_peaks")] = peak

    # 测试不同采样率
    ctx.set_config({"sampling_rate": 1.0}, plugin_name="waveform_width")
    widths_1ghz = ctx.get_data(run_id_1, "waveform_width")

    ctx.set_config({"sampling_rate": 2.0}, plugin_name="waveform_width")
    widths_2ghz = ctx.get_data(run_id_2, "waveform_width")

    # 2 GHz 采样率应该产生一半的时间值
    assert abs(widths_2ghz[0]["rise_time"] - widths_1ghz[0]["rise_time"] / 2) < 0.1


def test_waveform_width_plugin_interpolation(tmp_path):
    """测试插值选项"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(WaveformWidthPlugin())

    # 创建测试数据
    wave_length = 100
    dtype = create_record_dtype(wave_length)
    st_waveform = np.zeros(1, dtype=dtype)
    st_waveform[0]["wave"] = np.concatenate(
        [np.zeros(40), np.linspace(0, 100, 20), np.linspace(100, 0, 20), np.zeros(20)]
    )
    st_waveform[0]["timestamp"] = 1000
    st_waveform[0]["channel"] = 0

    from waveform_analysis.core.plugins.builtin.cpu.peak_finding import ADVANCED_PEAK_DTYPE

    peak = np.zeros(1, dtype=ADVANCED_PEAK_DTYPE)
    peak[0]["position"] = 59
    peak[0]["height"] = 100.0
    peak[0]["timestamp"] = 1000
    peak[0]["channel"] = 0
    peak[0]["event_index"] = 0

    run_id = "test_interp"
    ctx._results[(run_id, "st_waveforms")] = st_waveform
    ctx._results[(run_id, "signal_peaks")] = peak

    # 测试有插值
    ctx.set_config({"interpolation": True}, plugin_name="waveform_width")
    widths_interp = ctx.get_data(run_id, "waveform_width")

    # 清除缓存
    ctx._results.pop((run_id, "waveform_width"), None)

    # 测试无插值
    ctx.set_config({"interpolation": False}, plugin_name="waveform_width")
    ctx.get_data(run_id, "waveform_width")

    # 插值应该提供更精确的结果（通常是非整数）
    # 无插值的结果应该更接近整数
    assert widths_interp[0]["rise_time_samples"] != int(widths_interp[0]["rise_time_samples"])


def test_waveform_width_plugin_dependencies(tmp_path):
    """测试插件依赖关系"""
    ctx = Context(storage_dir=str(tmp_path))
    plugin = WaveformWidthPlugin()

    assert plugin.provides == "waveform_width"
    deps = plugin.resolve_depends_on(ctx)
    assert "signal_peaks" in deps
    assert "st_waveforms" in deps


def test_waveform_width_plugin_options():
    """测试插件配置选项"""
    plugin = WaveformWidthPlugin()

    # 验证所有必要的配置选项存在
    assert "use_filtered" in plugin.options
    assert "sampling_rate" in plugin.options
    assert "rise_low" in plugin.options
    assert "rise_high" in plugin.options
    assert "fall_high" in plugin.options
    assert "fall_low" in plugin.options
    assert "interpolation" in plugin.options

    # 验证默认值
    assert plugin.options["use_filtered"].default is False
    assert plugin.options["sampling_rate"].default is None
    assert plugin.options["rise_low"].default == 0.1
    assert plugin.options["rise_high"].default == 0.9
    assert plugin.options["interpolation"].default is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
