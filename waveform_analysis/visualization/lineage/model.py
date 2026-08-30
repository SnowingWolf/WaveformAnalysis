"""Lineage graph models and visual node classification."""

from waveform_analysis.core.foundation.model import (
    LineageGraphModel,
    NodeModel,
    PortModel,
    build_lineage_graph,
)

__all__ = ["LineageGraphModel", "NodeModel", "PortModel", "build_lineage_graph"]


def classify_node_type(node: NodeModel) -> str:
    """Classify a node into the stable visualization color categories."""
    plugin_class_lower = node.plugin_class.lower()
    node_key_lower = node.key.lower()
    if any(keyword in plugin_class_lower for keyword in ["rawfiles", "loader", "reader"]):
        return "raw_data"
    if "dataframe" in plugin_class_lower or "dataframe" in node_key_lower or node.key == "df":
        return "dataframe"
    for port in node.out_ports:
        if "dataframe" in port.dtype.lower():
            return "dataframe"
    if any(keyword in plugin_class_lower for keyword in ["group", "pair", "aggregate", "merge"]):
        return "grouped"
    if any(keyword in node_key_lower for keyword in ["grouped", "paired", "merged"]):
        return "grouped"
    if any(keyword in plugin_class_lower for keyword in ["export", "save", "write"]):
        return "side_effect"
    for port in node.out_ports:
        dtype_str = port.dtype.lower()
        if ("[(" in dtype_str or ", " in dtype_str) and "list" not in dtype_str:
            return "structured_array"
    return "intermediate"


def get_node_colors(node_type: str) -> tuple:
    """Return background, border, and header colors for a node category."""
    color_scheme = {
        "raw_data": ("#e3f2fd", "#1976d2", "#bbdefb"),
        "structured_array": ("#e8f5e9", "#388e3c", "#c8e6c9"),
        "dataframe": ("#fff3e0", "#f57c00", "#ffe0b2"),
        "grouped": ("#f3e5f5", "#7b1fa2", "#e1bee7"),
        "side_effect": ("#fce4ec", "#c2185b", "#f8bbd0"),
        "intermediate": ("#fafafa", "#424242", "#e0e0e0"),
    }
    return color_scheme.get(node_type, color_scheme["intermediate"])
