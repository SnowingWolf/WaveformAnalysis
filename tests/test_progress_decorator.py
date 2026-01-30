#!/usr/bin/env python
"""
进度追踪装饰器的单元测试
"""

import time

import pytest

from waveform_analysis.core.foundation.progress import (
    ProgressTracker,
    format_throughput,
    format_time,
    get_global_tracker,
    progress_iter,
    progress_map,
    reset_global_tracker,
    with_progress,
)


class TestProgressTracker:
    """测试 ProgressTracker 基础功能"""

    def test_create_and_close_bar(self):
        """测试创建和关闭进度条"""
        tracker = ProgressTracker(disable=True)  # 禁用显示以便测试
        bar_name = tracker.create_bar("test", total=100, desc="Test")

        assert bar_name == "test"
        assert "test" in tracker._bars

        tracker.close("test")
        assert "test" not in tracker._bars

    def test_update_bar(self):
        """测试更新进度"""
        tracker = ProgressTracker(disable=True)
        tracker.create_bar("test", total=100, desc="Test")

        tracker.update("test", n=10)
        assert tracker._bars["test"].n == 10

        tracker.update("test", n=5)
        assert tracker._bars["test"].n == 15

        tracker.close("test")

    def test_context_manager(self):
        """测试上下文管理器"""
        with ProgressTracker(disable=True) as tracker:
            tracker.create_bar("test", total=100, desc="Test")
            tracker.update("test", n=50)

        # 上下文退出后，所有进度条应该被关闭
        assert len(tracker._bars) == 0

    def test_nested_bars(self):
        """测试嵌套进度条"""
        tracker = ProgressTracker(disable=True)

        # 创建父进度条
        tracker.create_bar("parent", total=10, desc="Parent")

        # 创建子进度条
        tracker.create_bar("child1", total=100, desc="Child 1", nested=True, parent="parent")
        tracker.create_bar("child2", total=100, desc="Child 2", nested=True, parent="parent")

        # 验证嵌套结构
        assert tracker._bar_info["child1"]["parent"] == "parent"
        assert tracker._bar_info["child2"]["parent"] == "parent"
        assert tracker._bar_info["parent"]["nested_count"] == 2

        tracker.close_all()

    def test_calculate_throughput(self):
        """测试吞吐量计算"""
        tracker = ProgressTracker(disable=True)
        tracker.create_bar("test", total=100, desc="Test")

        # 模拟一些处理
        time.sleep(0.1)
        tracker.update("test", n=10)

        throughput = tracker.calculate_throughput("test")
        assert throughput is not None
        assert throughput > 0

        tracker.close("test")


class TestProgressDecorator:
    """测试 @with_progress 装饰器"""

    def test_generator_function(self):
        """测试装饰生成器函数"""

        @with_progress(total=10, desc="Test", disable=True)
        def generate_items():
            yield from range(10)

        result = list(generate_items())
        assert len(result) == 10
        assert result == list(range(10))

    def test_function_returning_list(self):
        """测试返回列表的函数"""

        @with_progress(desc="Test", disable=True)
        def get_items():
            return [1, 2, 3, 4, 5]

        result = list(get_items())
        assert len(result) == 5
        assert result == [1, 2, 3, 4, 5]

    def test_regular_function(self):
        """测试普通函数"""

        @with_progress(desc="Test", disable=True, show_result=True)
        def compute():
            return 42

        result = compute()
        assert result == 42

    def test_function_with_args(self):
        """测试带参数的函数"""

        @with_progress(total=5, desc="Test", disable=True)
        def process_items(items, multiplier=1):
            for item in items:
                yield item * multiplier

        result = list(process_items([1, 2, 3, 4, 5], multiplier=2))
        assert result == [2, 4, 6, 8, 10]


class TestProgressIter:
    """测试 progress_iter 函数"""

    def test_basic_iteration(self):
        """测试基本迭代"""
        data = [1, 2, 3, 4, 5]
        result = list(progress_iter(data, desc="Test", disable=True))
        assert result == data

    def test_auto_total(self):
        """测试自动推断总数"""
        data = list(range(100))
        result = list(progress_iter(data, desc="Test", disable=True))
        assert len(result) == 100

    def test_generator_input(self):
        """测试生成器输入"""

        def gen():
            yield from range(10)

        result = list(progress_iter(gen(), total=10, desc="Test", disable=True))
        assert len(result) == 10


class TestProgressMap:
    """测试 progress_map 函数"""

    def test_basic_map(self):
        """测试基本映射"""
        data = [1, 2, 3, 4, 5]
        result = progress_map(lambda x: x * 2, data, desc="Test", disable=True)
        assert result == [2, 4, 6, 8, 10]

    def test_map_with_function(self):
        """测试使用函数"""

        def square(x):
            return x**2

        data = range(10)
        result = progress_map(square, data, desc="Test", disable=True)
        assert result == [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]


class TestGlobalTracker:
    """测试全局追踪器"""

    def test_get_global_tracker(self):
        """测试获取全局追踪器"""
        reset_global_tracker()
        tracker1 = get_global_tracker()
        tracker2 = get_global_tracker()

        # 应该返回同一个实例
        assert tracker1 is tracker2

    def test_reset_global_tracker(self):
        """测试重置全局追踪器"""
        tracker1 = get_global_tracker()
        tracker1.create_bar("test", total=100, desc="Test", disable=True)

        reset_global_tracker()

        tracker2 = get_global_tracker()
        # 应该是新的实例
        assert tracker2 is not tracker1
        # 新实例应该没有进度条
        assert len(tracker2._bars) == 0


class TestUtilityFunctions:
    """测试工具函数"""

    def test_format_time(self):
        """测试时间格式化"""
        assert format_time(30) == "30s"
        assert format_time(90) == "01:30"
        assert format_time(3665) == "01:01:05"

    def test_format_throughput(self):
        """测试吞吐量格式化"""
        assert format_throughput(0.5, "items") == "0.50 items/s"
        assert format_throughput(5.5, "items") == "5.5 items/s"
        assert format_throughput(123.456, "items") == "123 items/s"


# ===========================
# 集成测试
# ===========================


class TestIntegration:
    """集成测试"""

    def test_complete_workflow(self):
        """测试完整工作流"""

        @with_progress(total=5, desc="Processing", unit="item", disable=True)
        def process_items(items):
            results = []
            for item in items:
                results.append(item * 2)
                yield item * 2

        data = [1, 2, 3, 4, 5]
        result = list(process_items(data))

        assert result == [2, 4, 6, 8, 10]

    def test_nested_progress(self):
        """测试嵌套进度"""
        tracker = ProgressTracker(disable=True)

        tracker.create_bar("main", total=3, desc="Main")

        for i in range(3):
            bar_name = f"sub_{i}"
            tracker.create_bar(bar_name, total=10, desc=f"Sub {i}", nested=True, parent="main")

            for _j in range(10):
                tracker.update(bar_name, n=1)

            tracker.close(bar_name)
            tracker.update("main", n=1)

        tracker.close("main")

        # 验证所有进度条都已关闭
        assert len(tracker._bars) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
