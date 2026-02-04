"""
DAQ 适配器层测试

测试 formats 模块的各个组件：
- FormatSpec 和 ColumnMapping
- DirectoryLayout
- FormatReader
- DAQAdapter
"""

from pathlib import Path

import pytest

from waveform_analysis.utils.formats import (
    FLAT_LAYOUT,
    VX2730_ADAPTER,
    VX2730_LAYOUT,
    VX2730_SPEC,
    ColumnMapping,
    FormatSpec,
    GenericCSVReader,
    TimestampUnit,
    VX2730Reader,
    get_adapter,
    get_format_reader,
    list_adapters,
    list_formats,
    register_format,
)


class TestFormatSpec:
    """FormatSpec 测试"""

    def test_vx2730_spec(self):
        """测试 VX2730 格式规范"""
        spec = VX2730_SPEC
        assert spec.name == "vx2730_csv"
        assert spec.delimiter == ";"
        assert spec.timestamp_unit == TimestampUnit.PICOSECONDS
        assert spec.header_rows_first_file == 2
        assert spec.header_rows_other_files == 0
        # expected_samples 已移除，波形长度现在由插件配置或自动检测
        assert spec.sampling_rate_hz == 500e6

    def test_timestamp_scale(self):
        """测试时间戳转换因子"""
        spec = FormatSpec(name="test", timestamp_unit=TimestampUnit.PICOSECONDS)
        assert spec.get_timestamp_scale() == 0.001  # ps -> ns

        spec = FormatSpec(name="test", timestamp_unit=TimestampUnit.NANOSECONDS)
        assert spec.get_timestamp_scale() == 1.0  # ns -> ns

        spec = FormatSpec(name="test", timestamp_unit=TimestampUnit.MICROSECONDS)
        assert spec.get_timestamp_scale() == 1e3  # us -> ns

    def test_column_mapping(self):
        """测试列映射"""
        cols = ColumnMapping()
        assert cols.board == 0
        assert cols.channel == 1
        assert cols.timestamp == 2
        assert cols.samples_start == 7
        assert cols.samples_end is None
        assert cols.baseline_start == 7
        assert cols.baseline_end == 47


class TestDirectoryLayout:
    """DirectoryLayout 测试"""

    def test_vx2730_layout(self):
        """测试 VX2730 目录布局"""
        layout = VX2730_LAYOUT
        assert layout.name == "vx2730"
        assert layout.raw_subdir == "RAW"
        assert layout.file_glob_pattern == "*CH*.CSV"

    def test_get_raw_path(self):
        """测试获取原始数据路径"""
        layout = VX2730_LAYOUT
        path = layout.get_raw_path("DAQ", "run_001")
        assert path == Path("DAQ/run_001/RAW")

    def test_flat_layout(self):
        """测试扁平目录布局"""
        layout = FLAT_LAYOUT
        assert layout.name == "flat"
        assert layout.raw_subdir == ""
        path = layout.get_raw_path("DAQ", "run_001")
        assert path == Path("DAQ/run_001")

    def test_extract_channel(self):
        """测试从文件名提取通道号"""
        layout = VX2730_LAYOUT
        assert layout.extract_channel("CH0_0.CSV") == 0
        assert layout.extract_channel("CH5_10.CSV") == 5
        assert layout.extract_channel("data_0.csv") is None

    def test_extract_file_index(self):
        """测试从文件名提取文件索引"""
        layout = VX2730_LAYOUT
        assert layout.extract_file_index("CH0_0.CSV") == 0
        assert layout.extract_file_index("CH0_10.CSV") == 10
        assert layout.extract_file_index("CH0.CSV") == 0


class TestVX2730Reader:
    """VX2730Reader 测试"""

    def test_reader_init(self):
        """测试读取器初始化"""
        reader = VX2730Reader()
        assert reader.spec == VX2730_SPEC

    def test_read_empty_file(self, tmp_path):
        """测试读取空文件"""
        empty_file = tmp_path / "empty.CSV"
        empty_file.touch()

        reader = VX2730Reader()
        data = reader.read_file(empty_file)
        assert data.size == 0

    def test_read_nonexistent_file(self, tmp_path):
        """测试读取不存在的文件"""
        reader = VX2730Reader()
        data = reader.read_file(tmp_path / "nonexistent.CSV")
        assert data.size == 0

    def test_read_simple_csv(self, tmp_path):
        """测试读取简单 CSV 文件"""
        csv_file = tmp_path / "CH0_0.CSV"
        # 创建带头部的 CSV 文件
        content = """HEADER LINE 1
HEADER LINE 2
0;0;1000;0;0;0;0;100;200;300;400
0;0;2000;0;0;0;0;110;210;310;410
"""
        csv_file.write_text(content)

        reader = VX2730Reader()
        data = reader.read_file(csv_file, is_first_file=True)

        assert data.shape[0] == 2  # 2 rows
        assert data[0, 2] == 1000  # timestamp
        assert data[1, 2] == 2000

    def test_extract_columns(self, tmp_path):
        """测试列提取"""
        csv_file = tmp_path / "CH0_0.CSV"
        content = """H1
H2
0;1;1000;0;0;0;0;100;200;300;400;500;600;700;800;900;1000;1100;1200;1300;1400;1500;1600;1700;1800;1900;2000;2100;2200;2300;2400;2500;2600;2700;2800;2900;3000;3100;3200;3300;3400;3500;3600;3700;3800;3900;4000
"""
        csv_file.write_text(content)

        reader = VX2730Reader()
        data = reader.read_file(csv_file)

        extracted = reader.extract_columns(data)

        assert extracted["board"][0] == 0
        assert extracted["channel"][0] == 1
        assert extracted["timestamp"][0] == 1000
        assert extracted["samples"].shape[1] > 0


class TestDAQAdapter:
    """DAQAdapter 测试"""

    def test_vx2730_adapter(self):
        """测试 VX2730 适配器"""
        adapter = VX2730_ADAPTER
        assert adapter.name == "vx2730"
        assert adapter.format_spec == VX2730_SPEC
        assert adapter.directory_layout == VX2730_LAYOUT
        assert adapter.sampling_rate_hz == 500e6

    def test_get_adapter(self):
        """测试获取适配器"""
        adapter = get_adapter("vx2730")
        assert adapter.name == "vx2730"

    def test_get_unknown_adapter(self):
        """测试获取不存在的适配器"""
        with pytest.raises(ValueError, match="未知适配器"):
            get_adapter("unknown_adapter")

    def test_list_adapters(self):
        """测试列出适配器"""
        adapters = list_adapters()
        assert "vx2730" in adapters


class TestRegistry:
    """注册表测试"""

    def test_list_formats(self):
        """测试列出格式"""
        formats = list_formats()
        assert "vx2730_csv" in formats

    def test_get_format_reader(self):
        """测试获取格式读取器"""
        reader = get_format_reader("vx2730_csv")
        assert isinstance(reader, VX2730Reader)

    def test_register_custom_format(self):
        """测试注册自定义格式"""
        custom_spec = FormatSpec(
            name="custom_test",
            delimiter=",",
            timestamp_unit=TimestampUnit.NANOSECONDS,
        )
        register_format("custom_test", GenericCSVReader, custom_spec)

        assert "custom_test" in list_formats()
        reader = get_format_reader("custom_test")
        assert reader.spec.name == "custom_test"


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, tmp_path):
        """测试完整工作流"""
        # 创建目录结构
        raw_dir = tmp_path / "run_001" / "RAW"
        raw_dir.mkdir(parents=True)

        # 创建测试文件
        for ch in range(2):
            for idx in range(2):
                csv_file = raw_dir / f"CH{ch}_{idx}.CSV"
                if idx == 0:
                    content = f"""HEADER 1
HEADER 2
0;{ch};{1000 + idx * 100};0;0;0;0;100;200;300
"""
                else:
                    content = f"""0;{ch};{1000 + idx * 100};0;0;0;0;100;200;300
"""
                csv_file.write_text(content)

        # 使用适配器
        adapter = get_adapter("vx2730")

        # 扫描目录
        channel_files = adapter.scan_run(str(tmp_path), "run_001")
        assert len(channel_files) == 2
        assert 0 in channel_files
        assert 1 in channel_files
        assert len(channel_files[0]) == 2
        assert len(channel_files[1]) == 2

        # 加载通道数据
        data = adapter.load_channel(str(tmp_path), "run_001", channel=0)
        assert data.shape[0] == 2  # 2 rows from 2 files

        # 提取并转换
        extracted = adapter.extract_and_convert(data)
        assert "timestamp" in extracted
        assert "channel" in extracted
        assert extracted["channel"][0] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
