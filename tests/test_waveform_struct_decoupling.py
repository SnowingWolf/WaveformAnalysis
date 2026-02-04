"""
测试 WaveformStruct 与 VX2730 解耦功能

验证 WaveformStructConfig 配置类和 WaveformStruct 的解耦实现。
"""

import numpy as np
import pytest

from waveform_analysis.core.plugins.builtin.cpu.waveforms import (
    WaveformStruct,
    WaveformStructConfig,
)
from waveform_analysis.core.processing.dtypes import (
    DEFAULT_WAVE_LENGTH,
    ST_WAVEFORM_DTYPE,
    create_record_dtype,
)
from waveform_analysis.utils.formats import VX2730_SPEC
from waveform_analysis.utils.formats.base import ColumnMapping, FormatSpec


class TestWaveformStructConfig:
    """测试 WaveformStructConfig 配置类"""

    def test_default_vx2730(self):
        """测试 VX2730 默认配置（不再硬编码 wave_length）"""
        config = WaveformStructConfig.default_vx2730()
        assert config.format_spec.name == "vx2730_csv"
        # wave_length 现在为 None，依赖自动检测
        assert config.wave_length is None
        # get_wave_length() 返回 DEFAULT_WAVE_LENGTH
        assert config.get_wave_length() == DEFAULT_WAVE_LENGTH

    def test_from_adapter(self):
        """测试从适配器创建配置（不再获取 expected_samples）"""
        config = WaveformStructConfig.from_adapter("vx2730")
        assert config.format_spec.name == "vx2730_csv"
        # 适配器不再提供 expected_samples
        assert config.wave_length is None

    def test_get_wave_length_priority(self):
        """测试波形长度优先级: wave_length > DEFAULT_WAVE_LENGTH"""
        # 优先级1: wave_length（用户显式配置）
        config = WaveformStructConfig(format_spec=VX2730_SPEC, wave_length=1000)
        assert config.get_wave_length() == 1000

        # 优先级2: DEFAULT_WAVE_LENGTH（当 wave_length 为 None）
        config = WaveformStructConfig(format_spec=VX2730_SPEC, wave_length=None)
        assert config.get_wave_length() == DEFAULT_WAVE_LENGTH

        # 自定义格式也遵循相同优先级
        custom_spec = FormatSpec(
            name="custom",
            columns=ColumnMapping(timestamp=2, samples_start=7),
        )
        config = WaveformStructConfig(format_spec=custom_spec, wave_length=None)
        assert config.get_wave_length() == DEFAULT_WAVE_LENGTH

    def test_get_record_dtype(self):
        """测试动态创建 ST_WAVEFORM_DTYPE"""
        config = WaveformStructConfig(format_spec=VX2730_SPEC, wave_length=1000)
        dtype = config.get_record_dtype()
        assert dtype.names == (
            "baseline",
            "baseline_upstream",
            "timestamp",
            "dt",
            "event_length",
            "channel",
            "wave",
        )
        assert dtype["wave"].shape == (1000,)


class TestDynamicRecordDtype:
    """测试动态 ST_WAVEFORM_DTYPE 创建"""

    def test_create_record_dtype_default(self):
        """测试默认波形长度的 dtype 与全局 ST_WAVEFORM_DTYPE 一致"""
        dtype = create_record_dtype(DEFAULT_WAVE_LENGTH)
        assert dtype == ST_WAVEFORM_DTYPE

    def test_create_record_dtype_custom(self):
        """测试自定义波形长度的 dtype"""
        dtype = create_record_dtype(1000)
        assert dtype.names == (
            "baseline",
            "baseline_upstream",
            "timestamp",
            "dt",
            "event_length",
            "channel",
            "wave",
        )
        assert dtype["wave"].shape == (1000,)

    def test_create_record_dtype_array(self):
        """测试使用动态 dtype 创建数组"""
        dtype = create_record_dtype(1600)
        arr = np.zeros(10, dtype=dtype)
        assert arr["wave"].shape == (10, 1600)


class TestWaveformStructDecoupling:
    """测试 WaveformStruct 解耦功能"""

    @pytest.fixture
    def mock_waveforms_vx2730(self):
        """创建模拟的 VX2730 格式波形数据"""
        # VX2730 格式: BOARD(0), CHANNEL(1), TIMETAG(2), ..., 波形数据从列7开始
        n_events = 10
        n_samples = 5000
        waveforms = []
        for ch in range(2):
            data = np.zeros((n_events, 7 + n_samples))
            data[:, 0] = 0  # BOARD
            data[:, 1] = ch  # CHANNEL
            data[:, 2] = np.arange(n_events) * 1000  # TIMETAG
            data[:, 7:] = np.random.randn(n_events, n_samples) * 10 + 100  # 波形数据
            waveforms.append(data)
        return waveforms

    @pytest.fixture
    def mock_waveforms_custom(self):
        """创建模拟的自定义格式波形数据"""
        # 自定义格式: BOARD(0), CHANNEL(1), 其他元数据(2), TIMETAG(3), ..., 波形数据从列10开始
        n_events = 10
        n_samples = 1000
        waveforms = []
        for ch in range(2):
            data = np.zeros((n_events, 10 + n_samples))
            data[:, 0] = 0  # BOARD
            data[:, 1] = ch  # CHANNEL
            data[:, 3] = np.arange(n_events) * 1000  # TIMETAG（列3）
            data[:, 10:] = np.random.randn(n_events, n_samples) * 10 + 100  # 波形数据
            waveforms.append(data)
        return waveforms

    def test_backward_compatibility_no_config(self, mock_waveforms_vx2730):
        """测试向后兼容：无配置时使用 VX2730 默认配置"""
        struct = WaveformStruct(mock_waveforms_vx2730)
        assert struct.config.format_spec.name == "vx2730_csv"
        # 默认配置现在使用 DEFAULT_WAVE_LENGTH
        assert struct.record_dtype == create_record_dtype(DEFAULT_WAVE_LENGTH)

    def test_from_adapter_vx2730(self, mock_waveforms_vx2730):
        """测试从适配器创建 WaveformStruct"""
        struct = WaveformStruct.from_adapter(mock_waveforms_vx2730, "vx2730")
        assert struct.config.format_spec.name == "vx2730_csv"
        st_waveforms = struct.structure_waveforms()
        assert len(st_waveforms) == 2
        # 实际波形长度从数据自动检测
        assert st_waveforms[0]["wave"].shape[1] == 5000

    def test_custom_format_config(self, mock_waveforms_custom):
        """测试自定义格式配置"""
        custom_spec = FormatSpec(
            name="custom_daq",
            columns=ColumnMapping(
                board=0,
                channel=1,
                timestamp=3,  # 时间戳在列3
                samples_start=10,  # 波形数据从列10开始
                baseline_start=10,
                baseline_end=50,
            ),
        )
        # 显式设置 wave_length
        config = WaveformStructConfig(format_spec=custom_spec, wave_length=1000)
        struct = WaveformStruct(mock_waveforms_custom, config=config)

        # 验证配置应用
        assert struct.config.format_spec.name == "custom_daq"
        assert struct.config.get_wave_length() == 1000

        # 验证结构化
        st_waveforms = struct.structure_waveforms()
        assert len(st_waveforms) == 2
        assert st_waveforms[0]["wave"].shape[1] == 1000

    def test_column_mapping_applied(self, mock_waveforms_custom):
        """测试列映射正确应用"""
        custom_spec = FormatSpec(
            name="custom_daq",
            columns=ColumnMapping(
                board=0,
                channel=1,
                timestamp=3,  # 时间戳在列3（不是VX2730的列2）
                samples_start=10,
                baseline_start=10,
                baseline_end=50,
            ),
        )
        config = WaveformStructConfig(format_spec=custom_spec, wave_length=1000)
        struct = WaveformStruct(mock_waveforms_custom, config=config)

        # 结构化第一个通道
        st_waveform = struct._structure_waveform(mock_waveforms_custom[0])

        # 验证时间戳从列3读取
        expected_timestamps = np.arange(10) * 1000
        np.testing.assert_array_equal(st_waveform["timestamp"], expected_timestamps)

        # 验证通道号
        assert np.all(st_waveform["channel"] == 0)

    def test_dynamic_wave_length(self, mock_waveforms_custom):
        """测试动态波形长度"""
        custom_spec = FormatSpec(
            name="custom_daq",
            columns=ColumnMapping(
                board=0,
                channel=1,
                timestamp=3,
                samples_start=10,
                baseline_start=10,
                baseline_end=50,
            ),
        )
        config = WaveformStructConfig(format_spec=custom_spec, wave_length=1000)
        struct = WaveformStruct(mock_waveforms_custom, config=config)

        # 验证 dtype 波形长度
        assert struct.record_dtype["wave"].shape == (1000,)

        # 结构化并验证
        st_waveforms = struct.structure_waveforms()
        assert st_waveforms[0]["wave"].shape == (10, 1000)

    def test_auto_detect_wave_length(self, mock_waveforms_custom):
        """测试自动检测波形长度（不设置 wave_length）"""
        custom_spec = FormatSpec(
            name="custom_daq",
            columns=ColumnMapping(
                board=0,
                channel=1,
                timestamp=3,
                samples_start=10,
                baseline_start=10,
                baseline_end=50,
            ),
        )
        # 不设置 wave_length，依赖自动检测
        config = WaveformStructConfig(format_spec=custom_spec, wave_length=None)
        struct = WaveformStruct(mock_waveforms_custom, config=config)

        # 结构化时应自动检测实际波形长度
        st_waveforms = struct.structure_waveforms()
        # 实际数据有 1000 个采样点
        assert st_waveforms[0]["wave"].shape == (10, 1000)


class TestWaveformStructEdgeCases:
    """测试边界情况"""

    def test_empty_waveforms(self):
        """测试空波形列表"""
        struct = WaveformStruct([])
        st_waveforms = struct.structure_waveforms()
        assert len(st_waveforms) == 0

    def test_zero_length_waveforms(self):
        """测试零长度波形数组"""
        waveforms = [np.zeros((0, 807))]
        struct = WaveformStruct(waveforms)
        st_waveforms = struct.structure_waveforms()
        assert len(st_waveforms) == 1
        assert len(st_waveforms[0]) == 0

    def test_mismatched_wave_length(self):
        """测试实际波形长度与配置不匹配时的处理"""
        # 创建实际长度为500的波形数据
        n_events = 5
        n_samples = 500
        waveforms = []
        data = np.zeros((n_events, 7 + n_samples))
        data[:, 0] = 0  # BOARD
        data[:, 1] = 0  # CHANNEL
        data[:, 2] = np.arange(n_events) * 1000  # TIMETAG
        data[:, 7:] = np.random.randn(n_events, n_samples) * 10 + 100
        waveforms.append(data)

        # 配置期望长度为800（但实际数据只有500）
        config = WaveformStructConfig(format_spec=VX2730_SPEC, wave_length=800)
        struct = WaveformStruct(waveforms, config=config)

        # 应该使用实际长度创建动态 dtype
        st_waveforms = struct.structure_waveforms()
        assert st_waveforms[0]["wave"].shape == (n_events, n_samples)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
