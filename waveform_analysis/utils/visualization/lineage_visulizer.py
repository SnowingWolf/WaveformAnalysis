from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle

from waveform_analysis.core.models import LineageGraphModel, build_lineage_graph
from waveform_analysis.core.utils import LineageStyle, get_plugin_dtype, get_plugin_title, get_plugins_from_context


def plot_lineage_labview(
    lineage: Any,
    target_name: str,
    context: Any = None,
    style: Optional[LineageStyle] = None,
    show_dtype_on_wire: bool = True,
    **kwargs,
):
    """
    绘制高度可定制的 LabVIEW 风格插件血缘图。

    参数:
        lineage: 可以是 lineage 字典，也可以是 LineageGraphModel 实例。
        target_name: 目标数据名称。
        context: Context 实例，用于获取插件信息。
        style: 样式配置。
        show_dtype_on_wire: 是否在连线上显示数据类型。
    """
    s = style or LineageStyle()
    # 合并用户通过 kwargs 传入的覆盖参数
    for k, v in kwargs.items():
        if hasattr(s, k):
            setattr(s, k, v)

    # 1. 确保我们有一个 LineageGraphModel
    if isinstance(lineage, dict):
        plugins = get_plugins_from_context(context)
        model = build_lineage_graph(lineage, target_name, plugins)
    elif isinstance(lineage, LineageGraphModel):
        model = lineage
    else:
        raise ValueError("lineage must be a dict or LineageGraphModel")

    # 2. 布局计算 (基于模型)
    pos = {}
    nodes_by_depth = {}
    for node_id, node in model.nodes.items():
        nodes_by_depth.setdefault(node.depth, []).append(node_id)

    max_d = max(n.depth for n in model.nodes.values()) if model.nodes else 0
    for d, vis in nodes_by_depth.items():
        x = (max_d - d) * s.x_gap
        for i, vi in enumerate(sorted(vis)):
            y = (i - (len(vis) - 1) / 2.0) * s.y_gap
            pos[vi] = (x, y)

            # 计算端口位置
            node = model.nodes[vi]
            for k, port in enumerate(node.in_ports):
                dy = (k - (len(node.in_ports) - 1) / 2.0) * 0.4 if len(node.in_ports) > 1 else 0
                pos[port.id] = (x - s.node_width / 2, y + dy)
            for k, port in enumerate(node.out_ports):
                dy = (k - (len(node.out_ports) - 1) / 2.0) * 0.4 if len(node.out_ports) > 1 else 0
                pos[port.id] = (x + s.node_width / 2, y + dy)

    # 3. 绘图
    fig, ax = plt.subplots(figsize=(max(12, max_d * 3), 6))

    def draw_wire(p1, p2, color):
        x1, y1 = p1
        x2, y2 = p2
        mx = (x1 + x2) / 2.0
        ax.plot([x1, mx, mx, x2], [y1, y1, y2, y2], color=color, lw=s.wire_linewidth, alpha=s.wire_alpha, zorder=1)
        ax.add_patch(
            FancyArrowPatch(
                (mx, y2), (x2, y2), arrowstyle="-|>", color=color, mutation_scale=s.arrow_mutation_scale, zorder=2
            )
        )
        return mx, (y1 + y2) / 2.0

    # 绘制连线
    for edge in model.edges:
        c = s.type_colors.get(edge.dtype, s.type_colors["Unknown"])
        p1 = pos.get(edge.source_port_id)
        p2 = pos.get(edge.target_port_id)
        if p1 and p2:
            mx, my = draw_wire(p1, p2, c)
            if show_dtype_on_wire:
                ax.text(
                    mx,
                    my + 0.12,
                    edge.dtype,
                    fontsize=s.font_size_wire,
                    color=c,
                    ha="center",
                    bbox=dict(fc="white", ec="none", alpha=0.7, boxstyle="round,pad=0.1"),
                )

    # 绘制节点
    for node_id, (x, y) in pos.items():
        if node_id.startswith("IN::") or node_id.startswith("OUT::"):
            # 绘制端口
            # 我们需要找到对应的 PortModel
            port = None
            # 简单起见，从模型中查找
            for n in model.nodes.values():
                for p in n.in_ports + n.out_ports:
                    if p.id == node_id:
                        port = p
                        break
                if port:
                    break

            if not port:
                continue

            c = s.type_colors.get(port.dtype, s.type_colors["Unknown"])
            ax.add_patch(
                Rectangle(
                    (x - s.port_size / 2, y - s.port_size / 2), s.port_size, s.port_size, fc=c, ec=s.node_edge, zorder=6
                )
            )

            if port.kind == "in":
                ax.text(
                    x + 0.12,
                    y,
                    port.name,
                    fontsize=s.font_size_port,
                    color=s.text_color,
                    ha="left",
                    va="center",
                    zorder=6,
                )
            else:
                ax.text(
                    x - 0.12,
                    y,
                    port.name,
                    fontsize=s.font_size_port,
                    color=s.text_color,
                    ha="right",
                    va="center",
                    zorder=6,
                )
            continue

        # 绘制 VI 节点
        node = model.nodes.get(node_id)
        if not node:
            continue

        # 主体
        ax.add_patch(
            Rectangle(
                (x - s.node_width / 2, y - s.node_height / 2),
                s.node_width,
                s.node_height,
                fc=s.node_bg,
                ec=s.node_edge,
                lw=2,
                zorder=3,
            )
        )
        # 标题栏
        ax.add_patch(
            Rectangle(
                (x - s.node_width / 2, y + s.node_height / 2 - s.header_height),
                s.node_width,
                s.header_height,
                fc=s.header_bg,
                ec=s.node_edge,
                lw=1,
                zorder=4,
            )
        )
        ax.text(
            x,
            y + s.node_height / 2 - s.header_height / 2,
            node.title,
            fontsize=s.font_size_title,
            fontweight="bold",
            color=s.text_color,
            ha="center",
            va="center",
            zorder=5,
        )

        # 根据 verbose 等级显示 key/class
        if s.verbose >= 1:
            ax.text(
                x,
                y + 0.25,
                f"key: {node.key}",
                fontsize=s.font_size_key,
                style="italic",
                color=s.text_color,
                ha="center",
                zorder=5,
            )
        if s.verbose >= 2:
            ax.text(
                x,
                y + 0.1,
                f"class: {node.plugin_class}",
                fontsize=s.font_size_key - 1,
                color="#7f8c8d",
                ha="center",
                zorder=5,
            )

        # 显示自定义描述
        if node.description and s.verbose >= 1:
            ax.text(
                x,
                y - 0.1,
                node.description,
                fontsize=s.font_size_key - 1,
                color="#34495e",
                ha="center",
                va="top",
                zorder=5,
                wrap=True,
            )

        # 配置信息
        cfg = node.config
        if cfg and s.verbose >= 1:
            max_items = 5 if s.verbose >= 2 else 3
            cfg_items = list(cfg.items())[:max_items]
            cfg_text = "\n".join([f"{k}: {v}" for k, v in cfg_items])
            ax.text(
                x,
                y - s.node_height / 2 + 0.15,
                cfg_text,
                fontsize=s.font_size_port - 1,
                ha="center",
                va="bottom",
                zorder=5,
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="#dcdde1", alpha=0.5),
            )

    ax.set_title(f"Data Lineage: {target_name}", fontsize=14, fontweight="bold", pad=20)
    ax.axis("off")
    plt.tight_layout()
    plt.show()

    ax.set_title(f"Data Lineage: {target_name}", fontsize=14, fontweight="bold", pad=20)
    ax.axis("off")
    plt.tight_layout()
    plt.show()
