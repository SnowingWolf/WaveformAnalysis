"""
DAQ 适配器层测试

测试 formats 模块的各个组件：
- FormatSpec 和 ColumnMapping
- DirectoryLayout
- FormatReader
- DAQAdapter
"""

from pathlib import Path

import numpy as np
import pytest

from waveform_analysis.core.processing.records_builder import build_records_from_v1725_files
from waveform_analysis.utils.formats import (
    FLAT_LAYOUT,
    VX2730_ADAPTER,
    VX2730_LAYOUT,
    VX2730_SPEC,
    ColumnMapping,
    FormatSpec,
    GenericCSVReader,
    RawTimestampMode,
    TimestampUnit,
    V1725Reader,
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
        assert spec.raw_timestamp_mode == RawTimestampMode.UNIT
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

    def test_normalize_timestamp_to_ps_for_physical_units(self):
        spec = FormatSpec(name="test", timestamp_unit=TimestampUnit.NANOSECONDS)
        timestamps = np.array([10, 20], dtype=np.int64)

        np.testing.assert_array_equal(
            spec.normalize_timestamp_to_ps(timestamps),
            np.array([10_000, 20_000], dtype=np.int64),
        )

    def test_normalize_timestamp_to_ps_for_sample_index(self):
        spec = FormatSpec(
            name="test",
            timestamp_unit=TimestampUnit.NANOSECONDS,
            raw_timestamp_mode=RawTimestampMode.SAMPLE_INDEX,
            sampling_rate_hz=250e6,
        )
        timestamps = np.array([10, 20], dtype=np.int64)

        np.testing.assert_array_equal(
            spec.normalize_timestamp_to_ps(timestamps),
            np.array([40_000, 80_000], dtype=np.int64),
        )
        np.testing.assert_array_equal(
            spec.normalize_timestamp_to_ps(timestamps, dt_ns=8),
            np.array([80_000, 160_000], dtype=np.int64),
        )

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


def _make_v1725_single_wave_blob(
    *,
    channel: int = 0,
    timestamp: int = 1234,
    baseline: int = 321,
    trunc: bool = False,
    samples: np.ndarray | None = None,
) -> bytes:
    if samples is None:
        samples = np.array([11, 12], dtype=np.int16)
    samples = np.asarray(samples, dtype=np.int16)
    payload = samples.tobytes()

    event_header = bytearray(16)
    channel_mask = 1 << int(channel)
    event_header[4] = channel_mask & 0xFF
    event_header[11] = (channel_mask >> 8) & 0xFF

    ch_header = bytearray(12)
    ch_size = 3 + (len(payload) // 4)
    ch_header[0] = ch_size & 0xFF
    ch_header[1] = (ch_size >> 8) & 0xFF
    ch_header[2] = (ch_size >> 16) & 0x3F
    if trunc:
        ch_header[3] |= 0x40
    ch_header[4:10] = int(timestamp).to_bytes(6, byteorder="little", signed=False)
    ch_header[10:12] = int(baseline).to_bytes(2, byteorder="little", signed=False)
    return bytes(event_header + ch_header + payload)


class TestV1725Reader:
    def test_v1725_spec_marks_sample_index_timestamps(self):
        adapter = get_adapter("v1725")
        assert adapter.format_spec.raw_timestamp_mode == RawTimestampMode.SAMPLE_INDEX

    def test_iter_waves_extracts_board_from_bseg_filename(self, tmp_path: Path):
        raw = tmp_path / "test_raw_b7_seg0.bin"
        raw.write_bytes(_make_v1725_single_wave_blob(channel=1, timestamp=77, baseline=555))

        reader = V1725Reader()
        waves = list(reader.iter_waves([raw]))

        assert len(waves) == 1
        assert waves[0].board == 7
        assert waves[0].channel == 1
        assert waves[0].timestamp == 77
        assert waves[0].baseline == 555

    def test_iter_waves_legacy_name_defaults_board_zero(self, tmp_path: Path):
        raw = tmp_path / "CH1_0.bin"
        raw.write_bytes(_make_v1725_single_wave_blob(channel=1, timestamp=88, baseline=444))

        reader = V1725Reader()
        waves = list(reader.iter_waves([raw]))

        assert len(waves) == 1
        assert waves[0].board == 0

    def test_build_records_from_v1725_files_keeps_board_from_filename(self, tmp_path: Path):
        raw0 = tmp_path / "test_raw_b3_seg0.bin"
        raw1 = tmp_path / "test_raw_b4_seg1.bin"
        raw0.write_bytes(_make_v1725_single_wave_blob(channel=0, timestamp=10, baseline=100))
        raw1.write_bytes(_make_v1725_single_wave_blob(channel=1, timestamp=20, baseline=200))

        bundle = build_records_from_v1725_files([str(raw0), str(raw1)], dt_ns=4)

        assert len(bundle.records) == 2
        np.testing.assert_array_equal(bundle.records["board"], np.array([3, 4], dtype=np.int16))
        np.testing.assert_array_equal(bundle.records["channel"], np.array([0, 1], dtype=np.int16))


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
        assert extracted["timestamp"][0] == 1000

        extracted_ns = adapter.extract_and_convert_ns(data)
        assert extracted_ns["timestamp"][0] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
