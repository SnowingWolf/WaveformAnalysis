"""测试能量重建功能

测试内容：
1. EnergyReconstructionPlugin (v0.1.0, 结构占位)
2. 占位 compute 逻辑：身份/可观测字段继承，能量字段填 NaN
3. 输出 dtype 字段完整性
"""

import numpy as np
import pytest

from waveform_analysis.core.plugins.builtin.energy_reconstruction import (
    ENERGY_RECONSTRUCTION_DTYPE,
    FLAG_ENERGY_NOT_IMPLEMENTED,
    FLAG_ENERGY_RECONSTRUCTED,
    FLAG_LOW_S1_SIGNAL,
    FLAG_LOW_S2_SIGNAL,
    FLAG_S1_ENERGY_VALID,
    FLAG_S2_ENERGY_VALID,
    FLAG_SATURATED_S2,
    EnergyReconstructionPlugin,
)


class SimpleContext:
    """最小 mock context：只提供 s1_s2_pairs 数据。"""

    def __init__(self, data_dict):
        self.config = {}
        self._data = data_dict

    def get_config(self, plugin, key):
        return plugin.options[key].default

    def get_data(self, run_id, data_name):
        if data_name not in self._data:
            raise KeyError(f"Data {data_name} not found")
        return self._data.get(data_name)


def _make_pairs_dtype():
    """构造 s1_s2_pairs 的最小 dtype。"""
    return np.dtype(
        [
            ("pair_id", "i8"),
            ("s1_peak_id", "i8"),
            ("s2_peak_id", "i8"),
            ("selected", bool),
            ("s1_area", "f4"),
            ("s2_area", "f4"),
            ("s1_n_channels", "i2"),
            ("s2_n_channels", "i2"),
            ("drift_time_ns", "f4"),
        ]
    )


def _make_pairs(n_rows=3):
    pairs = np.zeros(n_rows, dtype=_make_pairs_dtype())
    pairs["pair_id"] = [1, 2, 3]
    pairs["s1_peak_id"] = [10, 20, 30]
    pairs["s2_peak_id"] = [100, 200, 300]
    pairs["selected"] = [True, True, False]  # 第3个未选中
    pairs["s1_area"] = [50, 80, 70]
    pairs["s2_area"] = [500, 150, 50]
    pairs["s1_n_channels"] = [3, 4, 3]
    pairs["s2_n_channels"] = [7, 5, 3]
    pairs["drift_time_ns"] = [10000, 20000, 30000]
    return pairs


# ============================================================================
# 插件初始化测试
# ============================================================================


def test_plugin_initialization():
    """测试插件初始化"""
    plugin = EnergyReconstructionPlugin()

    assert plugin.provides == "energy_reconstruction"
    assert plugin.depends_on == ["s1_s2_pairs"]
    assert plugin.version == "0.1.0"
    assert plugin.output_dtype == ENERGY_RECONSTRUCTION_DTYPE

    # 检查配置选项
    assert "s1_energy_scale" in plugin.options
    assert "s2_energy_scale" in plugin.options


def test_plugin_empty_input():
    """测试插件空输入处理"""
    plugin = EnergyReconstructionPlugin()

    empty_pairs = np.zeros(0, dtype=[("selected", bool), ("pair_id", "i8")])
    ctx = SimpleContext(data_dict={"s1_s2_pairs": empty_pairs})

    result = plugin.compute(ctx, "test_run")

    assert len(result) == 0
    assert result.dtype == ENERGY_RECONSTRUCTION_DTYPE


# ============================================================================
# 插件功能测试（占位）
# ============================================================================


def test_plugin_with_mock_data():
    """测试插件占位 compute：只处理选中的配对"""
    plugin = EnergyReconstructionPlugin()
    pairs = _make_pairs(n_rows=3)
    ctx = SimpleContext(data_dict={"s1_s2_pairs": pairs})

    result = plugin.compute(ctx, "test_run")

    # 只处理前2个选中的配对
    assert len(result) == 2

    # 身份字段
    assert result["pair_id"][0] == 1
    assert result["pair_id"][1] == 2
    assert result["s1_peak_id"][0] == 10
    assert result["s2_peak_id"][0] == 100

    # 可观测字段继承
    assert result["s1_area"][0] == pytest.approx(50.0)
    assert result["s2_area"][0] == pytest.approx(500.0)
    assert result["s1_n_channels"][0] == 3
    assert result["s2_n_channels"][0] == 7
    assert result["drift_time_ns"][0] == pytest.approx(10000.0)

    # 能量字段占位为 NaN
    for field in ("s1_energy", "s2_energy", "total_energy", "s1_energy_fraction"):
        assert np.isnan(result[field][0])
    for field in ("s1_energy_err", "s2_energy_err", "total_energy_err"):
        assert np.isnan(result[field][0])
    assert np.isnan(result["energy_chi2"][0])

    # 方法占位
    assert np.all(result["s1_method"] == "none")
    assert np.all(result["s2_method"] == "none")

    # 标记算法未实现
    assert np.all(result["flags"] & FLAG_ENERGY_NOT_IMPLEMENTED != 0)


def test_energy_dtype():
    """测试能量数据类型字段完整性"""
    record = np.zeros(1, dtype=ENERGY_RECONSTRUCTION_DTYPE)

    expected_fields = [
        # Identity
        "event_id",
        "pair_id",
        "s1_peak_id",
        "s2_peak_id",
        # Energy
        "s1_energy",
        "s2_energy",
        "total_energy",
        "s1_energy_fraction",
        # Energy uncertainty
        "s1_energy_err",
        "s2_energy_err",
        "total_energy_err",
        # Quality
        "energy_chi2",
        "energy_ndf",
        "energy_goodness",
        # Method
        "s1_method",
        "s2_method",
        # Observables
        "s1_area",
        "s2_area",
        "s1_n_channels",
        "s2_n_channels",
        "drift_time_ns",
        # Flags
        "flags",
    ]

    for field in expected_fields:
        assert field in record.dtype.names, f"Missing field: {field}"


def test_flags():
    """测试标志位定义"""
    # 验证标志位是独立的位
    assert FLAG_ENERGY_RECONSTRUCTED == 1 << 0
    assert FLAG_S1_ENERGY_VALID == 1 << 1
    assert FLAG_S2_ENERGY_VALID == 1 << 2
    assert FLAG_LOW_S1_SIGNAL == 1 << 3
    assert FLAG_LOW_S2_SIGNAL == 1 << 4
    assert FLAG_SATURATED_S2 == 1 << 5
    assert FLAG_ENERGY_NOT_IMPLEMENTED == 1 << 6

    # 验证可以组合标志位
    flags = FLAG_ENERGY_RECONSTRUCTED | FLAG_S1_ENERGY_VALID | FLAG_S2_ENERGY_VALID
    assert flags & FLAG_ENERGY_RECONSTRUCTED != 0
    assert flags & FLAG_S1_ENERGY_VALID != 0
    assert flags & FLAG_S2_ENERGY_VALID != 0
    assert flags & FLAG_LOW_S1_SIGNAL == 0
