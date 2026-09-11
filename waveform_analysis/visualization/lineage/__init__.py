"""Responsibility-oriented building blocks for lineage visualization."""

from importlib import import_module

__all__ = ["plot_lineage_labview", "plot_lineage_plotly"]


def __getattr__(name: str):
    if name in __all__:
        module = "matplotlib_renderer" if name == "plot_lineage_labview" else "plotly_renderer"
        return getattr(import_module(f".{module}", __name__), name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
