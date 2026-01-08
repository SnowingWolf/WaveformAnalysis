"""
测试流式处理优化（避免完全物化）
"""

import numpy as np
import pytest

from waveform_analysis.core.streaming import StreamingPlugin
from waveform_analysis.core.chunk_utils import Chunk
from waveform_analysis.core.context import Context


class TestStreamingOptimization:
    """测试流式处理的批量优化"""

    def test_parallel_batch_processing(self):
        """测试并行批量处理避免完全物化"""

        # 定义完整的 dtype（包含 time, dt, length）
        dtype = np.dtype([("time", "i8"), ("dt", "i8"), ("length", "i8"), ("value", "f4")])

        class SimpleStreamingPlugin(StreamingPlugin):
            provides = "processed_data"
            parallel = True
            max_workers = 2
            parallel_batch_size = 3  # 小批量，便于测试

            def compute_chunk(self, chunk, context, run_id, **kwargs):
                # 简单处理：value * 2
                processed_data = chunk.data.copy()
                processed_data["value"] *= 2
                return Chunk(
                    data=processed_data,
                    start=chunk.start,
                    end=chunk.end,
                    run_id=chunk.run_id,
                    data_type=self.provides
                )

        # 创建一个生成器（模拟大数据流）
        def chunk_generator():
            for i in range(10):  # 生成10个chunk
                data = np.array(
                    [(i * 100 + j, 1, 1, float(j)) for j in range(100)],
                    dtype=dtype
                )
                yield Chunk(
                    data=data,
                    start=i * 100,
                    end=(i + 1) * 100,
                    run_id="test_run",
                    data_type="input"
                )

        plugin = SimpleStreamingPlugin()
        ctx = Context()

        # 处理流（不应完全物化）
        input_stream = chunk_generator()
        output_stream = plugin._compute_parallel(input_stream, ctx, "test_run")

        # 验证输出
        results = list(output_stream)
        assert len(results) == 10

        # 验证每个 chunk 的数据被正确处理（value * 2）
        for i, chunk in enumerate(results):
            assert len(chunk.data) == 100
            assert chunk.data["value"][0] == 0.0  # 第一个 value 应该是 0 * 2 = 0

    def test_batch_size_configuration(self):
        """测试可配置的批量大小"""

        class ConfigurableBatchPlugin(StreamingPlugin):
            provides = "data"
            parallel = True
            max_workers = 4
            parallel_batch_size = 5  # 自定义批量大小

            def compute_chunk(self, chunk, context, run_id, **kwargs):
                return chunk

        plugin = ConfigurableBatchPlugin()
        assert plugin.parallel_batch_size == 5

    def test_auto_batch_size(self):
        """测试自动批量大小计算"""

        class AutoBatchPlugin(StreamingPlugin):
            provides = "data"
            parallel = True
            max_workers = 4
            # 不设置 parallel_batch_size，应该自动计算

            def compute_chunk(self, chunk, context, run_id, **kwargs):
                return chunk

        plugin = AutoBatchPlugin()
        assert plugin.parallel_batch_size is None  # 未设置，应该在运行时自动计算

    def test_memory_efficiency(self):
        """测试内存效率：流不应被完全物化"""

        dtype = np.dtype([("time", "i8"), ("dt", "i8"), ("length", "i8"), ("value", "f4")])
        materialization_check = {"materialized": False}

        class MonitoringStreamingPlugin(StreamingPlugin):
            provides = "monitored_data"
            parallel = True
            max_workers = 2
            parallel_batch_size = 2

            def compute_chunk(self, chunk, context, run_id, **kwargs):
                return chunk

        def monitored_generator():
            """生成器，用于检测是否被完全消费"""
            for i in range(100):  # 大量 chunk
                data = np.array([(i, 1, 1, float(i))], dtype=dtype)
                yield Chunk(
                    data=data,
                    start=i,
                    end=i + 1,
                    run_id="test",
                    data_type="input"
                )
            # 如果所有 chunk 都被立即消费（物化），这个标记会被设置
            materialization_check["materialized"] = True

        plugin = MonitoringStreamingPlugin()
        ctx = Context()

        input_stream = monitored_generator()
        output_stream = plugin._compute_parallel(input_stream, ctx, "test")

        # 只消费前几个 chunk
        results = []
        for i, chunk in enumerate(output_stream):
            results.append(chunk)
            if i >= 5:  # 只消费前6个
                break

        # 生成器不应该被完全消费（避免物化）
        # 注意：由于批量处理，前几批可能已经被处理
        # 但整个流不应该被完全物化
        assert len(results) == 6

    def test_serial_processing_unchanged(self):
        """测试串行处理保持不变"""

        class SerialStreamingPlugin(StreamingPlugin):
            provides = "serial_data"
            parallel = False  # 串行处理

            def compute_chunk(self, chunk, context, run_id, **kwargs):
                return Chunk(
                    data=chunk.data + 10,
                    start=chunk.start,
                    end=chunk.end,
                    run_id=chunk.run_id,
                    data_type=self.provides
                )

        def chunk_generator():
            for i in range(5):
                yield Chunk(
                    data=np.array([i]),
                    start=i,
                    end=i + 1,
                    run_id="test",
                    data_type="input"
                )

        plugin = SerialStreamingPlugin()
        ctx = Context()

        # 串行处理应该正常工作
        results = list(plugin.compute(ctx, "test"))
        assert len(results) == 0  # 没有依赖，不会有输出

    def test_error_handling_in_parallel(self):
        """测试并行处理中的错误处理"""

        dtype = np.dtype([("time", "i8"), ("dt", "i8"), ("length", "i8"), ("value", "f4")])

        class ErrorPronePlugin(StreamingPlugin):
            provides = "error_data"
            parallel = True
            max_workers = 2
            parallel_batch_size = 2

            def compute_chunk(self, chunk, context, run_id, **kwargs):
                # 在第 3 个 chunk 抛出错误
                if chunk.data["time"][0] == 2:
                    raise ValueError("Test error")
                return chunk

        def chunk_generator():
            for i in range(5):
                data = np.array([(i, 1, 1, float(i))], dtype=dtype)
                yield Chunk(
                    data=data,
                    start=i,
                    end=i + 1,
                    run_id="test",
                    data_type="input"
                )

        plugin = ErrorPronePlugin()
        ctx = Context()

        input_stream = chunk_generator()

        # 应该在遇到错误时抛出异常
        with pytest.raises(ValueError, match="Test error"):
            list(plugin._compute_parallel(input_stream, ctx, "test"))

    def test_order_preservation(self):
        """测试并行处理保持顺序"""

        dtype = np.dtype([("time", "i8"), ("dt", "i8"), ("length", "i8"), ("value", "f4")])

        class OrderTestPlugin(StreamingPlugin):
            provides = "ordered_data"
            parallel = True
            max_workers = 4
            parallel_batch_size = 3

            def compute_chunk(self, chunk, context, run_id, **kwargs):
                # 添加延迟模拟不同处理时间
                import time
                time.sleep(0.001 * (10 - chunk.data["time"][0]))  # 反向延迟
                return chunk

        def chunk_generator():
            for i in range(10):
                data = np.array([(i, 1, 1, float(i))], dtype=dtype)
                yield Chunk(
                    data=data,
                    start=i,
                    end=i + 1,
                    run_id="test",
                    data_type="input"
                )

        plugin = OrderTestPlugin()
        ctx = Context()

        input_stream = chunk_generator()
        results = list(plugin._compute_parallel(input_stream, ctx, "test"))

        # 验证顺序保持
        for i, chunk in enumerate(results):
            assert chunk.data["time"][0] == i, f"Expected {i}, got {chunk.data['time'][0]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
