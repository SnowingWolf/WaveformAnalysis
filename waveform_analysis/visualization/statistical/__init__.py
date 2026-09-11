"""Binning, histogram, corner-layout, and cut-overlay modules."""

from importlib import import_module

__all__ = ["corner_hist", "plot_1d_cut_on_corner", "plot_2d_cut_on_corner"]


def __getattr__(name: str):
    if name == "corner_hist":
        return getattr(import_module(".corner", __name__), name)
    if name in {"plot_1d_cut_on_corner", "plot_2d_cut_on_corner"}:
        return getattr(import_module(".cuts", __name__), name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
