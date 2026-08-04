"""测试位置重建功能

测试内容：
1. PMT 几何布局系统
2. PositionReconstructionPlugin (v0.2.1)
3. S1S2PairAccessor.positions()
"""

import numpy as np
import pytest

from waveform_analysis.core.hardware.geometry import (
    PmtEntry,
    PmtLayout,
    load_fallback_layout,
    load_pmt_layout_from_config,
)
from waveform_analysis.core.plugins.builtin.position_reconstruction import (
    FLAG_EDGE_EVENT,
    FLAG_LOW_S2_SIGNAL,
    FLAG_POSITION_VALID,
    FLAG_XY_RECONSTRUCTED,
    FLAG_Z_RECONSTRUCTED,
    POSITION_RECONSTRUCTION_DTYPE,
    PositionReconstructionPlugin,
)

# ============================================================================
# PMT 几何布局测试
# ============================================================================


def test_fallback_layout():
    """测试 fallback 布局加载"""
    layout = load_fallback_layout()

    assert layout.source == "fallback"
    assert len(layout.entries) == 7  # 7-PMT 配置

    # 测试查找功能
    pmt1 = layout.entry_for_pmt(1)
    assert pmt1.pmt_no == 1
    assert pmt1.pmt_id == "LV2389"
    assert pmt1.x_mm == -26.8
    assert pmt1.y_mm == 17.7

    # 测试硬件映射
    pmt_by_channel = layout.entry_for_readout(0, 15)
    assert pmt_by_channel.pmt_no == 1

    # 测试字典访问
    positions = layout.pmt_positions
    assert len(positions) == 7
    assert positions[1] == (-26.8, 17.7)


def test_config_layout():
    """测试从配置加载布局"""
    config = {
        "detector_geometry": {
            "pmt_mapping": [
                {
                    "board": 0,
                    "channel": 10,
                    "pmt_no": 1,
                    "pmt_id": "TEST001",
                    "x_mm": 10.0,
                    "y_mm": 20.0,
                    "gain": 1.0e7,
                },
                {
                    "board": 0,
                    "channel": 11,
                    "pmt_no": 2,
                    "pmt_id": "TEST002",
                    "x_mm": -10.0,
                    "y_mm": -20.0,
                    "gain": 2.0e7,
                },
            ],
            "default_gain": 9.2e6,
        }
    }

    layout = load_pmt_layout_from_config(config)

    assert layout is not None
    assert layout.source == "config"
    assert len(layout.entries) == 2

    pmt1 = layout.entry_for_pmt(1)
    assert pmt1.x_mm == 10.0
    assert pmt1.gain == 1.0e7

    pmt2 = layout.entry_for_readout(0, 11)
    assert pmt2.pmt_no == 2
    assert pmt2.gain == 2.0e7


def test_pmt_layout_error_handling():
    """测试布局查找错误处理"""
    layout = load_fallback_layout()

    # 不存在的 PMT 编号
    with pytest.raises(KeyError):
        layout.entry_for_pmt(999)

    # 不存在的硬件通道
    with pytest.raises(KeyError):
        layout.entry_for_readout(99, 99)


# ============================================================================
# 位置重建插件测试
# ============================================================================


def test_plugin_initialization():
    """测试插件初始化"""
    plugin = PositionReconstructionPlugin()

    assert plugin.provides == "position_reconstruction"
    assert plugin.depends_on == ["s1_s2_pairs"]
    assert plugin.version == "0.2.1"
    assert plugin.output_dtype == POSITION_RECONSTRUCTION_DTYPE

    # 检查配置选项
    assert "drift_velocity" in plugin.options
    assert "min_s2_area_for_xy" in plugin.options
    assert "edge_threshold_mm" in plugin.options
    assert "detector_radius_mm" in plugin.options


def test_plugin_empty_input():
    """测试插件空输入处理"""
    plugin = PositionReconstructionPlugin()

    # 模拟空配对数据
    empty_pairs = np.zeros(0, dtype=[("selected", bool), ("pair_id", "i8")])

    # 创建简单 mock context
    class SimpleContext:
        def __init__(self, config_dict, data_dict):
            self.config = config_dict
            self._data = data_dict

        def get_config(self, plugin, key):
            return self.config.get(key)

        def get_data(self, run_id, data_name):
            return self._data.get(data_name)

    ctx = SimpleContext(config_dict={}, data_dict={"s1_s2_pairs": empty_pairs})

    result = plugin.compute(ctx, "test_run")

    assert len(result) == 0
    assert result.dtype == POSITION_RECONSTRUCTION_DTYPE


def test_plugin_with_mock_data():
    """测试插件基本功能（使用模拟数据，不测试 XY 重建）

    注意：完整的 XY 重建测试需要 PeakChannelAccessor，
    这里只测试 Z 坐标和标志位逻辑。
    """
    plugin = PositionReconstructionPlugin()

    # 创建模拟配对数据
    pairs_dtype = np.dtype(
        [
            ("pair_id", "i8"),
            ("s1_peak_id", "i8"),
            ("s2_peak_id", "i8"),
            ("selected", bool),
            ("drift_time_ns", "f4"),
            ("s2_area", "f4"),
            ("s2_n_channels", "i2"),
        ]
    )

    pairs = np.zeros(3, dtype=pairs_dtype)
    pairs["pair_id"] = [1, 2, 3]
    pairs["s1_peak_id"] = [10, 20, 30]
    pairs["s2_peak_id"] = [100, 200, 300]
    pairs["selected"] = [True, True, False]  # 第3个未选中
    pairs["drift_time_ns"] = [10000, 20000, 30000]
    pairs["s2_area"] = [500, 150, 50]  # 第2个信号较弱
    pairs["s2_n_channels"] = [7, 5, 3]

    # 创建一个简单的 mock context（不提供通道数据，XY 将失败）
    class SimpleContext:
        def __init__(self, config_dict, data_dict):
            self.config = config_dict
            self._data = data_dict

        def get_config(self, plugin, key):
            return self.config.get(key)

        def get_data(self, run_id, data_name):
            return self._data.get(data_name)

    ctx = SimpleContext(
        config_dict={
            "drift_velocity": 1.5,  # mm/ns
            "min_s2_area_for_xy": 200.0,  # 设置较高，使两个都不满足
            "detector_radius_mm": 50.0,
            "edge_threshold_mm": 5.0,
        },
        data_dict={"s1_s2_pairs": pairs},
    )

    result = plugin.compute(ctx, "test_run")

    # 应该只处理前2个选中的配对
    assert len(result) == 2

    # 检查基本字段
    assert result["pair_id"][0] == 1
    assert result["s1_peak_id"][0] == 10
    assert result["s2_peak_id"][0] == 100

    # 检查 Z 坐标
    assert result["z"][0] == pytest.approx(10000 * 1.5, rel=1e-5)
    assert result["z"][1] == pytest.approx(20000 * 1.5, rel=1e-5)
    assert all(result["z_method"] == "drift_time")

    # 检查 Z 重建标志位
    assert all(result["flags"] & FLAG_Z_RECONSTRUCTED != 0)

    # 两个配对 S2 信号都低于阈值（200.0），应该被标记
    # 第1个: 500 > 200, 不应该被标记
    # 第2个: 150 < 200, 应该被标记
    assert result["flags"][0] & FLAG_LOW_S2_SIGNAL == 0  # 第1个信号足够强
    assert result["flags"][1] & FLAG_LOW_S2_SIGNAL != 0  # 第2个信号太弱


def test_default_drift_velocity_outputs_z_in_mm():
    """默认漂移速度以 mm/ns 表达，Z 输出单位为 mm。"""
    plugin = PositionReconstructionPlugin()

    pairs_dtype = np.dtype(
        [
            ("pair_id", "i8"),
            ("s1_peak_id", "i8"),
            ("s2_peak_id", "i8"),
            ("selected", bool),
            ("drift_time_ns", "f4"),
            ("s2_area", "f4"),
            ("s2_n_channels", "i2"),
        ]
    )
    pairs = np.zeros(1, dtype=pairs_dtype)
    pairs["pair_id"] = [1]
    pairs["s1_peak_id"] = [10]
    pairs["s2_peak_id"] = [100]
    pairs["selected"] = [True]
    pairs["drift_time_ns"] = [50000.0]
    pairs["s2_area"] = [500.0]
    pairs["s2_n_channels"] = [7]

    class SimpleContext:
        def __init__(self, data_dict):
            self.config = {}
            self._data = data_dict

        def get_config(self, plugin, key):
            return plugin.options[key].default

        def get_data(self, run_id, data_name):
            return self._data.get(data_name)

    ctx = SimpleContext(data_dict={"s1_s2_pairs": pairs})
    result = plugin.compute(ctx, "test_run")

    assert result["z"][0] == pytest.approx(65.0, rel=1e-5)
    assert result["z_err"][0] == pytest.approx(0.013, rel=1e-5)


def test_flags():
    """测试标志位定义"""
    # 验证标志位是独立的位
    assert FLAG_POSITION_VALID == 1 << 0
    assert FLAG_Z_RECONSTRUCTED == 1 << 1
    assert FLAG_XY_RECONSTRUCTED == 1 << 2
    assert FLAG_LOW_S2_SIGNAL == 1 << 3
    assert FLAG_EDGE_EVENT == 1 << 4

    # 验证可以组合标志位
    flags = FLAG_POSITION_VALID | FLAG_Z_RECONSTRUCTED | FLAG_XY_RECONSTRUCTED
    assert flags & FLAG_POSITION_VALID != 0
    assert flags & FLAG_Z_RECONSTRUCTED != 0
    assert flags & FLAG_XY_RECONSTRUCTED != 0
    assert flags & FLAG_LOW_S2_SIGNAL == 0


def test_position_dtype():
    """测试位置数据类型"""
    # 创建一个测试记录
    pos = np.zeros(1, dtype=POSITION_RECONSTRUCTION_DTYPE)

    # 验证所有字段存在
    expected_fields = [
        "event_id",
        "pair_id",
        "s1_peak_id",
        "s2_peak_id",
        "x",
        "y",
        "z",
        "r",
        "x_err",
        "y_err",
        "z_err",
        "xy_chi2",
        "xy_ndf",
        "z_quality",
        "position_goodness",
        "xy_method",
        "z_method",
        "drift_time_ns",
        "s2_area",
        "s2_n_channels",
        "flags",
    ]

    for field in expected_fields:
        assert field in pos.dtype.names, f"Missing field: {field}"


# ============================================================================
# S1S2PairAccessor 位置访问测试
# ============================================================================


def test_accessor_positions_empty():
    """测试 accessor 位置访问（无数据）"""
    from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor

    empty_pairs = np.zeros(0, dtype=[("selected", bool), ("pair_id", "i8")])

    # 创建简单 mock context
    class SimpleContext:
        def __init__(self, config_dict, data_dict):
            self.config = config_dict
            self._data = data_dict

        def get_config(self, plugin, key):
            return self.config.get(key)

        def get_data(self, run_id, data_name):
            if data_name not in self._data:
                raise KeyError(f"Data {data_name} not found")
            return self._data.get(data_name)

    ctx = SimpleContext(config_dict={}, data_dict={"s1_s2_pairs": empty_pairs})

    accessor = S1S2PairAccessor(ctx, "test_run")
    positions = accessor.positions()

    # 无位置数据时应该返回空数组
    assert len(positions) == 0
    assert positions.dtype == POSITION_RECONSTRUCTION_DTYPE
