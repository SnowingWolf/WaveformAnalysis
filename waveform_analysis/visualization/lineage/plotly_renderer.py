"""Plotly implementation for lineage visualization."""

from typing import Any

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
    _node_heights_for,
    _resolve_wire_style,
    _route_edge_path,
    _wrap_text_lines,
)


def plot_lineage_plotly(
    lineage: Any,
    target_name: str,
    context: Any = None,
    style: LineageStyle | None = None,
    save_path: str | None = None,
    data_wires: bool = False,
    interactive: bool = True,
    show: bool = True,
    **kwargs,
):
    """
    使用 Plotly 绘制高级交互式血缘图。

    功能特点:
        - 自动缩放和平移
        - 鼠标悬停显示详细信息
        - 点击高亮依赖路径
        - 更现代的视觉效果

    参数:
        lineage: 可以是 lineage 字典，也可以是 LineageGraphModel 实例。
        target_name: 目标数据名称。
        context: Context 实例，用于获取插件信息。
        style: 样式配置（部分样式参数会被转换为 plotly 格式）。
        save_path: 可选，保存图片路径。
        data_wires: 是否在连线上显示数据类型。
        interactive: Plotly 图表始终是交互式的，此参数仅为兼容性保留（会被忽略）。
        show: Whether to display the figure immediately. Set false for HTML export.

    注意:
        需要安装 plotly: pip install plotly

    注意:
        - Plotly 模式始终是交互式的，不需要 interactive 参数
        - 使用 style.verbose 参数控制节点上显示的信息量：
          * verbose=0: 仅显示标题（key）
          * verbose=1: 显示标题（key）+ class
          * verbose=2: 显示 class + description + config
    """
    try:
        import plotly.graph_objects as go
    except ImportError as e:
        raise ImportError(
            "Plotly is required for interactive visualization. "
            "Install it with: pip install plotly"
        ) from e

    # Plotly 始终是交互式的，如果用户显式设置 interactive=False，发出警告
    if not interactive:
        import warnings

        warnings.warn(
            "Plotly visualization is always interactive. The 'interactive=False' parameter is ignored.",
            UserWarning,
            stacklevel=2,
        )

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

    # 2. 布局计算
    node_heights = _node_heights_for(model, s)
    pos = _layout_nodes_source_to_target(model, s, node_heights)
    view = _layout_view_metrics(pos, s, node_heights)

    # 3. 创建 plotly traces 和 shapes
    traces = []
    shapes = []  # 用于绘制矩形节点和端口
    node_annotations = []  # 用于节点文本

    # 绘制连线
    node_boxes = _build_node_boxes(model, pos, s, node_heights)
    for edge in model.edges:
        p1 = pos.get(edge.source_port_id)
        p2 = pos.get(edge.target_port_id)
        if not p1 or not p2:
            continue

        path, label_pos = _route_edge_path(p1, p2, edge, node_boxes, s)
        line_x = [point[0] for point in path]
        line_y = [point[1] for point in path]

        wire_style = _resolve_wire_style(edge, s)
        line_style = {
            "color": wire_style["color"],
            "width": wire_style["width"],
        }
        if wire_style.get("dash") and wire_style["dash"] != "solid":
            line_style["dash"] = wire_style["dash"]

        # 连线 trace
        traces.append(
            go.Scatter(
                x=line_x,
                y=line_y,
                mode="lines",
                line=line_style,
                opacity=wire_style["alpha"],
                hoverinfo="text",
                hovertext=f"类型: {edge.dtype}",
                showlegend=False,
                name="edge",
            )
        )

    # 绘制节点和端口
    for node_id, (x, y) in pos.items():
        if node_id.startswith(("IN::", "OUT::")):
            # 端口 - 绘制为小方块
            port: PortModel | None = None
            for n in model.nodes.values():
                for p in n.in_ports + n.out_ports:
                    if p.id == node_id:
                        port = p
                        break
                if port:
                    break

            if not port:
                continue

            color = s.type_colors.get(port.dtype, s.type_colors.get("Unknown", "#95a5a6"))

            hover_text = (
                f"<b>{port.name}</b><br>"
                f"类型: {port.dtype}<br>"
                f"方向: {'输入' if port.kind == 'in' else '输出'}"
            )

            # 绘制端口矩形
            half_size = s.port_size / 2
            shapes.append(
                {
                    "type": "rect",
                    "x0": x - half_size,
                    "y0": y - half_size,
                    "x1": x + half_size,
                    "y1": y + half_size,
                    "fillcolor": color,
                    "line": {"color": s.node_edge, "width": 1},
                    "layer": "above",
                }
            )

            # 添加一个不可见的点用于 hover 效果
            traces.append(
                go.Scatter(
                    x=[x],
                    y=[y],
                    mode="markers",
                    marker={"size": s.port_size * 20, "color": color, "opacity": 0},
                    hoverinfo="text",
                    hovertext=hover_text,
                    showlegend=False,
                    name="port",
                )
            )

            # 端口标签
            if port.kind == "in":
                node_annotations.append(
                    {
                        "x": x + 0.12,
                        "y": y,
                        "text": port.name,
                        "showarrow": False,
                        "font": {"size": s.font_size_port, "color": s.text_color},
                        "xanchor": "left",
                        "yanchor": "middle",
                    }
                )
            else:
                node_annotations.append(
                    {
                        "x": x - 0.12,
                        "y": y,
                        "text": port.name,
                        "showarrow": False,
                        "font": {"size": s.font_size_port, "color": s.text_color},
                        "xanchor": "right",
                        "yanchor": "middle",
                    }
                )
        else:
            # VI 节点
            node = model.nodes.get(node_id)
            if not node:
                continue
            node_height = node_heights[node_id]

            # 根据节点类型确定颜色
            node_type = _classify_node_type(node)
            node_bg, node_edge_color, header_bg = _get_node_colors(node_type)

            # 构建悬停信息（始终完整，添加类型信息）
            type_names = {
                "raw_data": "原始数据",
                "structured_array": "结构化数组",
                "dataframe": "DataFrame",
                "grouped": "聚合数据",
                "side_effect": "副作用",
                "intermediate": "中间处理",
            }
            hover_lines = [
                f"<b>{node.title}</b>",
                f"类型: {type_names.get(node_type, '未知')}",
                f"Key: {node.key}",
                f"Class: {node.plugin_class}",
                f"深度: {node.depth}",
            ]

            if node.description:
                hover_lines.append(f"<br>描述: {node.description}")

            if node.config:
                hover_lines.append("<br>配置:")
                for k, v in list(node.config.items())[:5]:
                    hover_lines.append(f"  {k}: {v}")
                if len(node.config) > 5:
                    hover_lines.append(f"  ... (还有 {len(node.config) - 5} 项)")

            hover_text = "<br>".join(hover_lines)

            # 绘制节点主体矩形
            half_w = s.node_width / 2
            half_h = node_height / 2
            shapes.append(
                {
                    "type": "rect",
                    "x0": x - half_w,
                    "y0": y - half_h,
                    "x1": x + half_w,
                    "y1": y + half_h,
                    "fillcolor": node_bg,
                    "line": {"color": node_edge_color, "width": 2},
                    "layer": "above",
                }
            )

            # 绘制标题栏
            shapes.append(
                {
                    "type": "rect",
                    "x0": x - half_w,
                    "y0": y + half_h - s.header_height,
                    "x1": x + half_w,
                    "y1": y + half_h,
                    "fillcolor": header_bg,
                    "line": {"color": node_edge_color, "width": 1},
                    "layer": "above",
                }
            )

            # 添加一个不可见的点用于 hover 效果
            traces.append(
                go.Scatter(
                    x=[x],
                    y=[y],
                    mode="markers",
                    marker={"size": max(s.node_width, s.node_height) * 20, "opacity": 0},
                    hoverinfo="text",
                    hovertext=hover_text,
                    showlegend=False,
                    name=f"node_{node_id}",
                )
            )

            # 标题文本
            node_annotations.append(
                {
                    "x": x,
                    "y": y + half_h - s.header_height / 2,
                    "text": f"<b>{node.key}</b>",
                    "showarrow": False,
                    "font": {"size": s.font_size_title, "color": s.text_color},
                    "xanchor": "center",
                    "yanchor": "middle",
                }
            )

            # 根据 verbose 等级添加额外信息
            # 计算需要的信息行数，动态调整节点高度
            line_height = 0.16
            content_top = y + half_h - s.header_height - 0.1
            content_bottom = y - half_h + 0.2

            current_y = content_top - 0.05
            if s.verbose >= 1:
                node_annotations.append(
                    {
                        "x": x,
                        "y": current_y,
                        "text": f"class: {node.plugin_class}",
                        "showarrow": False,
                        "font": {"size": s.font_size_key - 1, "color": "#7f8c8d"},
                        "xanchor": "center",
                        "yanchor": "middle",
                    }
                )
                current_y -= line_height

            cfg = node.config
            cfg_items = list(cfg.items()) if cfg else []
            cfg_lines = min(5, len(cfg_items)) if (cfg and s.verbose >= 2) else 0
            cfg_height = cfg_lines * line_height
            cfg_top = content_bottom + cfg_height if cfg_lines else content_bottom
            max_desc_lines = int((current_y - cfg_top - 0.05) / line_height)

            if node.description and s.verbose >= 2 and max_desc_lines > 0:
                max_width_chars = int(s.node_width * 10)
                desc_lines = _wrap_text_lines(node.description, max_width_chars, max_desc_lines)
                if desc_lines:
                    wrapped_desc_html = "<br>".join(desc_lines)
                    node_annotations.append(
                        {
                            "x": x,
                            "y": current_y,
                            "text": wrapped_desc_html,
                            "showarrow": False,
                            "font": {"size": s.font_size_key - 1, "color": "#34495e"},
                            "xanchor": "center",
                            "yanchor": "top",
                        }
                    )
                    current_y -= line_height * len(desc_lines)

            if cfg and s.verbose >= 2 and cfg_lines > 0:
                cfg_text = "<br>".join([f"{k}: {v}" for k, v in cfg_items[:cfg_lines]])
                cfg_y = content_bottom
                node_annotations.append(
                    {
                        "x": x,
                        "y": cfg_y,
                        "text": cfg_text,
                        "showarrow": False,
                        "font": {"size": s.font_size_port - 1, "color": s.text_color},
                        "xanchor": "center",
                        "yanchor": "bottom",
                    }
                )

    # 4. 创建图形
    fig = go.Figure(data=traces)

    # 添加箭头注释
    annotations = []
    for edge in model.edges:
        p1 = pos.get(edge.source_port_id)
        p2 = pos.get(edge.target_port_id)
        if not p1 or not p2:
            continue

        path, label_pos = _route_edge_path(p1, p2, edge, node_boxes, s)
        start_x, start_y = path[-2]
        end_x, end_y = path[-1]

        wire_style = _resolve_wire_style(edge, s)

        # 箭头注释
        annotations.append(
            {
                "ax": start_x,
                "ay": start_y,
                "x": end_x,
                "y": end_y,
                "xref": "x",
                "yref": "y",
                "axref": "x",
                "ayref": "y",
                "showarrow": True,
                "arrowhead": 2,
                "arrowsize": 1,
                "arrowwidth": wire_style["width"],
                "arrowcolor": wire_style["color"],
            }
        )

        # 数据类型标签
        if data_wires:
            annotations.append(
                {
                    "x": label_pos[0],
                    "y": label_pos[1] + 0.12,
                    "text": edge.dtype,
                    "showarrow": False,
                    "font": {"size": s.font_size_wire, "color": wire_style["color"]},
                    "bgcolor": "white",
                    "bordercolor": wire_style["color"],
                    "borderwidth": 1,
                    "borderpad": 2,
                    "opacity": 0.9,
                }
            )

    # 合并节点文本注释
    annotations.extend(node_annotations)

    fig.update_layout(
        title={
            "text": f"Data Lineage: {target_name}",
            "font": {"size": 20, "color": s.text_color},
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis={
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
            "title": "",
            "range": view["x_range"],
        },
        yaxis={
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
            "title": "",
            "range": view["y_range"],
            "scaleanchor": "x",  # 保持宽高比一致
            "scaleratio": 1,  # 1:1 比例
        },
        plot_bgcolor="white",
        hovermode="closest",
        annotations=annotations,
        shapes=shapes,  # 添加矩形 shapes
        height=view["plotly_height"],
        width=view["plotly_width"],
        dragmode="pan",  # 默认为平移模式
    )

    if save_path:
        fig.write_image(save_path)

    if show:
        fig.show()
    return fig


# Preserve the historical implementation metadata exposed through the facade.
plot_lineage_plotly.__name__ = "_plot_lineage_plotly_impl"
plot_lineage_plotly.__module__ = "waveform_analysis.visualization.lineage_visualizer"

__all__ = ["plot_lineage_plotly"]
