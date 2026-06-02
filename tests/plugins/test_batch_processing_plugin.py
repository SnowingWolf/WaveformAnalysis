"""
测试 BatchProcessingPlugin 基类
"""

import numpy as np
import pytest

from tests.utils import DummyContext
from waveform_analysis.core.plugins.core import BatchProcessingPlugin, Option
from waveform_analysis.core.processing.chunk import Chunk
from waveform_analysis.core.processing.dtypes import create_record_dtype


class SimpleBatchPlugin(BatchProcessingPlugin):
    """简单的批处理插件用于测试"""

    provides = "simple_batch_output"
    depends_on = ["st_waveforms"]
    chunk_size = 10
    parallel = False  # 测试时禁用并行避免复杂性

    options = {
        "multiplier": Option(default=2.0, type=float, help="乘数"),
    }

    output_dtype = np.dtype(
        [
            ("record_id", np.int64),
            ("value", np.float32),
            ("timestamp", np.int64),  # 添加时间字段
        ]
    )

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        """处理单个 chunk"""
        multiplier = float(context.get_config(self, "multiplier"))

        data = chunk.data
        result = np.zeros(len(data), dtype=self.output_dtype)
        result["record_id"] = data["record_id"]
        result["value"] = data["baseline"] * multiplier
        result["timestamp"] = data["timestamp"]  # 复制时间戳

        return Chunk(
            data=result,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
            time_field="timestamp",  # 指定时间字段
        )


def _make_test_data(n_events=100, wave_len=64):
    """创建测试数据"""
    dtype = create_record_dtype(wave_len)
    data = np.zeros(n_events, dtype=dtype)
    data["baseline"] = 100.0
    data["timestamp"] = np.arange(n_events) * 1000 + 1_000_000
    data["record_id"] = np.arange(n_events, dtype=np.int64)
    data["channel"] = 0
    data["dt"] = 2
    data["event_length"] = wave_len
    data["wave"] = 100
    return data


def test_batch_processing_plugin_basic():
    """测试基本的批处理功能"""
    plugin = SimpleBatchPlugin()
    data = _make_test_data(n_events=25)

    ctx = DummyContext(
        config={"multiplier": 2.0},
        data={"st_waveforms": data},
    )

    result = plugin.compute_array(ctx, "run_001")

    # 验证结果
    assert len(result) == 25
    assert result.dtype == plugin.output_dtype
    assert np.all(result["record_id"] == np.arange(25))
    assert np.allclose(result["value"], 200.0)  # 100.0 * 2.0


def test_batch_processing_plugin_empty_input():
    """测试空输入"""
    plugin = SimpleBatchPlugin()
    data = _make_test_data(n_events=0)

    ctx = DummyContext(
        config={"multiplier": 2.0},
        data={"st_waveforms": data},
    )

    result = plugin.compute_array(ctx, "run_001")

    # 验证结果
    assert len(result) == 0
    assert result.dtype == plugin.output_dtype


def test_batch_processing_plugin_chunking():
    """测试分块处理"""
    plugin = SimpleBatchPlugin()
    plugin.chunk_size = 10  # 每个 chunk 10 条记录

    data = _make_test_data(n_events=35)  # 会分成 4 个 chunks: 10, 10, 10, 5

    ctx = DummyContext(
        config={"multiplier": 3.0},
        data={"st_waveforms": data},
    )

    result = plugin.compute_array(ctx, "run_001")

    # 验证结果
    assert len(result) == 35
    assert np.all(result["record_id"] == np.arange(35))
    assert np.allclose(result["value"], 300.0)  # 100.0 * 3.0


def test_batch_processing_plugin_config():
    """测试配置选项"""
    plugin = SimpleBatchPlugin()
    data = _make_test_data(n_events=20)

    # 测试不同的 multiplier 值
    for multiplier in [1.0, 2.5, 10.0]:
        ctx = DummyContext(
            config={"multiplier": multiplier},
            data={"st_waveforms": data},
        )

        result = plugin.compute_array(ctx, "run_001")

        assert len(result) == 20
        assert np.allclose(result["value"], 100.0 * multiplier)


def test_batch_processing_plugin_inheritance():
    """测试继承关系"""
    plugin = SimpleBatchPlugin()

    # 验证继承自 BatchProcessingPlugin
    from waveform_analysis.core.plugins.core import BatchProcessingPlugin

    assert isinstance(plugin, BatchProcessingPlugin)

    # 验证继承自 StreamingPlugin
    from waveform_analysis.core.plugins.core import StreamingPlugin

    assert isinstance(plugin, StreamingPlugin)

    # 验证继承自 Plugin
    from waveform_analysis.core.plugins.core import Plugin

    assert isinstance(plugin, Plugin)


def test_batch_processing_plugin_attributes():
    """测试插件属性"""
    plugin = SimpleBatchPlugin()

    # 验证基本属性
    assert plugin.provides == "simple_batch_output"
    assert plugin.depends_on == ["st_waveforms"]
    assert plugin.chunk_size == 10
    assert plugin.parallel is False
    assert plugin.output_kind == "static"
    assert plugin.is_stateful is False


def test_batch_processing_plugin_large_dataset():
    """测试大数据集"""
    plugin = SimpleBatchPlugin()
    plugin.chunk_size = 1000

    # 创建较大的数据集
    data = _make_test_data(n_events=5000)

    ctx = DummyContext(
        config={"multiplier": 2.0},
        data={"st_waveforms": data},
    )

    result = plugin.compute_array(ctx, "run_001")

    # 验证结果
    assert len(result) == 5000
    assert np.all(result["record_id"] == np.arange(5000))
    assert np.allclose(result["value"], 200.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
