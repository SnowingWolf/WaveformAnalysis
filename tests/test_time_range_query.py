"""
测试时间范围查询功能 (Phase 2.2)
"""

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.core.data.query import (
    TimeIndex,
    TimeRangeQueryEngine,
)


class DummyDataPlugin(Plugin):
    """生成测试数据的插件"""

    provides = "test_data"
    depends_on = tuple()
    dtype = [("time", "i8"), ("dt", "i8"), ("length", "i8"), ("value", "f4")]
    version = "0.1.0"

    def compute(self, run_id, context, **kwargs):
        """生成测试数据"""
        n_records = 1000
        times = np.arange(0, n_records * 100, 100, dtype=np.int64)
        data = np.zeros(n_records, dtype=self.dtype)
        data["time"] = times
        data["dt"] = 1
        data["length"] = 50
        data["value"] = np.random.randn(n_records).astype(np.float32)
        return data


def test_time_index_creation():
    """测试时间索引创建"""
    # 创建测试数据
    n = 100
    times = np.arange(0, n * 10, 10, dtype=np.int64)
    data = np.zeros(n, dtype=[("time", "i8"), ("value", "f4")])
    data["time"] = times
    data["value"] = np.random.randn(n)

    # 创建索引
    index = TimeIndex(
        times=data["time"].copy(), indices=np.arange(n, dtype=np.int64)
    )

    assert index.n_records == n
    assert index.min_time == 0
    assert index.max_time == (n - 1) * 10


def test_time_index_query_range():
    """测试时间范围查询"""
    n = 100
    times = np.arange(0, n * 10, 10, dtype=np.int64)
    data = np.zeros(n, dtype=[("time", "i8"), ("value", "f4")])
    data["time"] = times
    data["value"] = np.arange(n, dtype=np.float32)

    index = TimeIndex(
        times=data["time"].copy(), indices=np.arange(n, dtype=np.int64)
    )

    # 查询范围
    indices = index.query_range(100, 300)
    assert len(indices) == 20  # 100, 110, ..., 290
    assert np.array_equal(indices, np.arange(10, 30, dtype=np.int64))

    # 查询边界外
    indices = index.query_range(1000, 2000)
    assert len(indices) == 0

    # 查询部分重叠
    indices = index.query_range(-50, 50)
    assert len(indices) == 5  # 0, 10, 20, 30, 40


def test_time_index_query_point():
    """测试时间点查询"""
    n = 100
    times = np.arange(0, n * 10, 10, dtype=np.int64)
    data = np.zeros(n, dtype=[("time", "i8"), ("value", "f4")])
    data["time"] = times

    index = TimeIndex(
        times=data["time"].copy(), indices=np.arange(n, dtype=np.int64)
    )

    # 查询存在的时间点
    idx = index.query_point(50)
    assert idx == 5

    # 查询不存在的时间点
    idx = index.query_point(55)
    assert idx is None

    # 查询边界外
    idx = index.query_point(1000)
    assert idx is None


def test_time_query_engine():
    """测试时间查询引擎"""
    engine = TimeRangeQueryEngine()

    # 创建测试数据
    n = 100
    data = np.zeros(n, dtype=[("time", "i8"), ("dt", "i8"), ("length", "i8"), ("value", "f4")])
    data["time"] = np.arange(0, n * 10, 10, dtype=np.int64)
    data["dt"] = 1
    data["length"] = 5
    data["value"] = np.arange(n, dtype=np.float32)

    # 构建索引
    index = engine.build_index("run_001", "test_data", data, time_field="time")
    assert index.n_records == n

    # 查询范围
    indices = engine.query("run_001", "test_data", start_time=100, end_time=300)
    assert len(indices) == 20

    # 检查索引统计
    stats = engine.get_stats()
    assert stats["total_indices"] == 1
    assert "run_001.test_data" in stats["indices"]


def test_context_time_range_query():
    """测试Context中的时间范围查询"""
    ctx = Context(storage_dir="./test_time_query_cache")

    # 注册测试插件
    ctx.register_plugin(DummyDataPlugin())

    # 获取数据
    data = ctx.get_data("run_001", "test_data")
    assert len(data) == 1000

    # 时间范围查询
    filtered_data = ctx.get_data_time_range(
        "run_001", "test_data", start_time=1000, end_time=3000
    )
    assert len(filtered_data) == 20  # 时间从1000到2900,步长100

    # 验证数据正确性
    assert filtered_data["time"][0] == 1000
    assert filtered_data["time"][-1] == 2900

    # 查询所有数据之后的范围
    filtered_data = ctx.get_data_time_range(
        "run_001", "test_data", start_time=50000
    )
    assert len(filtered_data) > 0

    # 清理
    ctx.clear_time_index()


def test_context_build_time_index():
    """测试预先构建时间索引"""
    ctx = Context(storage_dir="./test_time_query_cache")
    ctx.register_plugin(DummyDataPlugin())

    # 预先构建索引
    ctx.build_time_index("run_001", "test_data", endtime_field="computed")

    # 验证索引已创建
    stats = ctx.get_time_index_stats()
    assert stats["total_indices"] == 1

    # 查询应该使用索引
    filtered_data = ctx.get_data_time_range(
        "run_001", "test_data", start_time=1000, end_time=3000
    )
    assert len(filtered_data) == 20

    # 清理
    ctx.clear_time_index()


def test_time_index_with_endtime():
    """测试带结束时间的索引"""
    n = 100
    data = np.zeros(n, dtype=[("time", "i8"), ("dt", "i8"), ("length", "i8")])
    data["time"] = np.arange(0, n * 100, 100, dtype=np.int64)
    data["dt"] = 1
    data["length"] = 50

    # 计算endtime
    endtimes = data["time"] + data["dt"] * data["length"]

    index = TimeIndex(
        times=data["time"].copy(),
        indices=np.arange(n, dtype=np.int64),
        endtimes=endtimes,
    )

    # 查询范围应该考虑endtime
    # 第一个记录: time=0, endtime=50
    # 第二个记录: time=100, endtime=150
    # 查询[25, 125)应该包含第一个和第二个记录
    indices = index.query_range(25, 125)
    assert len(indices) >= 1  # 至少包含第一个记录


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
