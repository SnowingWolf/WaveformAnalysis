"""Lineage edge routing and style classification."""

from typing import Any

from waveform_analysis.core.foundation.utils import LineageStyle


def classify_edge_category(dtype: str) -> str:
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


def resolve_wire_style(edge: Any, style: LineageStyle) -> dict:
    dtype = edge.dtype or ""
    color = style.type_colors.get(dtype, style.type_colors.get("Unknown", "#95a5a6"))
    width = style.wire_linewidth
    alpha = style.wire_alpha
    dash = "solid"
    category_style = getattr(style, "wire_style_by_category", {}).get(
        classify_edge_category(dtype), {}
    )
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


def mpl_dash(dash: str | None) -> str:
    if not dash or dash == "solid":
        return "solid"
    return {"dash": "dashed", "dot": "dotted", "dashdot": "dashdot"}.get(dash, dash)
