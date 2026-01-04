"""
utils 模块测试
"""

import time

import pytest

from waveform_analysis.core.utils import (
    LineageStyle,
    OneTimeGenerator,
    Profiler,
    exporter,
    get_plugin_dtype,
    get_plugin_title,
    get_plugins_from_context,
)


class TestExporter:
    """exporter 函数测试"""

    def test_basic_export(self):
        """测试基本导出功能"""
        export, __all__ = exporter()

        @export
        def my_function():
            pass

        @export
        class MyClass:
            pass

        assert "my_function" in __all__
        assert "MyClass" in __all__
        assert len(__all__) == 2

    def test_export_self(self):
        """测试 export_self 参数"""
        export, __all__ = exporter(export_self=True)
        assert "exporter" in __all__

        export2, __all2__ = exporter(export_self=False)
        assert "exporter" not in __all2__

    def test_no_duplicate(self):
        """测试不会重复添加"""
        export, __all__ = exporter()

        @export
        def func():
            pass

        # 再次导出同一个函数
        export(func)

        assert __all__.count("func") == 1

    def test_manual_extend(self):
        """测试手动扩展 __all__"""
        export, __all__ = exporter()

        MY_CONSTANT = 42
        __all__.append("MY_CONSTANT")

        @export
        def func():
            pass

        assert "MY_CONSTANT" in __all__
        assert "func" in __all__

    def test_export_without_name_raises(self):
        """测试导出无 __name__ 对象抛出异常"""
        export, __all__ = exporter()

        with pytest.raises(ValueError, match="it has no __name__ and no name was provided"):
            export(42)  # 整数没有 __name__

    def test_returns_original_object(self):
        """测试装饰器返回原始对象"""
        export, __all__ = exporter()

        def original_func():
            return "hello"

        decorated = export(original_func)

        assert decorated is original_func
        assert decorated() == "hello"


class TestProfiler:
    """Profiler 类测试"""

    def test_init(self):
        """测试初始化"""
        profiler = Profiler()
        assert len(profiler.durations) == 0
        assert len(profiler.counts) == 0

    def test_timeit(self):
        """测试计时功能"""
        profiler = Profiler()

        with profiler.timeit("test_task"):
            time.sleep(0.01)  # 10ms

        assert "test_task" in profiler.durations
        assert profiler.durations["test_task"] >= 0.01
        assert profiler.counts["test_task"] == 1

    def test_timeit_multiple(self):
        """测试多次计时"""
        profiler = Profiler()

        for _ in range(3):
            with profiler.timeit("task"):
                pass

        assert profiler.counts["task"] == 3

    def test_reset(self):
        """测试重置"""
        profiler = Profiler()

        with profiler.timeit("task"):
            pass

        profiler.reset()
        assert len(profiler.durations) == 0
        assert len(profiler.counts) == 0

    def test_profile_decorator(self):
        """测试 Profiler.profile 装饰器"""
        profiler = Profiler()

        @profiler.profile("decorated_func")
        def my_func():
            return "ok"

        result = my_func()
        assert result == "ok"
        assert profiler.counts["decorated_func"] == 1
        assert "decorated_func" in profiler.durations

    def test_summary_empty(self):
        """测试空摘要"""
        profiler = Profiler()
        summary = profiler.summary()
        assert "No profiling data" in summary

    def test_summary_with_data(self):
        """测试带数据的摘要"""
        profiler = Profiler()

        with profiler.timeit("task_a"):
            pass
        with profiler.timeit("task_b"):
            pass

        summary = profiler.summary()
        assert "task_a" in summary
        assert "task_b" in summary


class TestLineageStyle:
    """LineageStyle 类测试"""

    def test_defaults(self):
        """测试默认值"""
        style = LineageStyle()
        assert style.node_width == 3.2
        assert style.node_height == 2.0
        assert style.verbose == 1

    def test_custom_values(self):
        """测试自定义值"""
        style = LineageStyle(node_width=5.0, verbose=2)
        assert style.node_width == 5.0
        assert style.verbose == 2

    def test_type_colors(self):
        """测试类型颜色"""
        style = LineageStyle()
        assert "List[List[str]]" in style.type_colors
        assert "np.ndarray" in style.type_colors


class TestOneTimeGenerator:
    """OneTimeGenerator 类测试"""

    def test_single_consumption(self):
        """测试单次消费"""

        def gen():
            yield 1
            yield 2
            yield 3

        otg = OneTimeGenerator(gen())
        result = list(otg)
        assert result == [1, 2, 3]

    def test_double_consumption_raises(self):
        """测试二次消费抛出异常"""

        def gen():
            yield 1

        otg = OneTimeGenerator(gen())
        list(otg)  # 第一次消费

        with pytest.raises(RuntimeError, match="already been consumed"):
            list(otg)  # 第二次消费应抛出异常

    def test_custom_name(self):
        """测试自定义名称"""

        def gen():
            yield 1

        otg = OneTimeGenerator(gen(), name="MyGenerator")
        list(otg)

        with pytest.raises(RuntimeError, match="MyGenerator"):
            list(otg)


class TestHelperFunctions:
    """辅助函数测试"""

    def test_get_plugins_from_context_none(self):
        """测试空上下文"""
        result = get_plugins_from_context(None)
        assert result == {}

    def test_get_plugins_from_context_with_plugins(self):
        """测试带插件的上下文"""

        class MockContext:
            _plugins = {"plugin1": "value1"}

        result = get_plugins_from_context(MockContext())
        assert result == {"plugin1": "value1"}

    def test_get_plugin_dtype_raw_files(self):
        """测试 raw_files 类型"""
        result = get_plugin_dtype("raw_files", {})
        assert result == "List[List[str]]"

    def test_get_plugin_dtype_waveforms(self):
        """测试 waveforms 类型"""
        result = get_plugin_dtype("waveforms", {})
        assert result == "List[np.ndarray]"

    def test_get_plugin_dtype_unknown(self):
        """测试未知类型"""
        result = get_plugin_dtype("unknown", {})
        assert result == "Unknown"

    def test_get_plugin_title_from_name(self):
        """测试从插件获取标题"""

        class MockPlugin:
            name = "Test Plugin"

        plugins = {"test": MockPlugin()}
        result = get_plugin_title("test", {}, plugins)
        assert result == "Test Plugin"

    def test_get_plugin_title_fallback(self):
        """测试标题回退"""
        result = get_plugin_title("unknown", {"plugin_class": "MyClass"}, {})
        assert result == "MyClass"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
