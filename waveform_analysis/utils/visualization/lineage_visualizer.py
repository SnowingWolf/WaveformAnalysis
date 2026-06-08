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
from typing import Any, Dict, List, Optional

from matplotlib.patches import Circle, FancyArrowPatch, Rectangle
import matplotlib.pyplot as plt

from waveform_analysis.core.foundation.model import (
    LineageGraphModel,
    NodeModel,
    PortModel,
    build_lineage_graph,
)
from waveform_analysis.core.foundation.utils import LineageStyle, get_plugins_from_context


def _classify_node_type(node: NodeModel) -> str:
    """
    分类节点类型，用于颜色高亮。

    返回值：
        - 'raw_data': 原始数据/输入节点（蓝色）
        - 'structured_array': 结构化数组节点（绿色）
        - 'dataframe': DataFrame/表格数据节点（橙色）
        - 'grouped': 聚合/分组数据节点（紫色）
        - 'side_effect': 副作用/导出节点（粉红色）
        - 'intermediate': 中间处理节点（默认白色）
    """
    plugin_class_lower = node.plugin_class.lower()
    node_key_lower = node.key.lower()

    # 1. 原始数据节点（文件读取、数据加载）
    if any(keyword in plugin_class_lower for keyword in ["rawfiles", "loader", "reader"]):
        return "raw_data"

    # 2. DataFrame 节点
    if "dataframe" in plugin_class_lower or "dataframe" in node_key_lower or node.key == "df":
        return "dataframe"
    for port in node.out_ports:
        if "dataframe" in port.dtype.lower():
            return "dataframe"

    # 3. 聚合/分组节点
    if any(keyword in plugin_class_lower for keyword in ["group", "pair", "aggregate", "merge"]):
        return "grouped"
    if any(keyword in node_key_lower for keyword in ["grouped", "paired", "merged"]):
        return "grouped"

    # 4. 副作用节点（导出、保存）
    if any(keyword in plugin_class_lower for keyword in ["export", "save", "write"]):
        return "side_effect"

    # 5. 结构化数组节点（有多个字段的 dtype）
    for port in node.out_ports:
        dtype_str = port.dtype.lower()
        # 检查是否包含多个字段
        if ("[(" in dtype_str or ", " in dtype_str) and "list" not in dtype_str:
            return "structured_array"

    # 6. 默认为中间处理节点
    return "intermediate"


def _get_node_colors(node_type: str) -> tuple:
    """
    根据节点类型返回颜色配置。

    返回: (background_color, border_color, header_color)
    """
    color_scheme = {
        "raw_data": ("#e3f2fd", "#1976d2", "#bbdefb"),  # 蓝色系 - 数据源
        "structured_array": ("#e8f5e9", "#388e3c", "#c8e6c9"),  # 绿色系 - 结构化数据
        "dataframe": ("#fff3e0", "#f57c00", "#ffe0b2"),  # 橙色系 - 表格数据
        "grouped": ("#f3e5f5", "#7b1fa2", "#e1bee7"),  # 紫色系 - 聚合数据
        "side_effect": ("#fce4ec", "#c2185b", "#f8bbd0"),  # 粉红色系 - 输出操作
        "intermediate": ("#fafafa", "#424242", "#e0e0e0"),  # 灰色系 - 中间处理
    }
    return color_scheme.get(node_type, color_scheme["intermediate"])


def _build_node_boxes(
    model: LineageGraphModel,
    pos: dict,
    style: LineageStyle,
) -> List[dict]:
    """Create node bounding boxes used for simple wire obstacle avoidance."""
    margin = max(0.2, style.port_size * 2)
    boxes = []
    for node_id in model.nodes:
        if node_id not in pos:
            continue
        x, y = pos[node_id]
        half_w = style.node_width / 2 + margin
        half_h = style.node_height / 2 + margin
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


def _path_intersects_boxes(path: List[tuple], boxes: List[dict], skip_ids: set) -> bool:
    for i in range(len(path) - 1):
        p1 = path[i]
        p2 = path[i + 1]
        for box in boxes:
            if box["id"] in skip_ids:
                continue
            if _segment_intersects_box(p1, p2, box):
                return True
    return False


def _layer_positions(nodes_by_depth: Dict[int, List[str]], y_gap: float) -> Dict[str, float]:
    node_y = {}
    for _depth, layer in nodes_by_depth.items():
        for idx, node_id in enumerate(layer):
            y = (idx - (len(layer) - 1) / 2.0) * y_gap
            node_y[node_id] = y
    return node_y


def _layout_nodes_source_to_target(
    model: LineageGraphModel,
    style: LineageStyle,
) -> dict:
    """Place lineage sources on the left and downstream targets on the right."""
    pos = {}
    nodes_by_depth: Dict[int, List[str]] = {}
    for node_id, node in model.nodes.items():
        nodes_by_depth.setdefault(node.depth, []).append(node_id)

    for depth in nodes_by_depth:
        nodes_by_depth[depth] = sorted(nodes_by_depth[depth])

    if getattr(style, "layout_reorder", True):
        nodes_by_depth = _reorder_layers(
            nodes_by_depth,
            model.edges,
            style.y_gap,
            getattr(style, "layout_iterations", 3),
        )

    for d in sorted(nodes_by_depth.keys()):
        layer = nodes_by_depth[d]
        x = d * style.x_gap
        for i, node_id in enumerate(layer):
            y = (i - (len(layer) - 1) / 2.0) * style.y_gap
            pos[node_id] = (x, y)

    _set_port_positions(model, pos, style)
    return pos


def _build_adjacency(edges: List[Any]) -> tuple:
    upstream_map: Dict[str, List[str]] = {}
    downstream_map: Dict[str, List[str]] = {}
    for edge in edges:
        downstream_map.setdefault(edge.source_node_id, []).append(edge.target_node_id)
        upstream_map.setdefault(edge.target_node_id, []).append(edge.source_node_id)
    return upstream_map, downstream_map


def _order_layer(
    layer: List[str],
    neighbors: Dict[str, List[str]],
    node_y: Dict[str, float],
) -> List[str]:
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
    nodes_by_depth: Dict[int, List[str]],
    edges: List[Any],
    y_gap: float,
    iterations: int,
) -> Dict[int, List[str]]:
    layers = {depth: list(layer) for depth, layer in nodes_by_depth.items()}
    if not layers:
        return layers

    upstream_map, downstream_map = _build_adjacency(edges)
    max_depth = max(layers.keys())
    iterations = max(0, int(iterations))

    for _ in range(iterations):
        node_y = _layer_positions(layers, y_gap)
        for depth in range(1, max_depth + 1):
            layers[depth] = _order_layer(layers[depth], downstream_map, node_y)

        node_y = _layer_positions(layers, y_gap)
        for depth in range(max_depth - 1, 0, -1):
            layers[depth] = _order_layer(layers[depth], upstream_map, node_y)

    return layers


def _order_ports(
    node: NodeModel,
    ports: List[PortModel],
    edges: List[Any],
    pos: dict,
    style: LineageStyle,
    direction: str,
) -> List[PortModel]:
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
) -> None:
    for node_id, node in model.nodes.items():
        if node_id not in pos:
            continue
        x, y = pos[node_id]

        in_ports = _order_ports(node, node.in_ports, model.edges, pos, style, "in")
        out_ports = _order_ports(node, node.out_ports, model.edges, pos, style, "out")

        for k, port in enumerate(in_ports):
            if len(in_ports) > 1:
                dy = (k - (len(in_ports) - 1) / 2.0) * 0.4
            else:
                dy = 0
            pos[port.id] = (x - style.node_width / 2, y + dy)

        for k, port in enumerate(out_ports):
            if len(out_ports) > 1:
                dy = (k - (len(out_ports) - 1) / 2.0) * 0.4
            else:
                dy = 0
            pos[port.id] = (x + style.node_width / 2, y + dy)


def _route_edge_path(
    p1: tuple,
    p2: tuple,
    edge: Any,
    boxes: List[dict],
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
    stub = max(0.4, style.port_size * 4)
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
        clearance = max(style.port_size * 4, style.node_height * 0.2, 0.4)
        candidates.extend([y_max + clearance, y_min - clearance])

    y_mid = (y1 + y2) / 2.0
    lane_step = max(style.y_gap * 0.6, 0.8)
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


def _classify_edge_category(dtype: str) -> str:
    if not dtype:
        return "unknown"

    dtype_lower = dtype.lower()
    if "dataframe" in dtype_lower:
        return "dataframe"
    if "list" in dtype_lower and "ndarray" in dtype_lower:
        return "list_array"
    if "[(" in dtype_lower or "structured" in dtype_lower:
        return "structured"
    if "ndarray" in dtype_lower:
        return "array"
    return "unknown"


def _resolve_wire_style(edge: Any, style: LineageStyle) -> dict:
    dtype = edge.dtype or ""
    color = style.type_colors.get(dtype, style.type_colors.get("Unknown", "#95a5a6"))
    width = style.wire_linewidth
    alpha = style.wire_alpha
    dash = "solid"

    category = _classify_edge_category(dtype)
    category_style = getattr(style, "wire_style_by_category", {}).get(category, {})
    color = category_style.get("color", color)
    width = category_style.get("width", width)
    alpha = category_style.get("alpha", alpha)
    dash = category_style.get("dash", dash)

    match_text = f"{edge.source_node_id} {edge.target_node_id} {dtype}".lower()
    for match, overrides in getattr(style, "wire_style_overrides", {}).items():
        if match.lower() in match_text:
            color = overrides.get("color", color)
            width = overrides.get("width", width)
            alpha = overrides.get("alpha", alpha)
            dash = overrides.get("dash", dash)

    return {"color": color, "width": width, "alpha": alpha, "dash": dash}


def _mpl_dash(dash: Optional[str]) -> str:
    if not dash or dash == "solid":
        return "solid"
    mapping = {"dash": "dashed", "dot": "dotted", "dashdot": "dashdot"}
    return mapping.get(dash, dash)


def _wrap_text_lines(text: str, max_width: int, max_lines: Optional[int] = None) -> List[str]:
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


def _auto_adjust_layout(model: LineageGraphModel, style: LineageStyle) -> None:
    if not getattr(style, "auto_fit_text", True):
        return

    max_width_chars = int(style.node_width * 10)
    if not model.nodes:
        return

    required_heights = [
        _estimate_node_height(node, style, max_width_chars) for node in model.nodes.values()
    ]
    max_required = max(required_heights) if required_heights else style.node_height
    if max_required > style.node_height:
        style.node_height = max_required

    min_gap = style.node_height * 1.25
    if style.y_gap < min_gap:
        style.y_gap = min_gap


def plot_lineage_labview(
    lineage: Any,
    target_name: str,
    context: Any = None,
    style: Optional[LineageStyle] = None,
    save_path: Optional[str] = None,
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

    _auto_adjust_layout(model, s)

    # 2. 布局计算 (基于模型)
    pos = _layout_nodes_source_to_target(model, s)
    max_d = max((node.depth for node in model.nodes.values()), default=0)

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
    fig, ax = plt.subplots(figsize=(max(12, max_d * 3), 6))
    node_boxes = _build_node_boxes(model, pos, s)

    def draw_wire(path: List[tuple], wire_style: dict) -> None:
        # 提高连线的zorder，确保在节点之上（节点zorder=3-5）
        line_x = [point[0] for point in path]
        line_y = [point[1] for point in path]
        linestyle = _mpl_dash(wire_style.get("dash"))
        ax.plot(
            line_x,
            line_y,
            color=wire_style["color"],
            lw=wire_style["width"],
            alpha=wire_style["alpha"],
            zorder=10,
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
                zorder=11,
            )
        )

    # 先绘制节点（zorder=3-5），后绘制连线（zorder=10-11），这样连线在节点上方
    # 绘制节点
    for node_id, (x, y) in pos.items():
        if node_id.startswith("IN::") or node_id.startswith("OUT::"):
            # 绘制端口
            # 我们需要找到对应的 PortModel
            port: Optional[PortModel] = None
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
                (x - s.node_width / 2, y - s.node_height / 2),
                s.node_width,
                s.node_height,
                fc=node_bg,
                ec=node_edge_color,
                lw=node_edge_width,
                zorder=3,
            )
        )
        # 标题栏
        ax.add_patch(
            Rectangle(
                (x - s.node_width / 2, y + s.node_height / 2 - s.header_height),
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
            y + s.node_height / 2 - s.header_height / 2,
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
        content_top = y + s.node_height / 2 - s.header_height - 0.1
        content_bottom = y - s.node_height / 2 + 0.2
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
            badge_y = y + s.node_height / 2 - 0.15
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

    # 绘制连线（在节点之后绘制，zorder更高，确保在节点之上）
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
                    bbox={"fc": "white", "ec": "none", "alpha": 0.7, "boxstyle": "round,pad=0.1"},
                    zorder=12,
                )

    ax.set_title(f"Data Lineage: {target_name}", fontsize=14, fontweight="bold", pad=20)
    ax.axis("off")
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight", pad_inches=0.2)

    # 交互式功能
    if interactive:
        _add_interactive_features(fig, ax, model, pos, s)

    plt.show()


def _add_interactive_features(fig, ax, model: LineageGraphModel, pos: dict, style: LineageStyle):
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
            half_h = style.node_height / 2
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


def plot_lineage_plotly(
    lineage: Any,
    target_name: str,
    context: Any = None,
    style: Optional[LineageStyle] = None,
    save_path: Optional[str] = None,
    data_wires: bool = False,
    interactive: bool = True,
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

    _auto_adjust_layout(model, s)

    # 2. 布局计算
    pos = _layout_nodes_source_to_target(model, s)

    # 3. 创建 plotly traces 和 shapes
    traces = []
    shapes = []  # 用于绘制矩形节点和端口
    node_annotations = []  # 用于节点文本

    # 绘制连线
    node_boxes = _build_node_boxes(model, pos, s)
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
            port: Optional[PortModel] = None
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
            half_h = s.node_height / 2
            shapes.append(
                {
                    "type": "rect",
                    "x0": x - half_w,
                    "y0": y - half_h,
                    "x1": x + half_w,
                    "y1": y + half_h,
                    "fillcolor": node_bg,
                    "line": {"color": node_edge_color, "width": 2},
                    "layer": "below",
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
                    "layer": "below",
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

    # 计算坐标范围，添加边距
    all_x = [p[0] for p in pos.values()]
    all_y = [p[1] for p in pos.values()]
    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)

    # 添加边距（考虑节点大小）
    x_margin = max(s.node_width, 2.0)
    y_margin = max(s.node_height, 2.0)
    x_range = [x_min - x_margin, x_max + x_margin]
    y_range = [y_min - y_margin, y_max + y_margin]

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
            "range": x_range,  # 明确设置坐标范围
        },
        yaxis={
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
            "title": "",
            "range": y_range,  # 明确设置坐标范围
            "scaleanchor": "x",  # 保持宽高比一致
            "scaleratio": 1,  # 1:1 比例
        },
        plot_bgcolor="white",
        hovermode="closest",
        annotations=annotations,
        shapes=shapes,  # 添加矩形 shapes
        height=600,
        width=max(1200, max_d * 300),
        dragmode="pan",  # 默认为平移模式
    )

    if save_path:
        fig.write_image(save_path)

    fig.show()
