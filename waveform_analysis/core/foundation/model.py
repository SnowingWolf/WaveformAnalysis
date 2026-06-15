"""
Model 模块 (lineage 图) - 框架内部数据模型定义。

定义了插件系统、数据流图以及配置管理中使用的基础数据结构，
如 PortModel, NodeModel, GraphModel 等，用于描述处理流程的拓扑结构。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PortModel:
    id: str
    name: str
    kind: str  # 'in' or 'out'
    dtype: str
    parent_node_id: str
    index: int


@dataclass
class NodeModel:
    id: str
    key: str
    title: str
    plugin_class: str
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    in_ports: list[PortModel] = field(default_factory=list)
    out_ports: list[PortModel] = field(default_factory=list)
    depth: int = 0


@dataclass
class EdgeModel:
    source_node_id: str
    source_port_id: str
    target_node_id: str
    target_port_id: str
    dtype: str = "unknown"


@dataclass
class LineageGraphModel:
    nodes: dict[str, NodeModel] = field(default_factory=dict)
    edges: list[EdgeModel] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_mermaid(self) -> str:
        """
        将模型转换为 Mermaid.js 流程图字符串。
        """
        # Start a left-to-right flowchart.
        lines = ["graph LR"]

        # 1. 定义节点
        for node_id, node in self.nodes.items():
            # Mermaid 节点 ID 不能包含特殊字符
            safe_id = node_id.replace("[", "_").replace("]", "_").replace(".", "_")
            label = f"{node.title}<br/>({node.plugin_class})"
            lines.append(f'    {safe_id}["{label}"]')

        # 2. 定义连线
        for edge in self.edges:
            src_id = edge.source_node_id.replace("[", "_").replace("]", "_").replace(".", "_")
            dst_id = edge.target_node_id.replace("[", "_").replace("]", "_").replace(".", "_")

            # 可以包含端口信息
            lines.append(f'    {src_id} -- "{edge.dtype}" --> {dst_id}')

        return "\n".join(lines)


def build_lineage_graph(
    lineage: dict[str, Any],
    target_name: str,
    plugins: dict[str, Any] | None = None,
) -> LineageGraphModel:
    """
    将血缘字典转换为纯数据结构的 LineageGraphModel。
    """
    from waveform_analysis.core.foundation.utils import get_plugin_dtypes, get_plugin_title

    model = LineageGraphModel()
    # Normalize plugins map to simplify downstream lookups.
    plugins = plugins or {}

    # 第一阶段：遍历收集所有节点和依赖关系
    visited = set()
    plugin_info = {}
    dependencies = {}  # {node: [依赖的节点列表]}

    def traverse(name, info):
        # DFS to collect node info and dependency edges.
        if name in visited:
            return
        visited.add(name)
        info = info or {}
        plugin_info[name] = info
        deps = info.get("depends_on", {}) or {}
        dependencies[name] = list(deps.keys())
        for dep_name, dep_info in deps.items():
            traverse(dep_name, dep_info)

    traverse(target_name, lineage)

    # 第二阶段：计算拓扑层级 depth（从源节点开始的正向层级）
    # depth 表示从源节点到该节点的最长路径长度
    plugin_depth: dict[str, int] = {}

    # 1. 找到所有源节点（没有依赖的节点）
    sources = [name for name, deps in dependencies.items() if not deps]
    for src in sources:
        plugin_depth[src] = 0

    # 2. 使用迭代算法计算每个节点的 depth
    # depth(node) = max(depth(dep) for dep in node的直接依赖) + 1
    changed = True
    max_iterations = 1000  # 防止循环依赖导致死循环
    iteration = 0

    while changed and iteration < max_iterations:
        iteration += 1
        changed = False
        for node, deps in dependencies.items():
            if node in plugin_depth:
                continue
            # 只有当所有依赖都已计算出 depth 时，才计算该节点
            if deps and all(dep in plugin_depth for dep in deps):
                new_depth = max(plugin_depth[dep] for dep in deps) + 1
                plugin_depth[node] = new_depth
                changed = True

    # 3. 处理未计算 depth 的节点（孤立节点或循环依赖）
    for node in plugin_info:
        if node not in plugin_depth:
            # 孤立节点设为 0，与源节点相同
            plugin_depth[node] = 0

    # 1. 创建节点和端口
    for p, info in plugin_info.items():
        node = NodeModel(
            id=p,
            key=p,
            title=get_plugin_title(p, info, plugins),
            plugin_class=info.get("plugin_class", "UnknownPlugin"),
            description=info.get("description", ""),
            config=info.get("config", {}) or {},
            depth=plugin_depth.get(p, 0),
        )

        # 获取输入输出类型

        in_dtype_str, out_dtype_str = get_plugin_dtypes(p, plugins)

        # 输入端口
        deps = sorted((info.get("depends_on", {}) or {}).keys())
        for i, dep_p in enumerate(deps):
            # 获取依赖项的输出类型作为本端口的输入类型
            _, dep_out_dtype = get_plugin_dtypes(dep_p, plugins)
            port = PortModel(
                id=f"IN::{p}::{i}",
                name=dep_p,
                kind="in",
                dtype=dep_out_dtype,
                parent_node_id=p,
                index=i,
            )
            node.in_ports.append(port)

        # 输出端口
        provides = info.get("provides", p)
        prov_list = [provides] if isinstance(provides, str) else list(provides or [p])
        for i, label in enumerate(prov_list):
            port = PortModel(
                id=f"OUT::{p}::{i}",
                name=label,
                kind="out",
                dtype=out_dtype_str,
                parent_node_id=p,
                index=i,
            )
            node.out_ports.append(port)

        model.nodes[p] = node

    # 2. 创建连线 (Edges)
    # 我们需要找到哪个输出端口连接到哪个输入端口
    # 规则：如果 Node B 依赖于 Node A 的输出 'X'，则连线 A.OUT(X) -> B.IN(X)
    for target_p, info in plugin_info.items():
        deps = info.get("depends_on", {}) or {}
        for dep_p in deps.keys():
            if dep_p not in model.nodes:
                continue

            source_node = model.nodes[dep_p]
            target_node = model.nodes[target_p]

            # 寻找源节点的输出端口
            source_port = None
            for p_out in source_node.out_ports:
                if p_out.name == dep_p:
                    source_port = p_out
                    break

            # 寻找目标节点的输入端口
            target_port = None
            for p_in in target_node.in_ports:
                if p_in.name == dep_p:
                    target_port = p_in
                    break

            if source_port and target_port:
                # Link the matching output/input port pair.
                model.edges.append(
                    EdgeModel(
                        source_node_id=source_node.id,
                        source_port_id=source_port.id,
                        target_node_id=target_node.id,
                        target_port_id=target_port.id,
                        dtype=source_port.dtype,
                    )
                )

    return model
