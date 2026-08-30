"""Histogram backend compatibility view."""

from ..statistical_plots import _ensure_numba_histogram2d, _safe_histogram2d

__all__ = ["_ensure_numba_histogram2d", "_safe_histogram2d"]
