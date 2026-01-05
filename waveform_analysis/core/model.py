"""
Model 模块 - 框架内部数据模型定义。

定义了插件系统、数据流图以及配置管理中使用的基础数据结构，
如 PortModel, NodeModel, GraphModel 等，用于描述处理流程的拓扑结构。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    config: Dict[str, Any] = field(default_factory=dict)
    in_ports: List[PortModel] = field(default_factory=list)
    out_ports: List[PortModel] = field(default_factory=list)
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
    nodes: Dict[str, NodeModel] = field(default_factory=dict)
    edges: List[EdgeModel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_mermaid(self) -> str:
        """
        将模型转换为 Mermaid.js 流程图字符串。
        """
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
    lineage: Dict[str, Any],
    target_name: str,
    plugins: Optional[Dict[str, Any]] = None,
) -> LineageGraphModel:
    """
    将血缘字典转换为纯数据结构的 LineageGraphModel。
    """
    from waveform_analysis.core.utils import get_plugin_dtypes, get_plugin_title

    model = LineageGraphModel()
    plugins = plugins or {}

    visited = set()
    plugin_info = {}
    plugin_depth = {}

    def traverse(name, info, depth=0):
        if name in visited:
            plugin_depth[name] = min(plugin_depth.get(name, depth), depth)
            return
        visited.add(name)
        info = info or {}
        plugin_info[name] = info
        plugin_depth[name] = depth
        deps = info.get("depends_on", {}) or {}
        for dep_name, dep_info in deps.items():
            traverse(dep_name, dep_info, depth + 1)

    traverse(target_name, lineage)

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
        from waveform_analysis.core.utils import get_plugin_dtypes

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
