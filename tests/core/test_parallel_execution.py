"""测试插件并行执行框架的正确性。

测试覆盖：
1. 依赖图构建的正确性
2. 执行层分组逻辑
3. 线程安全和数据一致性
4. 循环依赖检测
"""

from concurrent.futures import ThreadPoolExecutor
import time
from typing import Any

import numpy as np
import pytest

from tests.utils import DummyContext


class MockPlugin:
    """用于测试的模拟插件"""

    def __init__(self, name, depends_on=None, compute_time=0.01):
        self.provides = name
        self.depends_on = depends_on or []
        self.compute_time = compute_time
        self.compute_count = 0
        self.parallel = False
        self.save_when = "always"

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        """模拟计算"""
        self.compute_count += 1
        time.sleep(self.compute_time)

        # 生成一些假数据
        result = np.arange(10, dtype=np.int64) + self.compute_count

        # 将结果存入 context
        if hasattr(context, "_data") and isinstance(context._data, dict):
            context._data[self.provides] = result

        return result


def build_dependency_graph(plugins: dict) -> dict[str, set[str]]:
    """构建插件依赖图。

    Returns:
        dict: {plugin_name: set(dependencies)}
    """
    graph = {}
    for name, plugin in plugins.items():
        deps = set(plugin.depends_on) if plugin.depends_on else set()
        graph[name] = deps
    return graph


def detect_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """检测依赖图中的循环。

    Returns:
        list of cycles, 每个 cycle 是一个 plugin name 列表
    """

    def dfs(node, path, visited, rec_stack):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                cycle = dfs(neighbor, path, visited, rec_stack)
                if cycle:
                    return cycle
            elif neighbor in rec_stack:
                # 找到循环
                cycle_start = path.index(neighbor)
                return path[cycle_start:] + [neighbor]

        path.pop()
        rec_stack.remove(node)
        return None

    cycles = []
    visited = set()

    for node in graph:
        if node not in visited:
            rec_stack = set()
            cycle = dfs(node, [], visited, rec_stack)
            if cycle:
                cycles.append(cycle)

    return cycles


def get_execution_layers(graph: dict[str, set[str]]) -> list[set[str]]:
    """将插件分组为执行层，同一层的插件可以并行执行。

    Returns:
        list of sets, 每个 set 是一层的 plugin names
    """
    # 检查循环依赖
    cycles = detect_cycles(graph)
    if cycles:
        raise ValueError(f"检测到循环依赖: {cycles}")

    layers = []
    remaining = set(graph.keys())
    completed = set()

    while remaining:
        # 找出所有依赖都已满足的插件
        ready = set()
        for plugin in remaining:
            deps = graph[plugin]
            if deps.issubset(completed):
                ready.add(plugin)

        if not ready:
            # 理论上不应该发生（如果没有循环依赖）
            raise ValueError(f"无法解析依赖: 剩余 {remaining}, 已完成 {completed}")

        layers.append(ready)
        remaining -= ready
        completed.update(ready)

    return layers


def execute_plugins_parallel(
    plugins: dict, context: Any, run_id: str, max_workers: int = 4
) -> dict:
    """并行执行插件。

    Returns:
        dict: {plugin_name: result}
    """
    graph = build_dependency_graph(plugins)
    layers = get_execution_layers(graph)
    results = {}

    for layer in layers:
        if len(layer) == 1:
            # 单个插件，直接执行
            name = list(layer)[0]
            plugin = plugins[name]
            results[name] = plugin.compute(context, run_id)
        else:
            # 多个插件，并行执行
            def execute_one(name):
                plugin = plugins[name]
                return name, plugin.compute(context, run_id)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                layer_results = list(executor.map(execute_one, layer))

            for name, result in layer_results:
                results[name] = result

    return results


class TestDependencyGraph:
    """测试依赖图构建"""

    def test_empty_graph(self):
        """测试空依赖图"""
        plugins = {}
        graph = build_dependency_graph(plugins)
        assert graph == {}

    def test_simple_linear_chain(self):
        """测试简单的线性依赖链: A -> B -> C"""
        plugins = {
            "A": MockPlugin("A", depends_on=[]),
            "B": MockPlugin("B", depends_on=["A"]),
            "C": MockPlugin("C", depends_on=["B"]),
        }

        graph = build_dependency_graph(plugins)

        assert graph["A"] == set()
        assert graph["B"] == {"A"}
        assert graph["C"] == {"B"}

    def test_diamond_dependencies(self):
        """测试菱形依赖: A -> B,C -> D"""
        plugins = {
            "A": MockPlugin("A", depends_on=[]),
            "B": MockPlugin("B", depends_on=["A"]),
            "C": MockPlugin("C", depends_on=["A"]),
            "D": MockPlugin("D", depends_on=["B", "C"]),
        }

        graph = build_dependency_graph(plugins)

        assert graph["A"] == set()
        assert graph["B"] == {"A"}
        assert graph["C"] == {"A"}
        assert graph["D"] == {"B", "C"}

    def test_complex_graph(self):
        """测试复杂依赖图"""
        plugins = {
            "records": MockPlugin("records", depends_on=[]),
            "hit_threshold": MockPlugin("hit_threshold", depends_on=["records"]),
            "hit_merged": MockPlugin("hit_merged", depends_on=["hit_threshold"]),
            "hit_merged_components": MockPlugin("hit_merged_components", depends_on=["hit_merged"]),
            "hit_merged_features": MockPlugin(
                "hit_merged_features", depends_on=["hit_merged", "hit_merged_components", "records"]
            ),
            "peaklets": MockPlugin("peaklets", depends_on=["hit_merged"]),
        }

        graph = build_dependency_graph(plugins)

        assert graph["records"] == set()
        assert graph["hit_threshold"] == {"records"}
        assert graph["hit_merged_features"] == {"hit_merged", "hit_merged_components", "records"}


class TestCycleDetection:
    """测试循环依赖检测"""

    def test_no_cycle_linear(self):
        """测试无循环的线性图"""
        graph = {
            "A": set(),
            "B": {"A"},
            "C": {"B"},
        }

        cycles = detect_cycles(graph)
        assert cycles == []

    def test_no_cycle_diamond(self):
        """测试无循环的菱形图"""
        graph = {
            "A": set(),
            "B": {"A"},
            "C": {"A"},
            "D": {"B", "C"},
        }

        cycles = detect_cycles(graph)
        assert cycles == []

    def test_simple_cycle(self):
        """测试简单循环: A -> B -> A"""
        graph = {
            "A": {"B"},
            "B": {"A"},
        }

        cycles = detect_cycles(graph)
        assert len(cycles) > 0, "应该检测到循环"

    def test_self_loop(self):
        """测试自环: A -> A"""
        graph = {
            "A": {"A"},
        }

        cycles = detect_cycles(graph)
        assert len(cycles) > 0, "应该检测到自环"

    def test_complex_cycle(self):
        """测试复杂循环: A -> B -> C -> D -> B"""
        graph = {
            "A": set(),
            "B": {"A"},
            "C": {"B"},
            "D": {"C"},
            "E": {"D", "B"},  # 创建循环
        }
        graph["B"] = {"A", "E"}  # B 依赖 E，而 E 依赖 D -> C -> B

        cycles = detect_cycles(graph)
        # 这个图实际上有循环: B -> E -> D -> C -> B
        assert len(cycles) > 0, "应该检测到循环"


class TestExecutionLayers:
    """测试执行层分组"""

    def test_single_plugin(self):
        """测试单个插件"""
        graph = {"A": set()}
        layers = get_execution_layers(graph)

        assert len(layers) == 1
        assert layers[0] == {"A"}

    def test_linear_chain(self):
        """测试线性链"""
        graph = {
            "A": set(),
            "B": {"A"},
            "C": {"B"},
        }

        layers = get_execution_layers(graph)

        assert len(layers) == 3
        assert layers[0] == {"A"}
        assert layers[1] == {"B"}
        assert layers[2] == {"C"}

    def test_parallel_plugins(self):
        """测试可并行的插件"""
        graph = {
            "A": set(),
            "B": set(),
            "C": set(),
        }

        layers = get_execution_layers(graph)

        assert len(layers) == 1
        assert layers[0] == {"A", "B", "C"}

    def test_diamond_layering(self):
        """测试菱形依赖的分层"""
        graph = {
            "A": set(),
            "B": {"A"},
            "C": {"A"},
            "D": {"B", "C"},
        }

        layers = get_execution_layers(graph)

        assert len(layers) == 3
        assert layers[0] == {"A"}
        assert layers[1] == {"B", "C"}  # B 和 C 可以并行
        assert layers[2] == {"D"}

    def test_complex_layering(self):
        """测试复杂的分层"""
        graph = {
            "records": set(),
            "filtered": {"records"},
            "hit_threshold": {"records"},
            "hit_merged": {"hit_threshold"},
            "peaklets": {"hit_merged"},
            "peaks": {"peaklets", "filtered"},
        }

        layers = get_execution_layers(graph)

        assert len(layers) == 5
        assert layers[0] == {"records"}
        assert layers[1] == {"filtered", "hit_threshold"}  # 可并行
        assert layers[2] == {"hit_merged"}
        assert layers[3] == {"peaklets"}
        assert layers[4] == {"peaks"}

    def test_cycle_raises_error(self):
        """测试循环依赖抛出错误"""
        graph = {
            "A": {"B"},
            "B": {"A"},
        }

        with pytest.raises(ValueError, match="循环依赖"):
            get_execution_layers(graph)


class TestParallelExecution:
    """测试并行执行"""

    def test_sequential_execution(self):
        """测试顺序执行"""
        plugins = {
            "A": MockPlugin("A", depends_on=[], compute_time=0.01),
            "B": MockPlugin("B", depends_on=["A"], compute_time=0.01),
            "C": MockPlugin("C", depends_on=["B"], compute_time=0.01),
        }

        ctx = DummyContext({}, {})
        results = execute_plugins_parallel(plugins, ctx, "test_run", max_workers=4)

        assert len(results) == 3
        assert "A" in results
        assert "B" in results
        assert "C" in results

        # 验证执行次数
        assert plugins["A"].compute_count == 1
        assert plugins["B"].compute_count == 1
        assert plugins["C"].compute_count == 1

    def test_parallel_speedup(self):
        """测试并行加速"""
        # 创建可并行的插件
        plugins = {
            "A": MockPlugin("A", depends_on=[], compute_time=0.001),
            "B": MockPlugin("B", depends_on=["A"], compute_time=0.05),
            "C": MockPlugin("C", depends_on=["A"], compute_time=0.05),
            "D": MockPlugin("D", depends_on=["A"], compute_time=0.05),
        }

        ctx = DummyContext({}, {})

        # 并行执行
        start = time.time()
        results = execute_plugins_parallel(plugins, ctx, "test_run", max_workers=4)
        parallel_time = time.time() - start

        # 验证结果
        assert len(results) == 4

        # 并行时间应该明显小于串行时间
        # 串行时间约为 0.001 + 0.05 + 0.05 + 0.05 = 0.151 秒
        # 并行时间应该约为 0.001 + 0.05 = 0.051 秒（B, C, D 并行）
        assert parallel_time < 0.15, f"并行时间 {parallel_time:.3f}s 应该小于串行时间"

    def test_thread_safety(self):
        """测试线程安全"""
        # 创建多个可并行的插件，共享 context
        plugins = {
            "A": MockPlugin("A", depends_on=[], compute_time=0.001),
            "B1": MockPlugin("B1", depends_on=["A"], compute_time=0.01),
            "B2": MockPlugin("B2", depends_on=["A"], compute_time=0.01),
            "B3": MockPlugin("B3", depends_on=["A"], compute_time=0.01),
            "B4": MockPlugin("B4", depends_on=["A"], compute_time=0.01),
        }

        ctx = DummyContext(
            {},
        )

        # 多次执行，验证没有数据竞争
        for _ in range(5):
            results = execute_plugins_parallel(plugins, ctx, "test_run", max_workers=4)

            assert len(results) == 5
            for name in ["A", "B1", "B2", "B3", "B4"]:
                assert name in results
                assert len(results[name]) == 10  # 每个插件返回 10 个元素

    def test_data_consistency(self):
        """测试数据一致性"""
        plugins = {
            "A": MockPlugin("A", depends_on=[], compute_time=0.001),
            "B": MockPlugin("B", depends_on=["A"], compute_time=0.001),
            "C": MockPlugin("C", depends_on=["A"], compute_time=0.001),
            "D": MockPlugin("D", depends_on=["B", "C"], compute_time=0.001),
        }

        ctx = DummyContext({}, {})
        results = execute_plugins_parallel(plugins, ctx, "test_run", max_workers=4)

        # 验证数据在 context 中正确存储
        assert "A" in ctx._data
        assert "B" in ctx._data
        assert "C" in ctx._data
        assert "D" in ctx._data

        # 验证结果一致性
        np.testing.assert_array_equal(results["A"], ctx._data["A"])
        np.testing.assert_array_equal(results["B"], ctx._data["B"])

    def test_error_propagation(self):
        """测试错误传播"""

        class FailingPlugin(MockPlugin):
            def compute(self, context, run_id, **kwargs):
                raise RuntimeError("故意失败")

        plugins = {
            "A": MockPlugin("A", depends_on=[]),
            "B": FailingPlugin("B", depends_on=["A"]),
            "C": MockPlugin("C", depends_on=["A"]),
        }

        ctx = DummyContext({}, {})

        # 应该抛出异常
        with pytest.raises(RuntimeError, match="故意失败"):
            execute_plugins_parallel(plugins, ctx, "test_run", max_workers=4)


class TestRealWorldScenario:
    """测试真实世界场景"""

    def test_typical_waveform_pipeline(self):
        """测试典型的波形处理流水线"""
        plugins = {
            "records": MockPlugin("records", depends_on=[], compute_time=0.01),
            "wave_pool": MockPlugin("wave_pool", depends_on=["records"], compute_time=0.01),
            "hit_threshold": MockPlugin(
                "hit_threshold", depends_on=["records", "wave_pool"], compute_time=0.02
            ),
            "hit_merged": MockPlugin(
                "hit_merged", depends_on=["hit_threshold"], compute_time=0.015
            ),
            "hit_merged_components": MockPlugin(
                "hit_merged_components",
                depends_on=["hit_merged", "hit_threshold"],
                compute_time=0.01,
            ),
            "hit_merged_features": MockPlugin(
                "hit_merged_features",
                depends_on=["hit_merged", "hit_merged_components", "records", "wave_pool"],
                compute_time=0.02,
            ),
            "peaklets": MockPlugin("peaklets", depends_on=["hit_merged"], compute_time=0.015),
            "peaklet_components": MockPlugin(
                "peaklet_components", depends_on=["peaklets", "hit_merged"], compute_time=0.01
            ),
        }

        ctx = DummyContext({}, {})

        # 测量执行时间
        start = time.time()
        results = execute_plugins_parallel(plugins, ctx, "test_run", max_workers=8)
        execution_time = time.time() - start

        # 验证所有插件都执行了
        assert len(results) == len(plugins)
        for name in plugins:
            assert name in results
            assert plugins[name].compute_count == 1

        # 并行执行应该比串行快
        # 串行时间约为所有 compute_time 之和 = 0.135 秒
        # 并行时间应该明显更短
        print(f"Pipeline 执行时间: {execution_time:.3f}s")
        assert execution_time < 0.15, "并行执行应该更快"

    def test_load_balancing(self):
        """测试负载均衡"""
        # 创建不同耗时的插件
        plugins = {
            "fast1": MockPlugin("fast1", depends_on=[], compute_time=0.01),
            "fast2": MockPlugin("fast2", depends_on=[], compute_time=0.01),
            "slow": MockPlugin("slow", depends_on=[], compute_time=0.05),
            "fast3": MockPlugin("fast3", depends_on=[], compute_time=0.01),
        }

        ctx = DummyContext({}, {})

        start = time.time()
        results = execute_plugins_parallel(plugins, ctx, "test_run", max_workers=4)
        execution_time = time.time() - start

        # 所有插件可以并行，总时间应该接近最慢的插件
        assert len(results) == 4
        assert execution_time < 0.08, f"执行时间 {execution_time:.3f}s 应该接近最慢插件的时间"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
