"""Source-to-target lineage layout and node sizing."""

from __future__ import annotations

import textwrap
from typing import Any

from waveform_analysis.core.foundation.model import LineageGraphModel, NodeModel, PortModel
from waveform_analysis.core.foundation.utils import LineageStyle


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
    gap = 0.0
    class_lines = 1 if style.verbose >= 1 else 0
    desc_lines = (
        len(_wrap_text_lines(node.description, max_width_chars))
        if style.verbose >= 2 and node.description
        else 0
    )
    cfg_lines = min(5, len(node.config)) if style.verbose >= 2 and node.config else 0
    if class_lines and desc_lines:
        gap += 0.05
    if desc_lines and cfg_lines:
        gap += 0.05
    return style.header_height + 0.3 + (class_lines + desc_lines + cfg_lines) * line_height + gap


def _port_offset(index: int, count: int, node_height: float, style: LineageStyle) -> float:
    if count <= 1:
        return 0.0
    usable_half_height = max(node_height / 2 - style.port_size * 1.5, 0.0)
    return -usable_half_height + 2 * usable_half_height * index / (count - 1)


def _node_heights_for(model: LineageGraphModel, style: LineageStyle) -> dict[str, float]:
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


def _layer_positions(
    nodes_by_depth: dict[int, list[str]], node_heights: dict[str, float], style: LineageStyle
) -> dict[str, float]:
    node_y = {}
    for layer in nodes_by_depth.values():
        if not layer:
            continue
        centers = [0.0]
        for previous, current in zip(layer, layer[1:], strict=False):
            clearance = max(style.y_gap - style.node_height, 0.5)
            centers.append(
                centers[-1] + node_heights[previous] / 2 + node_heights[current] / 2 + clearance
            )
        midpoint = (centers[0] + centers[-1]) / 2
        node_y.update({node_id: y - midpoint for node_id, y in zip(layer, centers, strict=False)})
    return node_y


def _build_adjacency(edges: list[Any]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    upstream: dict[str, list[str]] = {}
    downstream: dict[str, list[str]] = {}
    for edge in edges:
        downstream.setdefault(edge.source_node_id, []).append(edge.target_node_id)
        upstream.setdefault(edge.target_node_id, []).append(edge.source_node_id)
    return upstream, downstream


def _order_layer(
    layer: list[str], neighbors: dict[str, list[str]], node_y: dict[str, float]
) -> list[str]:
    if len(layer) <= 1:
        return layer

    def sort_key(item: tuple[int, str]) -> tuple[float, int]:
        fallback, node_id = item
        values = [node_y[n] for n in neighbors.get(node_id, []) if n in node_y]
        return (sum(values) / len(values) if values else node_y.get(node_id, fallback), fallback)

    return [node_id for _, node_id in sorted(enumerate(layer), key=sort_key)]


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
    upstream, downstream = _build_adjacency(edges)
    max_depth = max(layers)
    for _ in range(max(0, int(iterations))):
        node_y = _layer_positions(layers, node_heights, style)
        for depth in range(1, max_depth + 1):
            layers[depth] = _order_layer(layers[depth], upstream, node_y)
        node_y = _layer_positions(layers, node_heights, style)
        for depth in range(max_depth - 1, -1, -1):
            layers[depth] = _order_layer(layers[depth], downstream, node_y)
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
    direction_groups = getattr(style, "port_groups", {}).get(node.key, {}).get(direction, [])
    default_group = len(direction_groups) // 2 if direction_groups else 0
    group_index = {name: index for index, group in enumerate(direction_groups) for name in group}
    port_to_ys = {port.id: [] for port in ports}
    for edge in edges:
        if direction == "in" and edge.target_port_id in port_to_ys and edge.source_node_id in pos:
            port_to_ys[edge.target_port_id].append(pos[edge.source_node_id][1])
        elif (
            direction == "out" and edge.source_port_id in port_to_ys and edge.target_node_id in pos
        ):
            port_to_ys[edge.source_port_id].append(pos[edge.target_node_id][1])

    def sort_key(port: PortModel) -> tuple:
        values = port_to_ys[port.id]
        average = sum(values) / len(values) if values else 0.0
        return (
            (group_index.get(port.name, default_group), average, port.index)
            if direction_groups
            else (average, port.index)
        )

    return sorted(ports, key=sort_key)


def _set_port_positions(
    model: LineageGraphModel, pos: dict, style: LineageStyle, node_heights: dict[str, float]
) -> None:
    for node_id, node in model.nodes.items():
        if node_id not in pos:
            continue
        x, y = pos[node_id]
        in_ports = _order_ports(node, node.in_ports, model.edges, pos, style, "in")
        out_ports = _order_ports(node, node.out_ports, model.edges, pos, style, "out")
        for index, port in enumerate(in_ports):
            pos[port.id] = (
                x - style.node_width / 2,
                y + _port_offset(index, len(in_ports), node_heights[node_id], style),
            )
        for index, port in enumerate(out_ports):
            pos[port.id] = (
                x + style.node_width / 2,
                y + _port_offset(index, len(out_ports), node_heights[node_id], style),
            )


def _layout_nodes_source_to_target(
    model: LineageGraphModel, style: LineageStyle, node_heights: dict[str, float] | None = None
) -> dict:
    pos = {}
    node_heights = node_heights or _node_heights_for(model, style)
    nodes_by_depth: dict[int, list[str]] = {}
    for node_id, node in model.nodes.items():
        nodes_by_depth.setdefault(node.depth, []).append(node_id)
    nodes_by_depth = {depth: sorted(layer) for depth, layer in nodes_by_depth.items()}
    if getattr(style, "layout_reorder", True):
        nodes_by_depth = _reorder_layers(
            nodes_by_depth, model.edges, node_heights, style, getattr(style, "layout_iterations", 3)
        )
    for depth, layer in sorted(nodes_by_depth.items()):
        layer_y = _layer_positions({depth: layer}, node_heights, style)
        for node_id in layer:
            pos[node_id] = (depth * style.x_gap, layer_y[node_id])
    _set_port_positions(model, pos, style, node_heights)
    return pos


def _layout_view_metrics(pos: dict, style: LineageStyle, node_heights: dict[str, float]) -> dict:
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


__all__ = [
    "_layout_nodes_source_to_target",
    "_layout_view_metrics",
    "_node_heights_for",
    "_set_port_positions",
    "_wrap_text_lines",
]
