# -*- coding: utf-8 -*-
"""
时间转换模块单元测试

测试内容：
- EpochInfo 创建和序列化
- TimeConverter 双向转换
- EpochExtractor 文件名解析
- TimeIndex 绝对时间查询
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import os

from waveform_analysis.core.foundation.time_conversion import (
    EpochInfo,
    TimeConverter,
    EpochExtractor,
)
from waveform_analysis.utils.formats.base import TimestampUnit


class TestEpochInfo:
    """EpochInfo 数据类测试"""

    def test_from_datetime_utc(self):
        """测试从 UTC datetime 创建 EpochInfo"""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        epoch = EpochInfo.from_datetime(dt, source="test")

        assert epoch.epoch_datetime == dt
        assert epoch.epoch_source == "test"
        assert epoch.time_unit == TimestampUnit.NANOSECONDS
        assert abs(epoch.epoch_timestamp - dt.timestamp()) < 1e-6

    def test_from_datetime_no_timezone(self):
        """测试从无时区 datetime 创建（应假定 UTC）"""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        epoch = EpochInfo.from_datetime(dt, source="test")

        assert epoch.epoch_datetime.tzinfo == timezone.utc

    def test_from_timestamp(self):
        """测试从 Unix 时间戳创建 EpochInfo"""
        ts = 1704110400.0  # 2024-01-01 12:00:00 UTC
        epoch = EpochInfo.from_timestamp(ts, source="manual")

        assert abs(epoch.epoch_timestamp - ts) < 1e-6
        assert epoch.epoch_source == "manual"

    def test_to_dict_and_from_dict(self):
        """测试 JSON 序列化和反序列化"""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        original = EpochInfo.from_datetime(dt, source="test", time_unit=TimestampUnit.PICOSECONDS)

        # 序列化
        data = original.to_dict()
        assert "epoch_timestamp" in data
        assert "epoch_datetime" in data
        assert "epoch_source" in data
        assert "time_unit" in data

        # 反序列化
        restored = EpochInfo.from_dict(data)
        assert abs(restored.epoch_timestamp - original.epoch_timestamp) < 1e-6
        assert restored.epoch_source == original.epoch_source
        assert restored.time_unit == original.time_unit


class TestTimeConverter:
    """TimeConverter 双向转换测试"""

    @pytest.fixture
    def converter(self):
        """创建测试用转换器"""
        dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        epoch = EpochInfo.from_datetime(dt, source="test", time_unit=TimestampUnit.NANOSECONDS)
        return TimeConverter(epoch)

    @pytest.fixture
    def converter_ps(self):
        """创建皮秒单位转换器"""
        dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        epoch = EpochInfo.from_datetime(dt, source="test", time_unit=TimestampUnit.PICOSECONDS)
        return TimeConverter(epoch)

    def test_relative_to_absolute_scalar(self, converter):
        """测试标量相对时间转绝对时间"""
        # 1秒 = 1e9 纳秒
        relative_ns = 1_000_000_000
        result = converter.relative_to_absolute(relative_ns)

        expected = datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
        assert result == expected

    def test_absolute_to_relative_scalar(self, converter):
        """测试标量绝对时间转相对时间"""
        dt = datetime(2024, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        result = converter.absolute_to_relative(dt)

        expected = 10_000_000_000  # 10秒 = 10e9 纳秒
        assert result == expected

    def test_roundtrip_conversion(self, converter):
        """测试往返转换精度"""
        original_ns = 123_456_789_012  # 123.456789012 秒

        # 相对 → 绝对 → 相对
        absolute = converter.relative_to_absolute(original_ns)
        restored = converter.absolute_to_relative(absolute)

        # 允许 10 纳秒误差（浮点精度）
        assert abs(restored - original_ns) <= 10

    def test_relative_to_absolute_array(self, converter):
        """测试数组相对时间转绝对时间"""
        relative_ns = np.array([0, 1_000_000_000, 2_000_000_000])
        result = converter.relative_to_absolute(relative_ns)

        assert isinstance(result, np.ndarray)
        assert result.dtype == np.dtype('datetime64[ns]')
        assert len(result) == 3

    def test_absolute_to_relative_array(self, converter):
        """测试数组绝对时间转相对时间"""
        dts = np.array(['2024-01-01T00:00:00', '2024-01-01T00:00:01'], dtype='datetime64[s]')
        result = converter.absolute_to_relative(dts)

        assert isinstance(result, np.ndarray)
        assert result[0] == 0
        # 允许 1 秒精度损失（因为 datetime64[s] 精度）
        assert abs(result[1] - 1_000_000_000) <= 1

    def test_convert_time_range(self, converter):
        """测试时间范围转换"""
        start = datetime(2024, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 0, 0, 20, tzinfo=timezone.utc)

        start_rel, end_rel = converter.convert_time_range(start, end)

        assert start_rel == 10_000_000_000
        assert end_rel == 20_000_000_000

    def test_convert_time_range_none(self, converter):
        """测试时间范围转换（边界为 None）"""
        start_rel, end_rel = converter.convert_time_range(None, None)

        assert start_rel is None
        assert end_rel is None

    def test_picoseconds_conversion(self, converter_ps):
        """测试皮秒单位转换"""
        # 1秒 = 1e12 皮秒
        relative_ps = 1_000_000_000_000
        result = converter_ps.relative_to_absolute(relative_ps)

        expected = datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
        assert result == expected


class TestEpochExtractor:
    """EpochExtractor 文件名解析测试"""

    @pytest.fixture
    def extractor(self):
        """创建测试用提取器"""
        return EpochExtractor()

    def test_extract_iso_format(self, extractor):
        """测试 ISO 8601 格式文件名"""
        result = extractor.extract_from_filename("data_2024-01-15_14-30-45.csv")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 45

    def test_extract_compact_format(self, extractor):
        """测试紧凑格式文件名"""
        result = extractor.extract_from_filename("run_20240115143045_CH0.csv")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 45

    def test_extract_underscore_format(self, extractor):
        """测试下划线分隔格式"""
        result = extractor.extract_from_filename("data_2024_01_15_143045.csv")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_extract_date_only(self, extractor):
        """测试仅日期格式"""
        result = extractor.extract_from_filename("data_2024-01-15.csv")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_extract_no_match(self, extractor):
        """测试无法匹配的文件名"""
        result = extractor.extract_from_filename("unknown_format.csv")

        assert result is None

    def test_extract_from_path(self, extractor):
        """测试从完整路径提取"""
        result = extractor.extract_from_filename("/path/to/data_2024-01-15_14-30-45.csv")

        assert result is not None
        assert result.year == 2024

    def test_auto_extract_success(self, extractor):
        """测试自动提取（成功场景）"""
        files = [
            "data_2024-01-15_14-30-45_CH0.csv",
            "data_2024-01-15_14-30-45_CH1.csv",
        ]
        result = extractor.auto_extract(files, strategy="filename")

        assert result.epoch_source == "filename"
        assert result.epoch_datetime.year == 2024

    def test_auto_extract_failure(self, extractor):
        """测试自动提取（失败场景）"""
        files = ["unknown1.csv", "unknown2.csv"]

        with pytest.raises(ValueError, match="无法从文件中提取 epoch"):
            extractor.auto_extract(files, strategy="filename")

    def test_custom_patterns(self):
        """测试自定义文件名模式"""
        # 自定义模式：exp_YYYYMMDDHHMMSS_data.csv
        custom_patterns = [
            (r"exp_(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", "%Y%m%d%H%M%S"),
        ]
        extractor = EpochExtractor(filename_patterns=custom_patterns)

        result = extractor.extract_from_filename("exp_20240115143045_data.csv")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 45


class TestEpochExtractorCSVHeader:
    """EpochExtractor CSV 头部解析测试"""

    def test_extract_from_csv_header_iso(self, tmp_path):
        """测试从 CSV 头部提取 ISO 格式时间戳"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "# Epoch: 2024-01-15T14:30:45+00:00\n"
            "# Other header\n"
            "col1;col2;col3\n"
            "1;2;3\n"
        )

        extractor = EpochExtractor()
        result = extractor.extract_from_csv_header(str(csv_file))

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_extract_from_csv_header_unix(self, tmp_path):
        """测试从 CSV 头部提取 Unix 时间戳"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "# timestamp: 1705327845\n"
            "col1;col2;col3\n"
        )

        extractor = EpochExtractor()
        result = extractor.extract_from_csv_header(str(csv_file))

        assert result is not None

    def test_extract_from_csv_header_not_found(self, tmp_path):
        """测试 CSV 头部无时间戳"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "# Some header\n"
            "col1;col2;col3\n"
        )

        extractor = EpochExtractor()
        result = extractor.extract_from_csv_header(str(csv_file))

        assert result is None


class TestTimeIndexAbsolute:
    """TimeIndex 绝对时间查询测试"""

    @pytest.fixture
    def time_index_with_epoch(self):
        """创建带 epoch 的 TimeIndex"""
        from waveform_analysis.core.data.query import TimeIndex

        # 创建测试数据：10 条记录，时间从 0 到 9 秒（纳秒单位）
        times = np.array([i * 1_000_000_000 for i in range(10)], dtype=np.int64)
        indices = np.arange(10, dtype=np.int64)

        # Epoch: 2024-01-01 00:00:00 UTC
        epoch = EpochInfo.from_datetime(
            datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            source="test",
            time_unit=TimestampUnit.NANOSECONDS,
        )

        return TimeIndex(times=times, indices=indices, epoch_info=epoch)

    def test_query_range_absolute(self, time_index_with_epoch):
        """测试绝对时间范围查询"""
        start = datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        result = time_index_with_epoch.query_range_absolute(start, end)

        assert len(result) == 3  # 索引 2, 3, 4
        assert 2 in result
        assert 3 in result
        assert 4 in result

    def test_query_point_absolute(self, time_index_with_epoch):
        """测试绝对时间点查询"""
        dt = datetime(2024, 1, 1, 0, 0, 5, tzinfo=timezone.utc)

        result = time_index_with_epoch.query_point_absolute(dt)

        assert result == 5

    def test_get_time_range_absolute(self, time_index_with_epoch):
        """测试获取绝对时间范围"""
        result = time_index_with_epoch.get_time_range_absolute()

        assert result is not None
        min_dt, max_dt = result
        assert min_dt == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert max_dt == datetime(2024, 1, 1, 0, 0, 9, tzinfo=timezone.utc)

    def test_query_without_epoch_raises(self):
        """测试无 epoch 时查询抛出异常"""
        from waveform_analysis.core.data.query import TimeIndex

        times = np.array([0, 1, 2], dtype=np.int64)
        indices = np.arange(3, dtype=np.int64)
        index = TimeIndex(times=times, indices=indices)  # 无 epoch

        dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="未设置 epoch_info"):
            index.query_range_absolute(dt, dt)


class TestEdgeCases:
    """边界条件和特殊场景测试"""

    def test_epoch_near_unix_epoch(self):
        """测试接近 Unix epoch 的时间"""
        dt = datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
        epoch = EpochInfo.from_datetime(dt, source="test")
        converter = TimeConverter(epoch)

        # 1 秒后
        result = converter.relative_to_absolute(1_000_000_000)
        expected = datetime(1970, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
        assert result == expected

    def test_large_time_values(self):
        """测试大时间值"""
        dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        epoch = EpochInfo.from_datetime(dt, source="test")
        converter = TimeConverter(epoch)

        # 1天后（86400 秒 = 8.64e13 纳秒）
        one_day_ns = 24 * 60 * 60 * 1_000_000_000
        result = converter.relative_to_absolute(one_day_ns)

        expected = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        # 允许 1 秒误差
        assert abs((result - expected).total_seconds()) < 1

    def test_negative_relative_time(self):
        """测试负相对时间（epoch 之前）"""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        epoch = EpochInfo.from_datetime(dt, source="test")
        converter = TimeConverter(epoch)

        # -1小时
        result = converter.relative_to_absolute(-3_600_000_000_000)
        expected = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_empty_file_list(self):
        """测试空文件列表"""
        extractor = EpochExtractor()

        with pytest.raises(ValueError, match="文件路径列表不能为空"):
            extractor.auto_extract([])
