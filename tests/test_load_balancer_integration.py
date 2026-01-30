#!/usr/bin/env python
"""
测试 DynamicLoadBalancer 集成到 ExecutorManager 和 StreamingPlugin
"""

import time

import numpy as np


def test_executor_manager_integration():
    """测试 ExecutorManager 的负载均衡集成"""
    print("=" * 60)
    print("测试 ExecutorManager 集成")
    print("=" * 60)

    from waveform_analysis.core.execution import (
        disable_global_load_balancing,
        enable_global_load_balancing,
        get_load_balancer_stats,
        parallel_apply,
        parallel_map,
    )

    # 1. 启用负载均衡
    print("\n1. 启用全局负载均衡...")
    enable_global_load_balancing(
        min_workers=2, max_workers=8, cpu_threshold=0.8, memory_threshold=0.85, check_interval=1.0
    )
    print("   ✓ 负载均衡已启用")

    # 2. 测试 parallel_map 使用负载均衡
    print("\n2. 测试 parallel_map 使用负载均衡...")

    def process_item(x):
        """模拟处理任务"""
        time.sleep(0.01)
        return x**2

    data = list(range(50))
    results = parallel_map(
        process_item,
        data,
        executor_type="thread",
        use_load_balancer=True,
        estimated_task_size=1024,  # 1KB per task
    )

    assert len(results) == len(data)
    assert results[10] == 100
    print(f"   ✓ 处理了 {len(data)} 个任务")

    # 3. 获取统计信息
    print("\n3. 获取负载均衡统计信息...")
    stats = get_load_balancer_stats()
    if stats:
        print(f"   - 总任务数: {stats['total_tasks']}")
        print(f"   - 成功任务数: {stats['successful_tasks']}")
        print(f"   - 当前 workers: {stats['current_workers']}")
        if stats["total_tasks"] > 0:
            print(f"   - 平均耗时: {stats['avg_duration']:.3f}s")
    else:
        print("   ⚠ 未获取到统计信息")

    # 4. 测试 parallel_apply
    print("\n4. 测试 parallel_apply 使用负载均衡...")

    def add_numbers(x, y):
        """模拟处理任务"""
        time.sleep(0.01)
        return x + y

    args_list = [(i, i * 2) for i in range(30)]
    results = parallel_apply(
        add_numbers,
        args_list,
        executor_type="thread",
        use_load_balancer=True,
        estimated_task_size=512,  # 512B per task
    )

    assert len(results) == len(args_list)
    assert results[10] == 30  # 10 + 20
    print(f"   ✓ 处理了 {len(args_list)} 个任务")

    # 5. 再次获取统计信息
    print("\n5. 更新后的统计信息...")
    stats = get_load_balancer_stats()
    if stats:
        print(f"   - 总任务数: {stats['total_tasks']}")
        print(f"   - 成功任务数: {stats['successful_tasks']}")
        print(f"   - 当前 workers: {stats['current_workers']}")
        if stats["total_tasks"] > 0:
            print(f"   - 平均耗时: {stats['avg_duration']:.3f}s")

    # 6. 禁用负载均衡
    print("\n6. 禁用全局负载均衡...")
    disable_global_load_balancing()
    print("   ✓ 负载均衡已禁用")

    # 7. 验证禁用后无统计信息
    stats = get_load_balancer_stats()
    assert stats is None, "禁用后应返回 None"
    print("   ✓ 确认已禁用")

    print("\n✅ ExecutorManager 集成测试通过")


def test_streaming_plugin_integration():
    """测试 StreamingPlugin 的负载均衡集成"""
    print("\n" + "=" * 60)
    print("测试 StreamingPlugin 集成")
    print("=" * 60)

    from waveform_analysis.core.plugins.core.streaming import StreamingPlugin
    from waveform_analysis.core.processing.chunk import Chunk

    # 1. 创建启用负载均衡的流式插件
    print("\n1. 创建启用负载均衡的流式插件...")

    class TestStreamingPlugin(StreamingPlugin):
        """测试用流式插件"""

        provides = "test_data"
        depends_on = ()
        dtype = np.dtype([("value", np.int32)])

        # 启用负载均衡
        use_load_balancer = True
        load_balancer_config = {"min_workers": 2, "max_workers": 4, "cpu_threshold": 0.75}

        def compute_chunk(self, chunk, context, run_id, **kwargs):
            """处理单个 chunk"""
            time.sleep(0.01)
            # 简单地返回相同的 chunk
            return chunk

    plugin = TestStreamingPlugin()
    print("   ✓ 插件创建成功")
    print(f"   - use_load_balancer: {plugin.use_load_balancer}")
    print(f"   - load_balancer_config: {plugin.load_balancer_config}")

    # 2. 验证负载均衡器已初始化
    print("\n2. 验证负载均衡器...")
    assert plugin._load_balancer is not None, "负载均衡器应已初始化"
    print("   ✓ 负载均衡器已初始化")

    # 3. 获取插件的负载均衡统计
    print("\n3. 获取初始统计信息...")
    stats = plugin.get_load_balancer_stats()
    if stats:
        print(f"   - 总任务数: {stats['total_tasks']}")
        print(f"   - 当前 workers: {stats['current_workers']}")

    # 4. 测试并行处理（模拟）
    print("\n4. 测试并行处理...")

    # 创建测试 chunks
    def create_test_chunks(n=20):
        """创建测试 chunks"""
        # 使用正确的 dtype，包含 time, dt, length 字段
        dtype = np.dtype(
            [("time", np.int64), ("dt", np.int32), ("length", np.int32), ("value", np.int32)]
        )
        for i in range(n):
            data = np.array([(i * 100, 1, 100, i)], dtype=dtype)
            yield Chunk(
                data=data,
                start=i * 100,
                end=(i + 1) * 100,
                run_id="test_run",
                data_type="test_data",
            )

    # 模拟并行处理
    input_chunks = create_test_chunks(20)
    output_chunks = list(plugin._compute_parallel(input_chunks, context=None, run_id="test_run"))

    assert len(output_chunks) == 20
    print(f"   ✓ 处理了 {len(output_chunks)} 个 chunks")

    # 5. 获取更新后的统计信息
    print("\n5. 更新后的统计信息...")
    stats = plugin.get_load_balancer_stats()
    if stats:
        print(f"   - 总任务数: {stats['total_tasks']}")
        print(f"   - 成功任务数: {stats['successful_tasks']}")
        print(f"   - 当前 workers: {stats['current_workers']}")
        if stats["total_tasks"] > 0:
            print(f"   - 平均耗时: {stats['avg_duration']:.3f}s")

    print("\n✅ StreamingPlugin 集成测试通过")


def test_backward_compatibility():
    """测试向后兼容性（默认不启用负载均衡）"""
    print("\n" + "=" * 60)
    print("测试向后兼容性")
    print("=" * 60)

    from waveform_analysis.core.execution import get_load_balancer_stats, parallel_map
    from waveform_analysis.core.plugins.core.streaming import StreamingPlugin

    # 1. 默认情况下，负载均衡未启用
    print("\n1. 验证默认未启用负载均衡...")
    stats = get_load_balancer_stats()
    assert stats is None, "默认情况下应返回 None"
    print("   ✓ 默认未启用")

    # 2. parallel_map 仍然正常工作
    print("\n2. 测试 parallel_map 默认行为...")

    def process(x):
        return x * 2

    results = parallel_map(process, list(range(10)), executor_type="thread")
    assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]
    print("   ✓ parallel_map 正常工作")

    # 3. StreamingPlugin 默认不使用负载均衡
    print("\n3. 验证 StreamingPlugin 默认行为...")

    class DefaultPlugin(StreamingPlugin):
        provides = "default_data"
        depends_on = ()
        dtype = np.dtype([("value", np.int32)])

    plugin = DefaultPlugin()
    assert plugin.use_load_balancer is False
    assert plugin._load_balancer is None
    print("   ✓ StreamingPlugin 默认未启用负载均衡")

    print("\n✅ 向后兼容性测试通过")


if __name__ == "__main__":
    print("\n" + "🚀 开始测试 DynamicLoadBalancer 集成" + "\n")

    try:
        # 测试 ExecutorManager 集成
        test_executor_manager_integration()

        # 测试 StreamingPlugin 集成
        test_streaming_plugin_integration()

        # 测试向后兼容性
        test_backward_compatibility()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
