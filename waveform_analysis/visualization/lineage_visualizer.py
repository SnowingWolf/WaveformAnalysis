"""
血缘图可视化模块 - LabVIEW 风格插件依赖图。

本模块提供两种高级可视化方式，支持智能颜色高亮和完整交互功能。

## 1. Matplotlib 静态/交互式可视化 (`plot_lineage_labview`)

### 基础用法
```python
from waveform_analysis.utils.visualization import plot_lineage_labview

# 静态图
plot_lineage_labview(lineage_dict, "target_data", context=ctx)

# 交互式图（鼠标悬停显示详情、点击显示依赖）
plot_lineage_labview(lineage_dict, "target_data", context=ctx, interactive=True)

# 显示详细信息
plot_lineage_labview(lineage_dict, "target_data", context=ctx, verbose=2, interactive=True)
```

### 特性
- ✅ 支持静态和交互式模式
- ✅ 智能颜色高亮（自动识别节点类型）
- ✅ 鼠标悬停显示详细信息
- ✅ 点击节点显示上游依赖
- ✅ 支持依赖分析高亮（关键路径、瓶颈节点、并行组）

## 2. Plotly 高级交互式可视化 (`plot_lineage_plotly`)

### 基础用法
```python
from waveform_analysis.utils.visualization import plot_lineage_plotly

# Plotly 高级交互式图（始终支持缩放、平移、悬停）
plot_lineage_plotly(lineage_dict, "target_data", context=ctx, verbose=2)

# 通过 Context 调用（推荐）
ctx.plot_lineage("df_paired", kind="plotly", verbose=2)
```

### 特性
- ✅ **真实矩形绘制**：使用 shapes API 绘制节点，尺寸精确
- ✅ **完整交互性**：缩放、平移、框选、悬停提示
- ✅ **坐标同步修复**：拖拽时光标和节点位置完全同步
- ✅ **智能颜色高亮**：自动识别节点类型并应用配色
- ✅ **端口可见**：显示彩色输入/输出端口
- ✅ **类型标注**：悬停提示包含节点类型信息

## 智能颜色高亮系统

系统自动根据节点类型应用以下颜色方案（两种模式均支持）：

| 节点类型     | 颜色      | 识别规则                                    |
|-------------|----------|-------------------------------------------|
| 原始数据     | 🔵 蓝色系 | RawFiles, Loader, Reader                  |
| 结构化数组   | 🟢 绿色系 | 多字段 dtype（如 `[('time', '<f8'), ...]`）|
| DataFrame   | 🟠 橙色系 | DataFrame, df 关键词                       |
| 聚合数据     | 🟣 紫色系 | Group, Pair, Aggregate, Merge             |
| 副作用       | 🌸 粉红色系| Export, Save, Write                       |
| 中间处理     | ⚪ 灰色系 | 其他所有节点                               |

颜色高亮无需额外配置，框架自动识别并应用。

## Verbose 等级

- `verbose=0`: 仅显示插件标题
- `verbose=1`: 显示标题 + key
- `verbose=2`: 显示标题 + key + class（推荐）
- `verbose>=3`: 同 verbose=2

## 自定义样式

```python
from waveform_analysis.core.foundation.utils import LineageStyle

style = LineageStyle(
    node_width=4.0,
    node_height=2.0,
    x_gap=6.0,
    y_gap=3.0,
    verbose=2  # 显示详细信息
)

plot_lineage_labview(
    lineage_dict,
    "target_data",
    context=ctx,
    style=style,
    interactive=True
)
```

## 依赖分析集成

支持高亮关键路径、瓶颈节点和并行组（需要 DependencyAnalysisResult）：

```python
from waveform_analysis.core.dependency_analysis import analyze_dependencies

result = analyze_dependencies(ctx, "df_paired")

plot_lineage_labview(
    lineage_dict,
    "df_paired",
    context=ctx,
    analysis_result=result,
    highlight_critical_path=True,
    highlight_bottlenecks=True,
    highlight_parallel_groups=True
)
```

## 技术实现

### LabVIEW 模式
- 使用 Matplotlib Patches（Rectangle, FancyArrowPatch）绘制
- 交互功能基于 matplotlib 事件系统
- 适合静态导出和简单交互

### Plotly 模式
- 使用 plotly shapes API 绘制矩形节点和端口
- 使用 annotations 添加文本和箭头
- 使用隐藏的 scatter traces 实现 hover 效果
- 明确设置坐标范围和 1:1 比例保证拖拽同步
- 适合复杂图形的深度探索

## 注意事项

1. **Interactive 参数**：
   - LabVIEW 模式：`interactive=True` 启用交互功能
   - Plotly 模式：始终交互式，`interactive` 参数被忽略

2. **依赖**：
   - LabVIEW 模式：需要 matplotlib（标准依赖）
   - Plotly 模式：需要 `pip install plotly`

3. **性能**：
   - 节点数量 < 20：两种模式性能相当
   - 节点数量 > 20：Plotly 模式交互性更好
"""

import textwrap
from typing import Any

from waveform_analysis.core.foundation.model import (
    LineageGraphModel,
    NodeModel,
    PortModel,
    build_lineage_graph,
)
from waveform_analysis.core.foundation.utils import LineageStyle, get_plugins_from_context
from waveform_analysis.visualization.lineage.model import (
    classify_node_type as _classify_node_type,
)
from waveform_analysis.visualization.lineage.model import get_node_colors as _get_node_colors
from waveform_analysis.visualization.lineage.routing import (
    classify_edge_category as _classify_edge_category,
)
from waveform_analysis.visualization.lineage.routing import mpl_dash as _mpl_dash
from waveform_analysis.visualization.lineage.routing import (
    resolve_wire_style as _resolve_wire_style,
)


def _build_node_boxes(
    model: LineageGraphModel,
    pos: dict,
    style: LineageStyle,
    node_heights: dict[str, float],
) -> list[dict]:
    """Create node bounding boxes used for simple wire obstacle avoidance."""
    margin = max(0.2, style.port_size * 2)
    boxes = []
    for node_id in model.nodes:
        if node_id not in pos:
            continue
        x, y = pos[node_id]
        half_w = style.node_width / 2 + margin
        half_h = node_heights[node_id] / 2 + margin
        boxes.append(
            {
                "id": node_id,
                "x_min": x - half_w,
                "x_max": x + half_w,
                "y_min": y - half_h,
                "y_max": y + half_h,
            }
        )
    return boxes


def _segment_intersects_box(p1: tuple, p2: tuple, box: dict) -> bool:
    x1, y1 = p1
    x2, y2 = p2
    if abs(y1 - y2) < 1e-9:
        y = y1
        x_min, x_max = sorted([x1, x2])
        return box["y_min"] <= y <= box["y_max"] and x_min <= box["x_max"] and x_max >= box["x_min"]
    if abs(x1 - x2) < 1e-9:
        x = x1
        y_min, y_max = sorted([y1, y2])
        return box["x_min"] <= x <= box["x_max"] and y_min <= box["y_max"] and y_max >= box["y_min"]
    return False


def _path_intersects_boxes(path: list[tuple], boxes: list[dict], skip_ids: set) -> bool:
    for i in range(len(path) - 1):
        p1 = path[i]
        p2 = path[i + 1]
        for box in boxes:
            if box["id"] in skip_ids:
                continue
            if _segment_intersects_box(p1, p2, box):
                return True
    return False


def _layer_positions(
    nodes_by_depth: dict[int, list[str]],
    node_heights: dict[str, float],
    style: LineageStyle,
) -> dict[str, float]:
    node_y = {}
    for _depth, layer in nodes_by_depth.items():
        if not layer:
            continue

        centers = [0.0]
        for previous, current in zip(layer, layer[1:], strict=False):
            preserved_clearance = max(style.y_gap - style.node_height, 0.5)
            distance = node_heights[previous] / 2 + node_heights[current] / 2 + preserved_clearance
            centers.append(centers[-1] + distance)

        midpoint = (centers[0] + centers[-1]) / 2
        for node_id, y in zip(layer, centers, strict=False):
            node_y[node_id] = y - midpoint
    return node_y


def _layout_nodes_source_to_target(
    model: LineageGraphModel,
    style: LineageStyle,
    node_heights: dict[str, float] | None = None,
) -> dict:
    """Place lineage sources on the left and downstream targets on the right."""
    pos = {}
    node_heights = node_heights or _node_heights_for(model, style)
    nodes_by_depth: dict[int, list[str]] = {}
    for node_id, node in model.nodes.items():
        nodes_by_depth.setdefault(node.depth, []).append(node_id)

    for depth in nodes_by_depth:
        nodes_by_depth[depth] = sorted(nodes_by_depth[depth])

    if getattr(style, "layout_reorder", True):
        nodes_by_depth = _reorder_layers(
            nodes_by_depth,
            model.edges,
            node_heights,
            style,
            getattr(style, "layout_iterations", 3),
        )

    for d in sorted(nodes_by_depth.keys()):
        layer = nodes_by_depth[d]
        x = d * style.x_gap
        layer_y = _layer_positions({d: layer}, node_heights, style)
        for node_id in layer:
            y = layer_y[node_id]
            pos[node_id] = (x, y)

    _set_port_positions(model, pos, style, node_heights)
    return pos


def _layout_view_metrics(pos: dict, style: LineageStyle, node_heights: dict[str, float]) -> dict:
    """Compute visible ranges and canvas sizes from actual layout coordinates."""
    if not pos:
        return {
            "x_range": [-1.0, 1.0],
            "y_range": [-1.0, 1.0],
            "mpl_figsize": (12.0, 7.0),
            "plotly_width": 1200,
            "plotly_height": 700,
        }

    all_x = [point[0] for point in pos.values()]
    all_y = [
        point[1] + node_heights.get(node_id, 0.0) / 2
        for node_id, point in pos.items()
        if node_id in node_heights
    ] + [
        point[1] - node_heights.get(node_id, 0.0) / 2
        for node_id, point in pos.items()
        if node_id in node_heights
    ]
    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)

    x_margin = max(style.node_width * 0.9, 2.0)
    y_margin = max(style.node_height * 0.9, 2.0)
    x_range = [x_min - x_margin, x_max + x_margin]
    y_range = [y_min - y_margin, y_max + y_margin]
    x_span = max(x_range[1] - x_range[0], 1.0)
    y_span = max(y_range[1] - y_range[0], 1.0)

    return {
        "x_range": x_range,
        "y_range": y_range,
        "mpl_figsize": (min(32.0, max(12.0, x_span * 0.65)), min(24.0, max(7.0, y_span * 0.8))),
        "plotly_width": int(min(3200, max(1200, x_span * 95))),
        "plotly_height": int(min(2400, max(700, y_span * 120))),
    }


def _build_adjacency(edges: list[Any]) -> tuple:
    upstream_map: dict[str, list[str]] = {}
    downstream_map: dict[str, list[str]] = {}
    for edge in edges:
        downstream_map.setdefault(edge.source_node_id, []).append(edge.target_node_id)
        upstream_map.setdefault(edge.target_node_id, []).append(edge.source_node_id)
    return upstream_map, downstream_map


def _order_layer(
    layer: list[str],
    neighbors: dict[str, list[str]],
    node_y: dict[str, float],
) -> list[str]:
    if len(layer) <= 1:
        return layer

    def sort_key(node_id: str, fallback: int) -> tuple:
        y_vals = [node_y[n] for n in neighbors.get(node_id, []) if n in node_y]
        avg_y = sum(y_vals) / len(y_vals) if y_vals else node_y.get(node_id, fallback)
        return (avg_y, fallback)

    ordered = []
    for idx, node_id in enumerate(layer):
        ordered.append((sort_key(node_id, idx), node_id))
    ordered.sort(key=lambda item: item[0])
    return [node_id for _, node_id in ordered]


def _reorder_layers(
    nodes_by_depth: dict[int, list[str]],
    edges: list[Any],
    node_heights: dict[str, float],
    style: LineageStyle,
    iterations: int,
) -> dict[int, list[str]]:
    layers = {depth: list(layer) for depth, layer in nodes_by_depth.items()}
    if not layers:
        return layers

    upstream_map, downstream_map = _build_adjacency(edges)
    max_depth = max(layers.keys())
    iterations = max(0, int(iterations))

    for _ in range(iterations):
        node_y = _layer_positions(layers, node_heights, style)
        for depth in range(1, max_depth + 1):
            layers[depth] = _order_layer(layers[depth], upstream_map, node_y)

        node_y = _layer_positions(layers, node_heights, style)
        for depth in range(max_depth - 1, -1, -1):
            layers[depth] = _order_layer(layers[depth], downstream_map, node_y)

    return layers


def _order_ports(
    node: NodeModel,
    ports: list[PortModel],
    edges: list[Any],
    pos: dict,
    style: LineageStyle,
    direction: str,
) -> list[PortModel]:
    if len(ports) <= 1:
        return ports

    groups = getattr(style, "port_groups", {}).get(node.key, {})
    direction_groups = groups.get(direction, [])
    default_group = len(direction_groups) // 2 if direction_groups else 0
    group_index = {}
    for idx, group in enumerate(direction_groups):
        for name in group:
            group_index[name] = idx

    port_to_ys = {port.id: [] for port in ports}
    for edge in edges:
        if direction == "in" and edge.target_port_id in port_to_ys:
            src_pos = pos.get(edge.source_node_id)
            if src_pos:
                port_to_ys[edge.target_port_id].append(src_pos[1])
        elif direction == "out" and edge.source_port_id in port_to_ys:
            tgt_pos = pos.get(edge.target_node_id)
            if tgt_pos:
                port_to_ys[edge.source_port_id].append(tgt_pos[1])

    def sort_key(port: PortModel) -> tuple:
        ys = port_to_ys.get(port.id, [])
        avg_y = sum(ys) / len(ys) if ys else 0.0
        group = group_index.get(port.name, default_group)
        if direction_groups:
            return (group, avg_y, port.index)
        return (avg_y, port.index)

    return sorted(ports, key=sort_key)


def _set_port_positions(
    model: LineageGraphModel,
    pos: dict,
    style: LineageStyle,
    node_heights: dict[str, float],
) -> None:
    for node_id, node in model.nodes.items():
        if node_id not in pos:
            continue
        x, y = pos[node_id]

        in_ports = _order_ports(node, node.in_ports, model.edges, pos, style, "in")
        out_ports = _order_ports(node, node.out_ports, model.edges, pos, style, "out")

        for k, port in enumerate(in_ports):
            dy = _port_offset(k, len(in_ports), node_heights[node_id], style)
            pos[port.id] = (x - style.node_width / 2, y + dy)

        for k, port in enumerate(out_ports):
            dy = _port_offset(k, len(out_ports), node_heights[node_id], style)
            pos[port.id] = (x + style.node_width / 2, y + dy)


def _route_edge_path(
    p1: tuple,
    p2: tuple,
    edge: Any,
    boxes: list[dict],
    style: LineageStyle,
) -> tuple:
    """Return a Manhattan path and label position that avoids node boxes when possible."""
    x1, y1 = p1
    x2, y2 = p2
    mx = (x1 + x2) / 2.0
    skip_ids = {edge.source_node_id, edge.target_node_id}

    default_path = [(x1, y1), (mx, y1), (mx, y2), (x2, y2)]
    if not _path_intersects_boxes(default_path, boxes, skip_ids):
        label_pos = (mx, (y1 + y2) / 2.0)
        return default_path, label_pos

    direction = 1 if x2 >= x1 else -1
    stub = max(0.8, style.port_size * 6)
    x1_stub = x1 + direction * stub
    x2_stub = x2 - direction * stub

    x_min = min(x1_stub, x2_stub)
    x_max = max(x1_stub, x2_stub)
    corridor_boxes = []
    for box in boxes:
        if box["id"] in skip_ids:
            continue
        if box["x_max"] < x_min or box["x_min"] > x_max:
            continue
        corridor_boxes.append(box)

    candidates = []
    if corridor_boxes:
        y_min = min(box["y_min"] for box in corridor_boxes)
        y_max = max(box["y_max"] for box in corridor_boxes)
        clearance = max(style.port_size * 6, style.node_height * 0.45, 0.8)
        candidates.extend([y_max + clearance, y_min - clearance])

    y_mid = (y1 + y2) / 2.0
    lane_step = max(style.y_gap * 0.9, 1.2)
    candidates = [y_mid] + candidates
    for i in range(1, 4):
        candidates.append(y_mid + i * lane_step)
        candidates.append(y_mid - i * lane_step)

    seen = set()
    for y_detour in candidates:
        if y_detour in seen:
            continue
        seen.add(y_detour)
        path = [
            (x1, y1),
            (x1_stub, y1),
            (x1_stub, y_detour),
            (x2_stub, y_detour),
            (x2_stub, y2),
            (x2, y2),
        ]
        if not _path_intersects_boxes(path, boxes, skip_ids):
            label_pos = ((x1_stub + x2_stub) / 2.0, y_detour)
            return path, label_pos

    label_pos = (mx, (y1 + y2) / 2.0)
    return default_path, label_pos


def _wrap_text_lines(text: str, max_width: int, max_lines: int | None = None) -> list[str]:
    lines = textwrap.wrap(text, width=max_width, break_long_words=False)
    if max_lines is None or max_lines <= 0 or len(lines) <= max_lines:
        return lines
    lines = lines[:max_lines]
    if lines:
        lines[-1] = lines[-1].rstrip(".") + "..."
    return lines


def _estimate_node_height(node: NodeModel, style: LineageStyle, max_width_chars: int) -> float:
    line_height = 0.16
    padding_top = 0.1
    padding_bottom = 0.2
    gap = 0.0

    class_lines = 1 if style.verbose >= 1 else 0
    desc_lines = 0
    cfg_lines = 0

    if style.verbose >= 2 and node.description:
        desc_lines = len(_wrap_text_lines(node.description, max_width_chars))
    if style.verbose >= 2 and node.config:
        cfg_lines = min(5, len(node.config))

    if class_lines and desc_lines:
        gap += 0.05
    if desc_lines and cfg_lines:
        gap += 0.05

    content_height = (class_lines + desc_lines + cfg_lines) * line_height + gap
    return style.header_height + padding_top + padding_bottom + content_height


def _port_offset(index: int, count: int, node_height: float, style: LineageStyle) -> float:
    """Keep ports evenly spaced inside the usable vertical span of a node."""
    if count <= 1:
        return 0.0

    usable_half_height = max(node_height / 2 - style.port_size * 1.5, 0.0)
    return -usable_half_height + 2 * usable_half_height * index / (count - 1)


def _node_heights_for(model: LineageGraphModel, style: LineageStyle) -> dict[str, float]:
    """Return the smallest readable height for each node without mutating its style."""
    max_width_chars = max(1, int(style.node_width * 10))
    heights = {}
    for node_id, node in model.nodes.items():
        text_height = (
            _estimate_node_height(node, style, max_width_chars)
            if getattr(style, "auto_fit_text", True)
            else style.node_height
        )
        port_count = max(len(node.in_ports), len(node.out_ports), 1)
        port_height = (port_count - 1) * style.port_size * 3 + style.port_size * 3
        heights[node_id] = max(style.node_height, text_height, port_height)
    return heights


from waveform_analysis.visualization.lineage.layout import (  # noqa: E402
    _layout_nodes_source_to_target,
    _layout_view_metrics,
    _node_heights_for,
    _set_port_positions,
    _wrap_text_lines,
)

__all__ = ["plot_lineage_labview", "plot_lineage_plotly"]  # noqa: F822


def __getattr__(name: str):
    if name == "plot_lineage_labview":
        from waveform_analysis.visualization.lineage.matplotlib_renderer import (
            plot_lineage_labview,
        )

        globals()[name] = plot_lineage_labview
        return plot_lineage_labview
    if name == "plot_lineage_plotly":
        from waveform_analysis.visualization.lineage.plotly_renderer import (
            plot_lineage_plotly,
        )

        globals()[name] = plot_lineage_plotly
        return plot_lineage_plotly
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(globals()) | set(__all__))
