"""
依赖分析模块 - 插件依赖关系图（DAG）分析。

提供以下功能：
1. 静态依赖分析：基于 DAG 结构分析
2. 动态性能分析：整合实际执行数据
3. 关键路径识别：CPM 算法
4. 并行机会识别：层次分析
5. 性能瓶颈识别：多维度评估
6. 智能优化建议：规则引擎

使用示例：

    from waveform_analysis.core.context import Context

    ctx = Context(enable_stats=True)
    # ... 注册插件并执行 ...

    # 分析依赖关系
    analysis = ctx.analyze_dependencies('paired_events')

    # 查看摘要
    print(analysis.summary())

    # 导出报告
    analysis.to_markdown('report.md')
    data = analysis.to_dict()  # 可保存为 JSON
"""

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from typing import Any

from waveform_analysis.core.foundation.model import (
    EdgeModel,
    LineageGraphModel,
    build_lineage_graph,
)
from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
@dataclass
class DependencyAnalysisResult:
    """依赖分析结果"""

    # 基本信息
    target_name: str
    total_plugins: int
    execution_plan: list[str]  # 拓扑排序结果

    # DAG 结构分析
    max_depth: int  # DAG 最大深度
    max_width: int  # DAG 最大宽度
    layers: dict[int, list[str]] = field(default_factory=dict)  # 按深度分层

    # 关键路径分析
    critical_path: list[str] = field(default_factory=list)  # 关键路径上的插件列表
    critical_path_time: float | None = None  # 总时间（如果有性能数据）

    # 并行机会
    parallel_groups: list[list[str]] = field(default_factory=list)  # 可并行执行的插件组
    parallelization_potential: float = 1.0  # 理论加速比

    # 性能瓶颈（仅在有统计数据时可用）
    bottlenecks: list[dict[str, Any]] = field(default_factory=list)
    performance_summary: dict[str, Any] | None = None

    # 优化建议
    recommendations: list[str] = field(default_factory=list)

    # 元数据
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    has_performance_data: bool = False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（可JSON序列化）"""
        data = asdict(self)
        # 确保所有数据可以被 JSON 序列化
        return data

    def to_json(self, filepath: str | None = None, indent: int = 2) -> str:
        """
        转换为 JSON 字符串，可选保存到文件

        Args:
            filepath: 可选的文件路径
            indent: JSON 缩进空格数

        Returns:
            JSON 字符串
        """
        json_str = json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)

        return json_str

    def to_markdown(self) -> str:
        """生成 Markdown 格式报告"""
        lines = []

        # 标题
        lines.append(f"# 依赖分析报告：{self.target_name}\n")
        lines.append(f"**生成时间**: {self.analyzed_at}")
        lines.append(
            f"**分析模式**: {'动态分析（含性能数据）' if self.has_performance_data else '静态分析'}\n"
        )

        # 概览
        lines.append("## 📊 概览\n")
        lines.append(f"- **总插件数**: {self.total_plugins}")
        lines.append(f"- **DAG 深度**: {self.max_depth}")
        lines.append(f"- **DAG 宽度**: {self.max_width}")
        lines.append(f"- **执行计划**: {' → '.join(self.execution_plan)}\n")

        # 层次结构
        if self.layers:
            lines.append("## 🏗️ 层次结构\n")
            for depth in sorted(self.layers.keys()):
                plugins = self.layers[depth]
                lines.append(f"**深度 {depth}**: {', '.join(plugins)}")
            lines.append("")

        # 关键路径
        if self.critical_path:
            lines.append("## 🎯 关键路径\n")
            if self.critical_path_time is not None:
                lines.append(f"**总耗时**: {self.critical_path_time:.2f} 秒\n")

            for i, plugin in enumerate(self.critical_path, 1):
                # 尝试从性能摘要中获取时间
                time_info = ""
                if self.performance_summary and plugin in self.performance_summary:
                    stats = self.performance_summary[plugin]
                    mean_time = stats.get("mean_time", 0)
                    percentage = stats.get("time_percentage", 0) if self.critical_path_time else 0
                    time_info = f" ({mean_time:.2f}s, {percentage:.1f}%)"
                lines.append(f"{i}. {plugin}{time_info}")
            lines.append("")

        # 并行机会
        if self.parallel_groups:
            lines.append("## ⚡ 并行机会\n")
            lines.append(f"**理论加速比**: {self.parallelization_potential:.2f}x\n")

            for i, group in enumerate(self.parallel_groups, 1):
                lines.append(f"### 并行组 #{i}")
                lines.append(f"- **插件**: {', '.join(group)}")
                lines.append(f"- **插件数量**: {len(group)}\n")

        # 性能瓶颈
        if self.bottlenecks:
            lines.append("## 🔴 性能瓶颈\n")

            for i, bottleneck in enumerate(self.bottlenecks, 1):
                plugin = bottleneck["plugin_name"]
                severity = bottleneck["severity"].upper()
                metrics = bottleneck["metrics"]

                severity_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚪")

                lines.append(f"### {severity_icon} 瓶颈 #{i}: {plugin} [{severity}]")
                lines.append(f"- **平均执行时间**: {metrics.get('mean_time', 0):.2f}s")
                lines.append(f"- **时间占比**: {metrics.get('time_percentage', 0):.1f}%")
                lines.append(f"- **缓存命中率**: {metrics.get('cache_hit_rate', 0):.1%}")
                lines.append(f"- **调用次数**: {metrics.get('call_count', 0)}")

                if "peak_memory_mb" in metrics and metrics["peak_memory_mb"] > 0:
                    lines.append(f"- **峰值内存**: {metrics['peak_memory_mb']:.2f}MB")

                issues = bottleneck.get("issues", [])
                if issues:
                    lines.append(f"- **问题**: {', '.join(issues)}")

                lines.append("")

        # 优化建议
        if self.recommendations:
            lines.append("## 💡 优化建议\n")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        return "\n".join(lines)

    def save_markdown(self, filepath: str):
        """保存 Markdown 报告到文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_markdown())

    def __repr__(self) -> str:
        """返回格式化的摘要字符串，在 Jupyter notebook 中正确显示换行"""
        return self.summary()

    def _repr_pretty_(self, p, cycle):
        """IPython 美化显示支持，确保换行正确显示"""
        if cycle:
            p.text("DependencyAnalysisResult(...)")
        else:
            p.text(self.summary())

    def summary(self) -> str:
        """生成简要文本摘要"""
        lines = []
        lines.append(f"=== 依赖分析摘要：{self.target_name} ===")
        lines.append(f"分析模式: {'动态（含性能数据）' if self.has_performance_data else '静态'}")
        lines.append(f"总插件数: {self.total_plugins}")
        lines.append(f"DAG 深度: {self.max_depth}, 宽度: {self.max_width}")

        if self.critical_path:
            lines.append(f"\n关键路径 ({len(self.critical_path)} 个插件):")
            path_str = " → ".join(self.critical_path[:5])
            if len(self.critical_path) > 5:
                path_str += f" ... (还有 {len(self.critical_path) - 5} 个)"
            lines.append(f"  {path_str}")

            if self.critical_path_time is not None:
                lines.append(f"  总耗时: {self.critical_path_time:.2f}s")

        if self.parallel_groups:
            lines.append(f"\n并行机会: {len(self.parallel_groups)} 组")
            lines.append(f"  理论加速比: {self.parallelization_potential:.2f}x")

        if self.bottlenecks:
            lines.append(f"\n性能瓶颈: {len(self.bottlenecks)} 个")
            high_severity = [b for b in self.bottlenecks if b["severity"] == "high"]
            if high_severity:
                lines.append(f"  高严重性: {len(high_severity)} 个")

        if self.recommendations:
            lines.append(f"\n优化建议: {len(self.recommendations)} 条")
            lines.append(f"  首要建议: {self.recommendations[0]}")

        return "\n".join(lines)


@export
class DependencyAnalyzer:
    """依赖分析器 - 分析插件依赖关系图"""

    def __init__(self, context: Any):
        """
        初始化分析器

        Args:
            context: Context 实例
        """
        self.context = context

    def analyze(
        self,
        target_name: str,
        include_performance: bool = True,
        run_id: str | None = None,
    ) -> DependencyAnalysisResult:
        """
        执行依赖分析

        Args:
            target_name: 目标数据名称
            include_performance: 是否包含性能数据分析
            run_id: 可选的 run_id（暂未使用，为未来扩展预留）

        Returns:
            DependencyAnalysisResult: 分析结果
        """
        # 1. 获取血缘图
        lineage = self.context.get_lineage(target_name)
        plugins = {name: self.context._plugins.get(name) for name in lineage.keys()}
        graph = build_lineage_graph(lineage, target_name, plugins)

        # 2. 获取执行计划（拓扑排序）
        execution_plan = self._get_execution_plan(target_name)

        # 3. 静态结构分析
        static_analysis = self._analyze_static_structure(graph, execution_plan)

        # 4. 性能数据分析（如果可用）
        performance_data = None
        has_performance = False

        if include_performance and self.context.stats_collector:
            if self.context.stats_collector.is_enabled():
                performance_data = self._get_performance_data(execution_plan)
                has_performance = bool(performance_data)

        # 5. 关键路径分析
        if has_performance and performance_data:
            critical_path, critical_path_time = self._find_critical_path_dynamic(
                graph, execution_plan, performance_data
            )
        else:
            critical_path = self._find_critical_path_static(graph, execution_plan)
            critical_path_time = None

        # 6. 并行机会识别
        parallel_groups = self._find_parallel_opportunities(graph, execution_plan)
        parallelization_potential = self._calculate_parallelization_potential(
            parallel_groups, performance_data
        )

        # 7. 性能瓶颈识别
        bottlenecks = []
        if has_performance and performance_data:
            bottlenecks = self._identify_bottlenecks(
                performance_data, critical_path, execution_plan
            )

        # 8. 生成优化建议
        recommendations = self._generate_recommendations(
            static_analysis,
            critical_path,
            critical_path_time,
            parallel_groups,
            parallelization_potential,
            bottlenecks,
            has_performance,
        )

        # 9. 构建结果
        result = DependencyAnalysisResult(
            target_name=target_name,
            total_plugins=len(execution_plan),
            execution_plan=execution_plan,
            max_depth=static_analysis["max_depth"],
            max_width=static_analysis["max_width"],
            layers=static_analysis["layers"],
            critical_path=critical_path,
            critical_path_time=critical_path_time,
            parallel_groups=parallel_groups,
            parallelization_potential=parallelization_potential,
            bottlenecks=bottlenecks,
            performance_summary=performance_data,
            recommendations=recommendations,
            has_performance_data=has_performance,
        )

        return result

    def _get_execution_plan(self, target_name: str) -> list[str]:
        """获取执行计划（拓扑排序）"""
        # Context delegates dependency resolution to ContextPluginDomain.
        plan = self.context.resolve_dependencies(target_name)
        return plan

    def _analyze_static_structure(
        self, graph: LineageGraphModel, execution_plan: list[str]
    ) -> dict[str, Any]:
        """
        静态依赖分析（不需要性能数据）

        分析内容：
        1. DAG 层次结构（深度、宽度）
        2. 每层的插件数量
        3. 分支和汇聚点
        """
        # 按层次分组
        layers = defaultdict(list)
        for node_id, node in graph.nodes.items():
            if not node_id.startswith(("IN::", "OUT::")):  # 排除端口节点
                layers[node.depth].append(node_id)

        max_depth = max(layers.keys()) if layers else 0
        max_width = max(len(plugins) for plugins in layers.values()) if layers else 0

        return {
            "max_depth": max_depth,
            "max_width": max_width,
            "layers": dict(layers),
        }

    def _get_performance_data(self, execution_plan: list[str]) -> dict[str, Any] | None:
        """获取性能统计数据"""
        if not self.context.stats_collector:
            return None

        stats = self.context.stats_collector.get_statistics()
        if not stats:
            return None

        # 转换为字典格式
        performance_data = {}
        for plugin_name in execution_plan:
            if plugin_name in stats:
                stat = stats[plugin_name]
                performance_data[plugin_name] = {
                    "mean_time": stat.mean_time,
                    "total_calls": stat.total_calls,
                    "cache_hit_rate": stat.cache_hit_rate(),
                    "peak_memory_mb": stat.peak_memory_mb,
                }

        return performance_data if performance_data else None

    def _find_critical_path_static(
        self, graph: LineageGraphModel, execution_plan: list[str]
    ) -> list[str]:
        """
        基于 DAG 深度的关键路径（静态分析）

        假设所有插件权重相等，关键路径 = 最长的依赖链
        """
        # 找到最深的节点（排除端口节点）
        plugin_nodes = {
            nid: node for nid, node in graph.nodes.items() if not nid.startswith(("IN::", "OUT::"))
        }

        if not plugin_nodes:
            return []

        deepest_node = max(plugin_nodes.values(), key=lambda n: n.depth)

        # 回溯到根节点
        path = []
        current = deepest_node.key

        while current:
            path.append(current)
            # 找到深度最大的父节点
            parent = self._find_deepest_parent(graph, current)
            if parent == current:  # 避免死循环
                break
            current = parent

        return list(reversed(path))

    def _find_deepest_parent(self, graph: LineageGraphModel, node_id: str) -> str | None:
        """找到节点的深度最大的父节点"""
        node = graph.nodes.get(node_id)
        if not node or not node.in_ports:
            return None

        # 找到所有输入边
        parent_nodes = set()
        for edge in graph.edges:
            for port in node.in_ports:
                if edge.target_port_id == port.id:
                    # 找到源节点
                    for src_node_id, src_node in graph.nodes.items():
                        for src_port in src_node.out_ports:
                            if src_port.id == edge.source_port_id:
                                parent_nodes.add(src_node_id)

        if not parent_nodes:
            return None

        # 返回深度最大的父节点
        parents_with_depth = [
            (pid, graph.nodes[pid].depth) for pid in parent_nodes if pid in graph.nodes
        ]
        if not parents_with_depth:
            return None

        return max(parents_with_depth, key=lambda x: x[1])[0]

    def _find_critical_path_dynamic(
        self,
        graph: LineageGraphModel,
        execution_plan: list[str],
        performance_data: dict[str, Any],
    ) -> tuple[list[str], float]:
        """
        基于实际执行时间的关键路径（CPM算法）

        使用关键路径法（Critical Path Method）计算
        """
        # 1. 构建依赖关系图（仅包含插件节点）
        dependencies = self._build_dependency_graph(graph, execution_plan)

        # 2. 前向计算最早完成时间（ES - Earliest Start）
        earliest_start = {}
        earliest_finish = {}

        for node_id in execution_plan:
            # ES = max(EF of all predecessors)
            predecessors = dependencies.get(node_id, {}).get("predecessors", [])
            es = max([earliest_finish.get(p, 0) for p in predecessors], default=0)

            # 获取执行时间
            duration = performance_data.get(node_id, {}).get("mean_time", 0)
            ef = es + duration

            earliest_start[node_id] = es
            earliest_finish[node_id] = ef

        # 3. 反向计算最晚开始时间（LS - Latest Start）
        target = execution_plan[-1] if execution_plan else None
        if not target:
            return [], 0.0

        latest_start = {target: earliest_start.get(target, 0)}
        latest_finish = {target: earliest_finish.get(target, 0)}

        for node_id in reversed(execution_plan):
            successors = dependencies.get(node_id, {}).get("successors", [])
            if successors:
                lf = min(
                    [latest_start.get(s, float("inf")) for s in successors],
                    default=latest_finish.get(target, 0),
                )
            else:
                lf = latest_finish.get(target, 0)

            duration = performance_data.get(node_id, {}).get("mean_time", 0)
            ls = lf - duration

            latest_start[node_id] = ls
            latest_finish[node_id] = lf

        # 4. 计算松弛时间（Slack = LS - ES）
        slack = {n: latest_start.get(n, 0) - earliest_start.get(n, 0) for n in execution_plan}

        # 5. 松弛时间接近0的节点即关键路径
        critical_nodes = [n for n, s in slack.items() if abs(s) < 0.001]

        # 6. 按执行顺序排序
        critical_path = [n for n in execution_plan if n in critical_nodes]
        total_time = earliest_finish.get(target, 0)

        return critical_path, total_time

    def _build_dependency_graph(
        self, graph: LineageGraphModel, execution_plan: list[str]
    ) -> dict[str, dict[str, list[str]]]:
        """构建简化的依赖关系图"""
        dependencies = {node: {"predecessors": [], "successors": []} for node in execution_plan}

        for node_id in execution_plan:
            node = graph.nodes.get(node_id)
            if not node:
                continue

            # 找到所有前驱节点
            for edge in graph.edges:
                for in_port in node.in_ports:
                    if edge.target_port_id == in_port.id:
                        # 找到源节点
                        for src_id, src_node in graph.nodes.items():
                            if src_id in execution_plan:
                                for out_port in src_node.out_ports:
                                    if out_port.id == edge.source_port_id:
                                        if src_id not in dependencies[node_id]["predecessors"]:
                                            dependencies[node_id]["predecessors"].append(src_id)
                                        if node_id not in dependencies[src_id]["successors"]:
                                            dependencies[src_id]["successors"].append(node_id)

        return dependencies

    def _find_parallel_opportunities(
        self, graph: LineageGraphModel, execution_plan: list[str]
    ) -> list[list[str]]:
        """
        识别可并行执行的插件组

        原理：同一层（depth相同）且无直接依赖关系的插件可并行
        """
        # 按深度分组
        layers = defaultdict(list)
        for node_id, node in graph.nodes.items():
            if node_id in execution_plan:  # 只考虑插件节点
                layers[node.depth].append(node_id)

        parallel_groups = []

        for _depth, plugins in layers.items():
            if len(plugins) > 1:
                # 该层有多个插件，检查它们是否真的独立
                # 简化版本：假设同一层的插件都可以并行
                parallel_groups.append(sorted(plugins))

        return [g for g in parallel_groups if len(g) > 1]

    def _calculate_parallelization_potential(
        self,
        parallel_groups: list[list[str]],
        performance_data: dict[str, Any] | None,
    ) -> float:
        """
        计算理论加速比

        Speedup = T_sequential / T_parallel
        """
        if not parallel_groups:
            return 1.0

        if not performance_data:
            # 静态估算：假设均匀分布
            max_group_size = max(len(g) for g in parallel_groups)
            return float(max_group_size)

        # 动态计算：基于实际时间
        total_sequential = sum(data.get("mean_time", 0) for data in performance_data.values())

        if total_sequential == 0:
            return 1.0

        # 计算并行执行时间（每组取最大）
        total_parallel = total_sequential
        for group in parallel_groups:
            group_times = [performance_data.get(p, {}).get("mean_time", 0) for p in group]
            if group_times:
                saved_time = sum(group_times) - max(group_times)
                total_parallel -= saved_time

        return total_sequential / total_parallel if total_parallel > 0 else 1.0

    def _identify_bottlenecks(
        self,
        performance_data: dict[str, Any],
        critical_path: list[str],
        execution_plan: list[str],
    ) -> list[dict[str, Any]]:
        """
        识别性能瓶颈

        瓶颈判断规则：
        1. 执行时间占比 > 20% → high severity
        2. 在关键路径上 → 提升优先级
        3. 缓存命中率 < 30% → 缓存问题
        4. 频繁调用且单次耗时长 → 优化目标
        5. 内存使用 > 1GB → 内存瓶颈
        """
        total_time = sum(
            data.get("mean_time", 0) * data.get("total_calls", 1)
            for data in performance_data.values()
        )

        if total_time == 0:
            return []

        bottlenecks = []

        for plugin_name, data in performance_data.items():
            mean_time = data.get("mean_time", 0)
            total_calls = data.get("total_calls", 1)
            cache_hit_rate = data.get("cache_hit_rate", 1.0)
            peak_memory = data.get("peak_memory_mb", 0)

            plugin_total_time = mean_time * total_calls
            time_percentage = (plugin_total_time / total_time * 100) if total_time > 0 else 0

            issues = []
            severity = "low"

            # 规则1：执行时间占比高
            if time_percentage > 20:
                issues.append("execution_time")
                severity = "high"
            elif time_percentage > 10:
                issues.append("execution_time")
                severity = "medium"

            # 规则2：缓存命中率低
            if cache_hit_rate < 0.3 and total_calls > 5:
                issues.append("cache_miss")
                if severity == "low":
                    severity = "medium"

            # 规则3：内存使用高
            if peak_memory > 1024:  # > 1GB
                issues.append("memory")
                if severity == "low":
                    severity = "medium"

            # 规则4：在关键路径上
            if plugin_name in critical_path:
                issues.append("critical_path")
                # 提升严重性等级
                if severity == "low":
                    severity = "medium"
                elif severity == "medium":
                    severity = "high"

            # 规则5：频繁调用
            if total_calls > 10 and mean_time > 1.0:
                issues.append("frequency")

            if issues:
                bottlenecks.append(
                    {
                        "plugin_name": plugin_name,
                        "severity": severity,
                        "issues": issues,
                        "metrics": {
                            "mean_time": mean_time,
                            "time_percentage": time_percentage,
                            "cache_hit_rate": cache_hit_rate,
                            "call_count": total_calls,
                            "peak_memory_mb": peak_memory,
                        },
                    }
                )

        # 按严重性和时间占比排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        bottlenecks.sort(
            key=lambda x: (
                severity_order[x["severity"]],
                -x["metrics"]["time_percentage"],
            )
        )

        return bottlenecks

    def _generate_recommendations(
        self,
        static_analysis: dict[str, Any],
        critical_path: list[str],
        critical_path_time: float | None,
        parallel_groups: list[list[str]],
        parallelization_potential: float,
        bottlenecks: list[dict[str, Any]],
        has_performance: bool,
    ) -> list[str]:
        """基于分析结果生成优化建议"""
        recommendations = []

        # 建议1：关键路径优化
        if critical_path and has_performance:
            top_critical = critical_path[:3]
            time_info = f"（总耗时 {critical_path_time:.2f}s）" if critical_path_time else ""
            recommendations.append(
                f"🎯 关键路径优化：重点关注 {', '.join(top_critical)}{time_info}，"
                f"它们决定了整体执行时间"
            )

        # 建议2：并行执行
        if parallel_groups and parallelization_potential > 1.2:
            for i, group in enumerate(parallel_groups[:3], 1):
                recommendations.append(
                    f"⚡ 并行机会 #{i}：{', '.join(group)} 可以并行执行，"
                    f"预计加速 {len(group):.1f}x"
                )

        # 建议3：瓶颈优化（按严重性）
        for i, bottleneck in enumerate(bottlenecks[:5], 1):
            plugin = bottleneck["plugin_name"]
            issues = bottleneck["issues"]
            metrics = bottleneck["metrics"]
            severity_icon = "🔴" if bottleneck["severity"] == "high" else "🟡"

            if "execution_time" in issues:
                recommendations.append(
                    f"{severity_icon} 瓶颈 #{i}: {plugin} 占总执行时间 "
                    f"{metrics['time_percentage']:.1f}%，建议优化算法或启用缓存"
                )

            if "cache_miss" in issues:
                recommendations.append(
                    f"💾 缓存优化: {plugin} 缓存命中率仅 "
                    f"{metrics['cache_hit_rate']:.1%}，检查缓存失效原因"
                )

            if "memory" in issues:
                recommendations.append(
                    f"🧠 内存优化: {plugin} 峰值内存 "
                    f"{metrics['peak_memory_mb']:.1f}MB，考虑分块处理或流式处理"
                )

        # 建议4：架构优化
        max_depth = static_analysis.get("max_depth", 0)
        max_width = static_analysis.get("max_width", 0)

        if max_depth > 10:
            recommendations.append(
                f"📊 架构建议：依赖链深度达 {max_depth} 层，" f"考虑合并部分插件以减少开销"
            )

        if max_width > 5:
            recommendations.append(
                f"🌊 并行架构：最大宽度 {max_width}，" f"确保使用足够的 workers 支持并行执行"
            )

        # 如果没有性能数据，给出提示
        if not has_performance:
            recommendations.append(
                "📈 数据收集建议：启用性能统计（enable_stats=True）以获得更详细的分析和建议"
            )

        return recommendations
