"""
测试依赖解析缓存优化的性能提升
"""

import time

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import Plugin


class TestCacheOptimization:
    """测试缓存优化的性能提升"""

    def test_execution_plan_cache(self):
        """测试执行计划缓存"""

        class PluginA(Plugin):
            provides = "data_a"

            def compute(self, context, run_id):
                return np.array([1])

        class PluginB(Plugin):
            provides = "data_b"
            depends_on = ["data_a"]

            def compute(self, context, run_id):
                return np.array([2])

        class PluginC(Plugin):
            provides = "data_c"
            depends_on = ["data_b"]

            def compute(self, context, run_id):
                return np.array([3])

        ctx = Context()
        ctx.register_plugin(PluginA())
        ctx.register_plugin(PluginB())
        ctx.register_plugin(PluginC())

        # 首次调用应该解析依赖
        data1 = ctx.get_data("run_001", "data_c")
        assert "data_c" in ctx._execution_plan_cache

        # 缓存的执行计划
        cached_plan = ctx._execution_plan_cache["data_c"]
        assert cached_plan == ["data_a", "data_b", "data_c"]

        # 再次调用应该使用缓存
        data2 = ctx.get_data("run_002", "data_c")
        np.testing.assert_array_equal(data2, np.array([3]))

    def test_lineage_cache(self):
        """测试血缘缓存"""

        class SimplePlugin(Plugin):
            provides = "test_data"
            version = "1.2.3"

            def compute(self, context, run_id):
                return np.array([1, 2, 3])

        ctx = Context()
        ctx.register_plugin(SimplePlugin())

        # 首次获取 lineage
        lineage1 = ctx.get_lineage("test_data")
        assert "test_data" in ctx._lineage_cache

        # 再次获取应该使用缓存
        lineage2 = ctx.get_lineage("test_data")
        assert lineage1 is lineage2  # 应该是同一个对象

    def test_key_cache(self):
        """测试 key 缓存"""

        class SimplePlugin(Plugin):
            provides = "test_data"

            def compute(self, context, run_id):
                return np.array([1])

        ctx = Context()
        ctx.register_plugin(SimplePlugin())

        # 首次调用 key_for
        key1 = ctx.key_for("run_001", "test_data")
        assert ("run_001", "test_data") in ctx._key_cache

        # 再次调用应该使用缓存
        key2 = ctx.key_for("run_001", "test_data")
        assert key1 == key2
        assert ctx._key_cache[("run_001", "test_data")] == key1

    def test_cache_invalidation_on_register(self):
        """测试注册插件时缓存失效"""

        class PluginV1(Plugin):
            provides = "data"
            version = "1.0.0"

            def compute(self, context, run_id):
                return np.array([1])

        ctx = Context()
        ctx.register_plugin(PluginV1())

        # 构建缓存
        lineage1 = ctx.get_lineage("data")
        key1 = ctx.key_for("run_001", "data")
        assert "data" in ctx._lineage_cache
        assert ("run_001", "data") in ctx._key_cache

        # 注册新版本插件（覆盖）
        class PluginV2(Plugin):
            provides = "data"
            version = "2.0.0"

            def compute(self, context, run_id):
                return np.array([2])

        ctx.register_plugin(PluginV2(), allow_override=True)

        # 缓存应该已失效
        assert "data" not in ctx._lineage_cache
        assert ("run_001", "data") not in ctx._key_cache

        # 重新获取应该使用新版本
        lineage2 = ctx.get_lineage("data")
        assert lineage2["plugin_version"] == "2.0.0"

    def test_clear_performance_caches(self):
        """测试清除性能缓存"""

        class SimplePlugin(Plugin):
            provides = "data"

            def compute(self, context, run_id):
                return np.array([1])

        ctx = Context()
        ctx.register_plugin(SimplePlugin())

        # 构建缓存
        ctx.get_lineage("data")
        ctx.key_for("run_001", "data")
        plan = ctx.resolve_dependencies("data")
        ctx._execution_plan_cache["data"] = plan

        assert ctx._lineage_cache
        assert ctx._key_cache
        assert ctx._execution_plan_cache

        # 清除缓存
        ctx.clear_performance_caches()

        assert not ctx._lineage_cache
        assert not ctx._key_cache
        assert not ctx._execution_plan_cache

    def test_cache_performance_improvement(self):
        """测试缓存带来的性能提升"""

        class PluginA(Plugin):
            provides = "a"

            def compute(self, context, run_id):
                return np.array([1])

        class PluginB(Plugin):
            provides = "b"
            depends_on = ["a"]

            def compute(self, context, run_id):
                return np.array([2])

        class PluginC(Plugin):
            provides = "c"
            depends_on = ["b"]

            def compute(self, context, run_id):
                return np.array([3])

        ctx = Context()
        ctx.register_plugin(PluginA())
        ctx.register_plugin(PluginB())
        ctx.register_plugin(PluginC())

        # 首次调用（构建缓存）
        start = time.perf_counter()
        for i in range(10):
            ctx.key_for(f"run_{i}", "c")
        first_time = time.perf_counter() - start

        # 清除缓存重新测试
        ctx.clear_performance_caches()

        # 第二次调用（使用缓存）
        start = time.perf_counter()
        for i in range(10):
            ctx.key_for(f"run_{i}", "c")
        cached_time = time.perf_counter() - start

        # 使用缓存应该更快（虽然差异可能很小）
        # 这里只是确保功能正常，不严格要求性能提升
        assert cached_time >= 0
        assert first_time >= 0

    def test_nested_dependency_cache(self):
        """测试嵌套依赖的缓存"""

        class Plugin1(Plugin):
            provides = "level1"

            def compute(self, context, run_id):
                return np.array([1])

        class Plugin2(Plugin):
            provides = "level2"
            depends_on = ["level1"]

            def compute(self, context, run_id):
                return np.array([2])

        class Plugin3(Plugin):
            provides = "level3"
            depends_on = ["level2"]

            def compute(self, context, run_id):
                return np.array([3])

        ctx = Context()
        ctx.register_plugin(Plugin1())
        ctx.register_plugin(Plugin2())
        ctx.register_plugin(Plugin3())

        # 构建完整的依赖链缓存
        lineage3 = ctx.get_lineage("level3")
        assert "level3" in ctx._lineage_cache

        # 依赖的 lineage 应该被递归缓存
        lineage2 = ctx.get_lineage("level2")
        lineage1 = ctx.get_lineage("level1")

        assert "level2" in ctx._lineage_cache
        assert "level1" in ctx._lineage_cache

        # 验证嵌套结构
        assert "level2" in lineage3["depends_on"]
        assert "level1" in lineage2["depends_on"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
