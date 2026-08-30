"""Matplotlib implementation for lineage visualization."""

from typing import Any

from matplotlib.patches import Circle, FancyArrowPatch, Rectangle
import matplotlib.pyplot as plt

from waveform_analysis.core.foundation.model import (
    LineageGraphModel,
    PortModel,
    build_lineage_graph,
)
from waveform_analysis.core.foundation.utils import LineageStyle, get_plugins_from_context
from waveform_analysis.visualization.lineage_visualizer import (
    _build_node_boxes,
    _classify_node_type,
    _get_node_colors,
    _layout_nodes_source_to_target,
    _layout_view_metrics,
    _mpl_dash,
    _node_heights_for,
    _resolve_wire_style,
    _route_edge_path,
    _wrap_text_lines,
)


def plot_lineage_labview(
    lineage: Any,
    target_name: str,
    context: Any = None,
    style: LineageStyle | None = None,
    save_path: str | None = None,
    data_wires: bool = False,
    interactive: bool = False,
    analysis_result: Any = None,  # DependencyAnalysisResult
    highlight_critical_path: bool = False,
    highlight_bottlenecks: bool = False,
    highlight_parallel_groups: bool = False,
    **kwargs,
):
    """
    绘制高度可定制的 LabVIEW 风格插件血缘图。

    参数:
        lineage: 可以是 lineage 字典，也可以是 LineageGraphModel 实例。
        target_name: 目标数据名称。
        context: Context 实例，用于获取插件信息。
        style: 样式配置。
        save_path: 可选，保存图片路径。
        data_wires: 是否在连线上显示数据类型。
        interactive: 是否启用交互式功能（鼠标悬停显示详情）。
        analysis_result: DependencyAnalysisResult 对象（可选）。
        highlight_critical_path: 是否高亮关键路径（需要 analysis_result）。
        highlight_bottlenecks: 是否高亮瓶颈节点（需要 analysis_result）。
        highlight_parallel_groups: 是否标记并行组（需要 analysis_result）。
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
        # 验证 build_lineage_graph 返回了正确的类型
        if not isinstance(model, LineageGraphModel):
            raise ValueError(
                f"build_lineage_graph returned unexpected type: {type(model).__name__}, "
                f"expected LineageGraphModel. This may indicate a bug in build_lineage_graph."
            )
    elif isinstance(lineage, LineageGraphModel):
        model = lineage
    else:
        raise ValueError(
            f"lineage must be a dict or LineageGraphModel, but got {type(lineage).__name__}: {lineage}"
        )

    # 2. 布局计算 (基于模型)
    node_heights = _node_heights_for(model, s)
    pos = _layout_nodes_source_to_target(model, s, node_heights)

    # 3. 准备分析数据（用于高亮）
    critical_path_set = set()
    bottleneck_map = {}  # {plugin_name: severity}
    parallel_group_map = {}  # {plugin_name: group_index}
    parallel_colors = ["#3498db", "#2ecc71", "#9b59b6", "#e67e22", "#1abc9c"]

    if analysis_result:
        if highlight_critical_path and hasattr(analysis_result, "critical_path"):
            critical_path_set = set(analysis_result.critical_path)

        if highlight_bottlenecks and hasattr(analysis_result, "bottlenecks"):
            for bottleneck in analysis_result.bottlenecks:
                bottleneck_map[bottleneck["plugin_name"]] = bottleneck["severity"]

        if highlight_parallel_groups and hasattr(analysis_result, "parallel_groups"):
            for i, group in enumerate(analysis_result.parallel_groups):
                for plugin_name in group:
                    parallel_group_map[plugin_name] = i

    # 4. 绘图
    view = _layout_view_metrics(pos, s, node_heights)
    fig, ax = plt.subplots(figsize=view["mpl_figsize"])
    node_boxes = _build_node_boxes(model, pos, s, node_heights)

    def draw_wire(path: list[tuple], wire_style: dict) -> None:
        line_x = [point[0] for point in path]
        line_y = [point[1] for point in path]
        linestyle = _mpl_dash(wire_style.get("dash"))
        ax.plot(
            line_x,
            line_y,
            color=wire_style["color"],
            lw=wire_style["width"],
            alpha=wire_style["alpha"],
            zorder=1,
            solid_capstyle=getattr(s, "wire_capstyle", "round"),
            solid_joinstyle=getattr(s, "wire_joinstyle", "round"),
            linestyle=linestyle,
        )
        start = path[-2]
        end = path[-1]
        ax.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                color=wire_style["color"],
                mutation_scale=s.arrow_mutation_scale,
                linewidth=wire_style["width"],
                linestyle=linestyle,
                zorder=2,
            )
        )

    # 先绘制连线，再绘制节点，避免线条压住节点文字。
    for edge in model.edges:
        wire_style = _resolve_wire_style(edge, s)
        p1 = pos.get(edge.source_port_id)
        p2 = pos.get(edge.target_port_id)
        if p1 and p2:
            path, label_pos = _route_edge_path(p1, p2, edge, node_boxes, s)
            draw_wire(path, wire_style)
            if data_wires:
                ax.text(
                    label_pos[0],
                    label_pos[1] + 0.12,
                    edge.dtype,
                    fontsize=s.font_size_wire,
                    color=wire_style["color"],
                    ha="center",
                    bbox={"fc": "white", "ec": "none", "alpha": 0.85, "boxstyle": "round,pad=0.1"},
                    zorder=12,
                )

    # 绘制节点
    for node_id, (x, y) in pos.items():
        if node_id.startswith("IN::") or node_id.startswith("OUT::"):
            # 绘制端口
            # 我们需要找到对应的 PortModel
            port: PortModel | None = None
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
                    (x - s.port_size / 2, y - s.port_size / 2),
                    s.port_size,
                    s.port_size,
                    fc=c,
                    ec=s.node_edge,
                    zorder=6,
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
        node_height = node_heights[node_id]

        # 根据节点类型确定颜色
        node_type = _classify_node_type(node)
        node_bg, node_edge_color, header_bg = _get_node_colors(node_type)
        node_edge_width = 2

        # 高亮关键路径（优先级更高）
        if node_id in critical_path_set:
            node_edge_color = "#e74c3c"  # 红色边框
            node_edge_width = 4

        # 高亮瓶颈节点（优先级更高）
        if node_id in bottleneck_map:
            severity = bottleneck_map[node_id]
            if severity == "high":
                node_bg = "#ffe5e5"  # 浅红色背景
                node_edge_color = "#e74c3c"  # 红色边框
                node_edge_width = 3
            elif severity == "medium":
                node_bg = "#fff4e5"  # 浅橙色背景
                node_edge_color = "#f39c12"  # 橙色边框
                node_edge_width = 3
            else:  # low
                node_bg = "#fffbe5"  # 浅黄色背景

        # 主体
        ax.add_patch(
            Rectangle(
                (x - s.node_width / 2, y - node_height / 2),
                s.node_width,
                node_height,
                fc=node_bg,
                ec=node_edge_color,
                lw=node_edge_width,
                zorder=3,
            )
        )
        # 标题栏
        ax.add_patch(
            Rectangle(
                (x - s.node_width / 2, y + node_height / 2 - s.header_height),
                s.node_width,
                s.header_height,
                fc=header_bg,
                ec=s.node_edge,
                lw=1,
                zorder=4,
            )
        )
        ax.text(
            x,
            y + node_height / 2 - s.header_height / 2,
            node.key,
            fontsize=s.font_size_title,
            fontweight="bold",
            color=s.text_color,
            ha="center",
            va="center",
            zorder=5,
        )

        # 根据 verbose 等级显示 class
        line_height = 0.16
        content_top = y + node_height / 2 - s.header_height - 0.1
        content_bottom = y - node_height / 2 + 0.2
        class_y = content_top - 0.05
        if s.verbose >= 1:
            ax.text(
                x,
                class_y,
                f"class: {node.plugin_class}",
                fontsize=s.font_size_key - 1,
                color="#7f8c8d",
                ha="center",
                va="center",
                zorder=5,
            )

        # 显示自定义描述（支持换行）
        desc_top = class_y - line_height * 0.9
        cfg = node.config
        cfg_items = list(cfg.items()) if cfg else []
        cfg_lines = min(5, len(cfg_items)) if (cfg and s.verbose >= 2) else 0
        cfg_height = cfg_lines * line_height
        cfg_top = content_bottom + cfg_height if cfg_lines else content_bottom
        max_desc_lines = int((desc_top - cfg_top - 0.05) / line_height)

        if node.description and s.verbose >= 2 and max_desc_lines > 0:
            max_width_chars = int(s.node_width * 12)
            desc_lines = _wrap_text_lines(node.description, max_width_chars, max_desc_lines)
            if desc_lines:
                ax.text(
                    x,
                    desc_top,
                    "\n".join(desc_lines),
                    fontsize=s.font_size_key - 1,
                    color="#34495e",
                    ha="center",
                    va="top",
                    zorder=5,
                )

        # 并行组标记
        if node_id in parallel_group_map:
            group_idx = parallel_group_map[node_id]
            badge_color = parallel_colors[group_idx % len(parallel_colors)]
            # 在右上角显示小徽章
            badge_x = x + s.node_width / 2 - 0.2
            badge_y = y + node_height / 2 - 0.15
            ax.add_patch(
                Circle(
                    (badge_x, badge_y),
                    0.12,
                    fc=badge_color,
                    ec="white",
                    lw=2,
                    zorder=10,
                )
            )
            ax.text(
                badge_x,
                badge_y,
                f"P{group_idx + 1}",
                fontsize=8,
                color="white",
                ha="center",
                va="center",
                fontweight="bold",
                zorder=11,
            )

        # 配置信息
        if cfg and s.verbose >= 2 and cfg_lines > 0:
            cfg_text = "\n".join([f"{k}: {v}" for k, v in cfg_items[:cfg_lines]])
            ax.text(
                x,
                content_bottom,
                cfg_text,
                fontsize=s.font_size_port - 1,
                ha="center",
                va="bottom",
                zorder=5,
                bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "#dcdde1", "alpha": 0.5},
            )

    ax.set_title(f"Data Lineage: {target_name}", fontsize=14, fontweight="bold", pad=20)
    ax.set_xlim(view["x_range"])
    ax.set_ylim(view["y_range"])
    ax.axis("off")
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight", pad_inches=0.2)

    # 交互式功能
    if interactive:
        _add_interactive_features(fig, ax, model, pos, s, node_heights)

    plt.show()
    return fig


def _add_interactive_features(
    fig,
    ax,
    model: LineageGraphModel,
    pos: dict,
    style: LineageStyle,
    node_heights: dict[str, float],
):
    """
    为血缘图添加交互式功能。

    参数:
        fig: matplotlib figure 对象
        ax: matplotlib axes 对象
        model: LineageGraphModel 实例
        pos: 节点位置字典 {node_id: (x, y)}
        style: LineageStyle 样式配置
    """
    # 创建 annotation 对象用于显示 tooltip
    annot = ax.annotate(
        "",
        xy=(0, 0),
        xytext=(20, 20),
        textcoords="offset points",
        bbox={"boxstyle": "round,pad=0.8", "fc": "yellow", "alpha": 0.9, "ec": "black", "lw": 2},
        arrowprops={"arrowstyle": "->", "connectionstyle": "arc3,rad=0", "lw": 2},
        fontsize=10,
        visible=False,
        zorder=100,
    )

    # 存储节点和端口的边界框，用于快速碰撞检测
    node_bounds = {}  # {node_id: (x_min, x_max, y_min, y_max)}
    port_bounds = {}  # {port_id: (x_min, x_max, y_min, y_max)}

    # 计算节点边界框
    for node_id, (x, y) in pos.items():
        if node_id.startswith(("IN::", "OUT::")):
            # 端口边界框
            half_size = style.port_size / 2
            port_bounds[node_id] = (x - half_size, x + half_size, y - half_size, y + half_size)
        else:
            # VI 节点边界框
            half_w = style.node_width / 2
            half_h = node_heights[node_id] / 2
            node_bounds[node_id] = (x - half_w, x + half_w, y - half_h, y + half_h)

    def _get_node_info(node_id: str) -> str:
        """生成节点的详细信息文本"""
        node = model.nodes.get(node_id)
        if not node:
            return ""

        info_lines = [
            f"插件: {node.title}",
            f"Key: {node.key}",
            f"Class: {node.plugin_class}",
            f"深度: {node.depth}",
        ]

        if node.description:
            info_lines.append(f"描述: {node.description}")

        if node.config:
            info_lines.append("\n配置:")
            for k, v in list(node.config.items())[:5]:
                info_lines.append(f"  {k}: {v}")
            if len(node.config) > 5:
                info_lines.append(f"  ... (还有 {len(node.config) - 5} 项)")

        if node.in_ports:
            info_lines.append(f"\n输入端口 ({len(node.in_ports)}):")
            for port in node.in_ports[:3]:
                info_lines.append(f"  • {port.name} ({port.dtype})")
            if len(node.in_ports) > 3:
                info_lines.append(f"  ... (还有 {len(node.in_ports) - 3} 个)")

        if node.out_ports:
            info_lines.append(f"\n输出端口 ({len(node.out_ports)}):")
            for port in node.out_ports[:3]:
                info_lines.append(f"  • {port.name} ({port.dtype})")
            if len(node.out_ports) > 3:
                info_lines.append(f"  ... (还有 {len(node.out_ports) - 3} 个)")

        return "\n".join(info_lines)

    def _get_port_info(port_id: str) -> str:
        """生成端口的详细信息文本"""
        # 在模型中查找端口
        for node in model.nodes.values():
            for port in node.in_ports + node.out_ports:
                if port.id == port_id:
                    info_lines = [
                        f"端口: {port.name}",
                        f"类型: {port.dtype}",
                        f"方向: {'输入' if port.kind == 'in' else '输出'}",
                        f"所属插件: {node.title}",
                    ]
                    return "\n".join(info_lines)
        return ""

    def _point_in_box(x, y, box):
        """检查点 (x, y) 是否在矩形框内"""
        x_min, x_max, y_min, y_max = box
        return x_min <= x <= x_max and y_min <= y <= y_max

    def on_hover(event):
        """鼠标悬停事件处理器"""
        if event.inaxes != ax:
            annot.set_visible(False)
            fig.canvas.draw_idle()
            return

        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return

        # 检查是否在节点上
        for node_id, box in node_bounds.items():
            if _point_in_box(x, y, box):
                info = _get_node_info(node_id)
                if info:
                    annot.xy = (x, y)
                    annot.set_text(info)
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
                    return

        # 检查是否在端口上
        for port_id, box in port_bounds.items():
            if _point_in_box(x, y, box):
                info = _get_port_info(port_id)
                if info:
                    annot.xy = (x, y)
                    annot.set_text(info)
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
                    return

        # 鼠标不在任何对象上
        if annot.get_visible():
            annot.set_visible(False)
            fig.canvas.draw_idle()

    # 注册事件处理器
    fig.canvas.mpl_connect("motion_notify_event", on_hover)

    # 点击事件：高亮依赖路径
    highlighted_items = {"nodes": set(), "edges": set()}  # 存储当前高亮的对象

    def _get_upstream_nodes(node_id: str, visited: set = None) -> set:
        """递归获取节点的所有上游依赖节点"""
        if visited is None:
            visited = set()
        if node_id in visited:
            return visited

        visited.add(node_id)

        # 查找所有输入到该节点的边
        for edge in model.edges:
            # 检查边是否连接到该节点的输入端口
            target_node_found = False
            for node in model.nodes.values():
                for port in node.in_ports:
                    if port.id == edge.target_port_id and node.key == node_id:
                        target_node_found = True
                        break
                if target_node_found:
                    break

            if target_node_found:
                # 找到输出该边的源节点
                for source_node in model.nodes.values():
                    for port in source_node.out_ports:
                        if port.id == edge.source_port_id:
                            _get_upstream_nodes(source_node.key, visited)
                            break

        return visited

    def on_click(event):
        """鼠标点击事件处理器"""
        if event.inaxes != ax or event.button != 1:  # 只处理左键点击
            return

        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return

        # 检查是否点击了节点
        clicked_node = None
        for node_id, box in node_bounds.items():
            if _point_in_box(x, y, box):
                clicked_node = node_id
                break

        if clicked_node:
            # 获取上游依赖节点
            upstream = _get_upstream_nodes(clicked_node)

            # 如果点击的是已经高亮的节点，则取消高亮
            if clicked_node in highlighted_items["nodes"]:
                highlighted_items["nodes"].clear()
                highlighted_items["edges"].clear()
                print(f"取消高亮节点: {clicked_node}")
            else:
                # 高亮新节点及其依赖
                highlighted_items["nodes"] = upstream
                print(f"\n点击节点: {clicked_node}")
                print(f"上游依赖节点 ({len(upstream)}):")
                for node_id in sorted(upstream):
                    node = model.nodes.get(node_id)
                    if node:
                        print(f"  • {node.title} ({node.key})")

                # 找到所有连接这些节点的边
                highlighted_items["edges"].clear()
                for edge in model.edges:
                    # 检查边的两端是否都在高亮节点集合中
                    source_in = False
                    target_in = False

                    for node_id in upstream:
                        node = model.nodes.get(node_id)
                        if node:
                            for port in node.out_ports:
                                if port.id == edge.source_port_id:
                                    source_in = True
                            for port in node.in_ports:
                                if port.id == edge.target_port_id:
                                    target_in = True

                    if source_in and target_in:
                        highlighted_items["edges"].add((edge.source_port_id, edge.target_port_id))

            # 重新绘制图形（需要重新调用 plot_lineage_labview 或更新现有对象）
            # 这里简单地打印信息，完整实现需要更新 patches 的样式
            fig.canvas.draw_idle()

    fig.canvas.mpl_connect("button_press_event", on_click)


# Preserve the historical implementation metadata exposed through the facade.
plot_lineage_labview.__name__ = "_plot_lineage_labview_impl"
plot_lineage_labview.__module__ = "waveform_analysis.visualization.lineage_visualizer"

__all__ = ["plot_lineage_labview"]
