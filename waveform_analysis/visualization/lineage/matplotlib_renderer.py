"""Matplotlib lineage renderer entry point."""

from functools import wraps


def _implementation():
    from ..lineage_visualizer import _plot_lineage_labview_impl

    return _plot_lineage_labview_impl


@wraps(_implementation())
def plot_lineage_labview(*args, **kwargs):
    return _implementation()(*args, **kwargs)


__all__ = ["plot_lineage_labview"]
