"""
测试插件超时控制功能
"""

import time
import pytest

from waveform_analysis.core.execution.timeout import (
    TimeoutManager,
    get_timeout_manager,
    with_timeout,
)
from waveform_analysis.core.foundation.exceptions import PluginTimeoutError


class TestTimeoutManager:
    """测试TimeoutManager基本功能"""

    def test_timeout_manager_creation(self):
        """测试创建TimeoutManager"""
        manager = TimeoutManager()
        assert manager is not None

    def test_timeout_manager_singleton(self):
        """测试全局单例"""
        manager1 = get_timeout_manager()
        manager2 = get_timeout_manager()
        assert manager1 is manager2

    def test_function_completes_within_timeout(self):
        """测试函数在超时前完成"""
        manager = TimeoutManager()

        def quick_func(x, y):
            return x + y

        result = manager.run_with_timeout(quick_func, 5.0, 10, 20)
        assert result == 30

    def test_function_timeout(self):
        """测试函数超时"""
        manager = TimeoutManager()

        def slow_func():
            time.sleep(3)
            return "completed"

        with pytest.raises(PluginTimeoutError):
            manager.run_with_timeout(slow_func, timeout=1.0)

    def test_no_timeout(self):
        """测试None timeout(无限制)"""
        manager = TimeoutManager()

        def func():
            time.sleep(0.1)
            return "done"

        result = manager.run_with_timeout(func, timeout=None)
        assert result == "done"

    def test_zero_timeout(self):
        """测试零超时等同于无超时"""
        manager = TimeoutManager()

        def func():
            time.sleep(0.1)
            return "done"

        result = manager.run_with_timeout(func, timeout=0)
        assert result == "done"

    def test_timeout_context_manager(self):
        """测试context manager形式的超时控制"""
        manager = TimeoutManager()

        with manager.timeout_context(5.0, "test_operation"):
            time.sleep(0.1)
            x = 1 + 1

        assert x == 2

    def test_timeout_context_manager_timeout(self):
        """测试context manager超时"""
        manager = TimeoutManager()

        with pytest.raises(PluginTimeoutError):
            with manager.timeout_context(1.0, "slow_operation"):
                time.sleep(3)

    def test_timeout_stats(self):
        """测试超时统计"""
        manager = TimeoutManager()
        manager.reset_stats()

        def slow_func():
            time.sleep(2)

        # 执行几次超时
        for _ in range(3):
            try:
                manager.run_with_timeout(slow_func, timeout=0.5)
            except PluginTimeoutError:
                pass

        stats = manager.get_timeout_stats()
        assert 'slow_func' in stats
        assert stats['slow_func'] == 3

    def test_timeout_with_exception(self):
        """测试函数内部抛出异常"""
        manager = TimeoutManager()

        def error_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            manager.run_with_timeout(error_func, timeout=5.0)

    def test_timeout_with_args_kwargs(self):
        """测试带参数的函数超时"""
        manager = TimeoutManager()

        def func_with_args(a, b, c=3):
            time.sleep(0.1)
            return a + b + c

        result = manager.run_with_timeout(
            func_with_args, 5.0, 1, 2, c=4
        )
        assert result == 7


class TestTimeoutDecorator:
    """测试@with_timeout装饰器"""

    def test_decorator_no_timeout(self):
        """测试无超时的装饰器"""
        @with_timeout(timeout=5.0)
        def quick_func(x):
            return x * 2

        result = quick_func(10)
        assert result == 20

    def test_decorator_with_timeout(self):
        """测试装饰器超时"""
        @with_timeout(timeout=1.0)
        def slow_func():
            time.sleep(3)
            return "done"

        with pytest.raises(PluginTimeoutError):
            slow_func()

    def test_decorator_preserves_function_name(self):
        """测试装饰器保留函数名"""
        @with_timeout(timeout=5.0)
        def my_function():
            """My docstring"""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring"


class TestPluginWithTimeout:
    """测试Plugin类的timeout属性"""

    def test_plugin_timeout_attribute(self):
        """测试Plugin有timeout属性"""
        from waveform_analysis.core.plugins.core.base import Plugin

        class TestPlugin(Plugin):
            provides = "test_data"
            timeout = 10.0

            def compute(self, *args, **kwargs):
                return [1, 2, 3]

        plugin = TestPlugin()
        assert plugin.timeout == 10.0

    def test_plugin_default_no_timeout(self):
        """测试Plugin默认无超时"""
        from waveform_analysis.core.plugins.core.base import Plugin

        class TestPlugin(Plugin):
            provides = "test_data"

            def compute(self, *args, **kwargs):
                return [1, 2, 3]

        plugin = TestPlugin()
        assert plugin.timeout is None


class TestCrossPlatform:
    """测试跨平台兼容性"""

    def test_platform_detection(self):
        """测试平台检测"""
        import platform
        manager = TimeoutManager()

        if platform.system() in ['Linux', 'Darwin']:
            assert manager.is_unix is True
        else:
            assert manager.is_unix is False

    def test_timeout_works_on_current_platform(self):
        """测试超时在当前平台上工作"""
        manager = TimeoutManager()

        def slow_func():
            time.sleep(2)

        with pytest.raises(PluginTimeoutError):
            manager.run_with_timeout(slow_func, timeout=0.5)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
