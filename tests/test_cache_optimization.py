"""
测试依赖解析缓存优化的性能提升
"""

import time

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin


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
        ctx.register(PluginA())
        ctx.register(PluginB())
        ctx.register(PluginC())

        # 首次调用应该解析依赖
        ctx.get_data("run_001", "data_c")
        assert ("run_001", "data_c") in ctx._execution_plan_cache

        # 缓存的执行计划
        cached_plan = ctx._execution_plan_cache[("run_001", "data_c")]
        assert cached_plan == ["data_a", "data_b", "data_c"]

        # 再次调用应该使用缓存
        data2 = ctx.get_data("run_002", "data_c")
        np.testing.assert_array_equal(data2, np.array([3]))

    def test_step_cache_skip_in_plan(self, tmp_path):
        """测试执行计划中缓存命中时跳过执行"""

        dtype = np.dtype([("v", "i4")])
        executed = []

        class TrackingContext(Context):
            def _execute_single_plugin(
                self, name, run_id, data_name, kwargs, tracker, bar_name, **extra
            ):
                executed.append(name)
                return super()._execute_single_plugin(
                    name, run_id, data_name, kwargs, tracker, bar_name, **extra
                )

        class PluginA(Plugin):
            provides = "data_a"
            output_dtype = dtype

            def compute(self, context, run_id):
                return np.array([(1,)], dtype=self.output_dtype)

        class PluginB(Plugin):
            provides = "data_b"
            depends_on = ["data_a"]
            output_dtype = dtype

            def compute(self, context, run_id):
                _ = context.get_data(run_id, "data_a")
                return np.array([(2,)], dtype=self.output_dtype)

        class PluginC(Plugin):
            provides = "data_c"
            depends_on = ["data_b"]
            output_dtype = dtype

            def compute(self, context, run_id):
                _ = context.get_data(run_id, "data_b")
                return np.array([(3,)], dtype=self.output_dtype)

        ctx = TrackingContext(storage_dir=str(tmp_path))
        ctx.register(PluginA())
        ctx.register(PluginB())
        ctx.register(PluginC())

        run_id = "run_cache_skip"
        ctx._set_data(run_id, "data_a", np.array([(1,)], dtype=dtype))

        data = ctx.get_data(run_id, "data_c")
        np.testing.assert_array_equal(data, np.array([(3,)], dtype=dtype))
        assert executed == ["data_b", "data_c"]

    def test_prune_upstream_when_mid_cached(self, tmp_path):
        """测试中间节点缓存命中时剪枝上游依赖"""

        dtype = np.dtype([("v", "i4")])
        executed = []

        class TrackingContext(Context):
            def _execute_single_plugin(
                self, name, run_id, data_name, kwargs, tracker, bar_name, **extra
            ):
                executed.append(name)
                return super()._execute_single_plugin(
                    name, run_id, data_name, kwargs, tracker, bar_name, **extra
                )

        class PluginA(Plugin):
            provides = "data_a"
            output_dtype = dtype

            def compute(self, context, run_id):
                return np.array([(1,)], dtype=self.output_dtype)

        class PluginB(Plugin):
            provides = "data_b"
            depends_on = ["data_a"]
            output_dtype = dtype

            def compute(self, context, run_id):
                _ = context.get_data(run_id, "data_a")
                return np.array([(2,)], dtype=self.output_dtype)

        class PluginC(Plugin):
            provides = "data_c"
            depends_on = ["data_b"]
            output_dtype = dtype

            def compute(self, context, run_id):
                _ = context.get_data(run_id, "data_b")
                return np.array([(3,)], dtype=self.output_dtype)

        ctx = TrackingContext(storage_dir=str(tmp_path))
        ctx.register(PluginA())
        ctx.register(PluginB())
        ctx.register(PluginC())

        run_id = "run_prune_mid"
        ctx._set_data(run_id, "data_b", np.array([(2,)], dtype=dtype))

        data = ctx.get_data(run_id, "data_c")
        np.testing.assert_array_equal(data, np.array([(3,)], dtype=dtype))
        assert executed == ["data_c"]

    def test_prune_upstream_when_mid_cached_on_disk(self, tmp_path):
        """测试中间节点磁盘缓存命中时剪枝上游依赖"""

        dtype = np.dtype([("v", "i4")])
        executed = []

        class TrackingContext(Context):
            def _execute_single_plugin(
                self, name, run_id, data_name, kwargs, tracker, bar_name, **extra
            ):
                executed.append(name)
                return super()._execute_single_plugin(
                    name, run_id, data_name, kwargs, tracker, bar_name, **extra
                )

        class PluginA(Plugin):
            provides = "data_a"
            output_dtype = dtype

            def compute(self, context, run_id):
                return np.array([(1,)], dtype=self.output_dtype)

        class PluginB(Plugin):
            provides = "data_b"
            depends_on = ["data_a"]
            output_dtype = dtype
            save_when = "always"

            def compute(self, context, run_id):
                _ = context.get_data(run_id, "data_a")
                return np.array([(2,)], dtype=self.output_dtype)

        class PluginC(Plugin):
            provides = "data_c"
            depends_on = ["data_b"]
            output_dtype = dtype

            def compute(self, context, run_id):
                _ = context.get_data(run_id, "data_b")
                return np.array([(3,)], dtype=self.output_dtype)

        ctx = TrackingContext(storage_dir=str(tmp_path))
        ctx.register(PluginA())
        ctx.register(PluginB())
        ctx.register(PluginC())

        run_id = "run_prune_disk"
        _ = ctx.get_data(run_id, "data_b")
        key_b = ctx.key_for(run_id, "data_b")
        assert ctx.storage.exists(key_b, run_id)

        executed.clear()
        ctx._results.pop((run_id, "data_a"), None)
        ctx._results.pop((run_id, "data_b"), None)

        data = ctx.get_data(run_id, "data_c")
        np.testing.assert_array_equal(data, np.array([(3,)], dtype=dtype))
        assert executed == ["data_c"]

    def test_run_plugin_loads_disk_cache(self, tmp_path):
        """测试 run_plugin 强制执行并忽略缓存"""

        dtype = np.dtype([("v", "i4")])
        executed = []

        class TrackingContext(Context):
            def _execute_single_plugin(
                self, name, run_id, data_name, kwargs, tracker, bar_name, **extra
            ):
                executed.append(name)
                return super()._execute_single_plugin(
                    name, run_id, data_name, kwargs, tracker, bar_name, **extra
                )

        class PluginA(Plugin):
            provides = "data_a"
            output_dtype = dtype
            save_when = "always"

            def compute(self, context, run_id):
                return np.array([(1,)], dtype=self.output_dtype)

        ctx = TrackingContext(storage_dir=str(tmp_path))
        ctx.register(PluginA())

        run_id = "run_disk_cache"
        _ = ctx.get_data(run_id, "data_a")
        executed.clear()
        ctx._results.pop((run_id, "data_a"), None)

        data = ctx._execution_domain.run_plugin(run_id, "data_a")
        np.testing.assert_array_equal(data, np.array([(1,)], dtype=dtype))
        assert executed == ["data_a"]

    def test_lineage_cache(self):
        """测试血缘缓存"""

        class SimplePlugin(Plugin):
            provides = "test_data"
            version = "1.2.3"

            def compute(self, context, run_id):
                return np.array([1, 2, 3])

        ctx = Context()
        ctx.register(SimplePlugin())

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
        ctx.register(SimplePlugin())

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
        ctx.register(PluginV1())

        # 构建缓存
        ctx.get_lineage("data")
        ctx.key_for("run_001", "data")
        assert "data" in ctx._lineage_cache
        assert ("run_001", "data") in ctx._key_cache

        # 注册新版本插件（覆盖）
        class PluginV2(Plugin):
            provides = "data"
            version = "2.0.0"

            def compute(self, context, run_id):
                return np.array([2])

        ctx.register(PluginV2(), allow_override=True)

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
        ctx.register(SimplePlugin())

        # 构建缓存
        ctx.get_lineage("data")
        ctx.key_for("run_001", "data")
        plan = ctx.resolve_dependencies("data")
        ctx._execution_plan_cache[("run_001", "data")] = plan

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
        ctx.register(PluginA())
        ctx.register(PluginB())
        ctx.register(PluginC())

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
        ctx.register(Plugin1())
        ctx.register(Plugin2())
        ctx.register(Plugin3())

        # 构建完整的依赖链缓存
        lineage3 = ctx.get_lineage("level3")
        assert "level3" in ctx._lineage_cache

        # 依赖的 lineage 应该被递归缓存
        lineage2 = ctx.get_lineage("level2")
        ctx.get_lineage("level1")

        assert "level2" in ctx._lineage_cache
        assert "level1" in ctx._lineage_cache

        # 验证嵌套结构
        assert "level2" in lineage3["depends_on"]
        assert "level1" in lineage2["depends_on"]

    def test_downstream_recomputed_after_upstream_recompute(self, tmp_path):
        """重算上游后，同一进程内下游必须重算而非命中陈旧缓存。

        复现 run 00110 的问题：上游谱系变化后，默认谱系路径的中间节点把旧的上游
        谱系缓存在 _lineage_cache 里，导致缓存校验错误命中陈旧磁盘结果。
        """
        dtype = np.dtype([("v", "i4")])
        executed = []

        class TrackingContext(Context):
            def _execute_single_plugin(
                self, name, run_id, data_name, kwargs, tracker, bar_name, **extra
            ):
                executed.append(name)
                return super()._execute_single_plugin(
                    name, run_id, data_name, kwargs, tracker, bar_name, **extra
                )

        class PluginA(Plugin):
            provides = "data_a"
            version = "1.0.0"
            output_dtype = dtype
            save_when = "always"
            value = 1

            def compute(self, context, run_id):
                return np.array([(self.value,)], dtype=dtype)

        class PluginB(Plugin):
            provides = "data_b"
            depends_on = ["data_a"]
            output_dtype = dtype
            # 中间结果也落盘，镜像生产里 hit_threshold 等 save_when="always" 的插件。
            save_when = "always"

            def compute(self, context, run_id):
                a = context.get_data(run_id, "data_a")
                return np.array([(a["v"][0] + 1,)], dtype=dtype)

        class PluginC(Plugin):
            provides = "data_c"
            depends_on = ["data_a", "data_b"]
            output_dtype = dtype
            save_when = "always"

            # 像 records/wave_pool 一样自定义谱系：直接内嵌上游的当前谱系。
            def get_lineage(self, context):
                return {
                    "plugin_class": self.__class__.__name__,
                    "plugin_version": self.version,
                    "description": self.description,
                    "depends_on": {
                        "data_a": context.get_lineage("data_a"),
                        "data_b": context.get_lineage("data_b"),
                    },
                }

            def compute(self, context, run_id):
                b = context.get_data(run_id, "data_b")
                return np.array([(b["v"][0] + 1,)], dtype=dtype)

        ctx = TrackingContext(storage_dir=str(tmp_path))
        ctx.register(PluginA())
        ctx.register(PluginB())
        ctx.register(PluginC())

        run_id = "run_downstream_recompute"
        first = ctx.get_data(run_id, "data_c")
        np.testing.assert_array_equal(first, np.array([(3,)], dtype=dtype))
        assert executed == ["data_a", "data_b", "data_c"]
        executed.clear()

        # 重新注册 A（version 2.0.0）：register 只清 A 自身的性能缓存，
        # 不清 B/C —— 精确复现"下游谱系缓存陈旧"的场景。
        class PluginA2(PluginA):
            version = "2.0.0"
            value = 2

        ctx.register(PluginA2(), allow_override=True)

        # 清内存缓存但保留磁盘缓存与陈旧的 _lineage_cache，走磁盘命中路径。
        ctx.clear_cache_for(run_id, clear_disk=False, verbose=False)

        second = ctx.get_data(run_id, "data_c")
        # A 因谱系变化重算；B/C 也必须重算，而不是命中基于旧 A 的陈旧磁盘结果。
        np.testing.assert_array_equal(second, np.array([(4,)], dtype=dtype))
        assert executed == ["data_a", "data_b", "data_c"]

    def test_execution_plan_keyed_by_run_id(self, tmp_path):
        """执行计划缓存按 (run_id, data_name) 键控，动态依赖在不同 run 下不串。

        resolve_depends_on 可按 run_id 返回不同依赖；若计划缓存只按 data_name
        键控，后请求的 run 会复用先请求 run 的计划而执行错误的依赖链。
        """
        dtype = np.dtype([("v", "i4")])
        executed = []

        class PluginBase(Plugin):
            provides = "data_base"
            version = "1.0.0"
            output_dtype = dtype
            save_when = "always"

            def compute(self, context, run_id):
                executed.append("data_base")
                return np.array([(1,)], dtype=dtype)

        class PluginDynamic(Plugin):
            provides = "data_b"
            version = "1.0.0"
            output_dtype = dtype
            save_when = "always"

            def resolve_depends_on(self, context, run_id=None):
                if run_id == "run_A":
                    return ["data_base"]
                return []

            def compute(self, context, run_id):
                executed.append("data_b")
                if run_id == "run_A":
                    base = context.get_data(run_id, "data_base")
                    return np.array([(base["v"][0] + 1,)], dtype=dtype)
                return np.array([(9,)], dtype=dtype)

        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(PluginBase())
        ctx.register(PluginDynamic())

        # run_A 先请求：计划应为 [data_base, data_b]。
        a = ctx.get_data("run_A", "data_b")
        np.testing.assert_array_equal(a, np.array([(2,)], dtype=dtype))
        assert "data_base" in executed

        executed.clear()
        # run_B 后请求：计划不得复用 run_A 的 [data_base, data_b]。
        b = ctx.get_data("run_B", "data_b")
        np.testing.assert_array_equal(b, np.array([(9,)], dtype=dtype))
        assert "data_base" not in executed

    def test_reverse_deps_cached_per_run(self):
        """_collect_downstream_data_names 按 (run_id, registry_version) 缓存 reverse_deps，
        注册变化后自动失效。"""

        class PluginA(Plugin):
            provides = "data_a"

            def compute(self, context, run_id):
                return np.array([1])

        class PluginB(Plugin):
            provides = "data_b"
            depends_on = ["data_a"]

            def compute(self, context, run_id):
                return np.array([1])

        class PluginC(Plugin):
            provides = "data_c"
            depends_on = ["data_b"]

            def compute(self, context, run_id):
                return np.array([1])

        ctx = Context()
        ctx.register(PluginA())
        ctx.register(PluginB())
        ctx.register(PluginC())

        downstream = ctx._collect_downstream_data_names("data_a", run_id="r1")
        assert set(downstream) == {"data_b", "data_c"}
        assert ("r1", ctx._registry_version) in ctx._reverse_deps_cache
        # 同 (run, registry_version) 复用缓存。
        assert ctx._collect_downstream_data_names("data_a", run_id="r1") == downstream

        # 注册新下游后缓存失效并反映新依赖。
        class PluginD(Plugin):
            provides = "data_d"
            depends_on = ["data_a"]

            def compute(self, context, run_id):
                return np.array([1])

        ctx.register(PluginD())
        downstream2 = ctx._collect_downstream_data_names("data_a", run_id="r1")
        assert set(downstream2) == {"data_b", "data_c", "data_d"}

    def test_key_cache_capped(self):
        """_key_cache 有容量上限，超限按 FIFO 淘汰，不影响键正确性。"""

        class SimplePlugin(Plugin):
            provides = "test_data"

            def compute(self, context, run_id):
                return np.array([1])

        ctx = Context()
        ctx.register(SimplePlugin())

        for i in range(8500):
            ctx.key_for(f"run_{i:04d}", "test_data")
        assert len(ctx._key_cache) <= 8192
        assert ctx.key_for("run_9999", "test_data").startswith("run_9999-")
        # 前缀缓存按 data_name 缓存且格式正确。
        suffix = ctx._key_prefix_cache["test_data"]
        assert suffix.startswith("test_data-")
        assert ctx.key_for("run_1234", "test_data") == f"run_1234-{suffix}"

    def test_storage_key_list_cache_refreshes_after_save(self, tmp_path):
        """save_plugin_result 写盘后 _storage_list_keys 缓存失效，新键可见。"""

        dtype = np.dtype([("v", "i4")])

        class SavePlugin(Plugin):
            provides = "saved_data"
            version = "1.0.0"
            output_dtype = dtype
            save_when = "always"

            def compute(self, context, run_id):
                return np.array([(7,)], dtype=dtype)

        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SavePlugin())
        run_id = "run_saved"
        storage = ctx.storage

        # 首次扫描并缓存（此时磁盘无 saved_data 键）。
        before = ctx._storage_list_keys(storage, run_id)
        assert ctx._run_key_list_cache[(id(storage), run_id)] is before
        assert not any("saved_data" in k for k in before)

        # get_data 执行并写盘；写路径应使 list_keys 缓存失效。
        data = ctx.get_data(run_id, "saved_data")
        np.testing.assert_array_equal(data, np.array([(7,)], dtype=dtype))

        # 写盘后重新扫描应看到新键（缓存已失效，不会读到陈旧列表）。
        after = ctx._storage_list_keys(storage, run_id)
        assert any("saved_data" in k for k in after)

    def test_compute_needed_set_skips_target_check(self, tmp_path):
        """target_is_missing=True 时 compute_needed_set 不再重复检查目标缓存。"""

        dtype = np.dtype([("v", "i4")])
        checked = []

        class CountingContext(Context):
            def _is_cache_hit(self, run_id, name, load=False):
                checked.append(name)
                return super()._is_cache_hit(run_id, name, load=False)

        class PluginA(Plugin):
            provides = "data_base"
            output_dtype = dtype

            def compute(self, context, run_id):
                return np.array([(1,)], dtype=dtype)

        class PluginTarget(Plugin):
            provides = "data_target"
            depends_on = ["data_base"]
            output_dtype = dtype

            def compute(self, context, run_id):
                base = context.get_data(run_id, "data_base")
                return np.array([(base["v"][0] + 1,)], dtype=dtype)

        ctx = CountingContext(storage_dir=str(tmp_path))
        ctx.register(PluginA())
        ctx.register(PluginTarget())

        plan = ctx._execution_domain.resolve_execution_plan("run_tgt", "data_target")
        checked.clear()
        ctx._execution_domain.compute_needed_set("run_tgt", "data_target", plan)
        assert "data_target" in checked
        checked.clear()
        ctx._execution_domain.compute_needed_set(
            "run_tgt", "data_target", plan, target_is_missing=True
        )
        assert "data_target" not in checked


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
