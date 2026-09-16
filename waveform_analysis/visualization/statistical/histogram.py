"""Numba-accelerated 2D histogram backend with NumPy fallback."""

import logging
import sys

import numpy as np

logger = logging.getLogger(__name__)
_NUMBA_AVAILABLE = None
_numba_histogram2d = None


def _publish_backend_state() -> None:
    """Keep historical private state visible on the compatibility module."""
    module = sys.modules.get("waveform_analysis.visualization.statistical_plots")
    if module is not None:
        module._NUMBA_AVAILABLE = _NUMBA_AVAILABLE
        module._numba_histogram2d = _numba_histogram2d


def _ensure_numba_histogram2d():
    global _NUMBA_AVAILABLE, _numba_histogram2d
    if _NUMBA_AVAILABLE is not None:
        return
    try:
        from numba import njit

        @njit(cache=True, nogil=True)
        def _histogram2d_core(x, y, xedges, yedges, weights):
            nx = len(xedges) - 1
            ny = len(yedges) - 1
            result = np.zeros((nx, ny), dtype=np.float64)
            for index in range(len(x)):
                x_index = np.searchsorted(xedges, x[index], side="right") - 1
                y_index = np.searchsorted(yedges, y[index], side="right") - 1
                if x_index == nx and x[index] == xedges[nx]:
                    x_index = nx - 1
                if y_index == ny and y[index] == yedges[ny]:
                    y_index = ny - 1
                if 0 <= x_index < nx and 0 <= y_index < ny:
                    result[x_index, y_index] += 1.0 if weights is None else weights[index]
            return result.T

        _numba_histogram2d = _histogram2d_core
        _NUMBA_AVAILABLE = True
    except Exception as error:
        _NUMBA_AVAILABLE = False
        _numba_histogram2d = None
        logger.debug("Numba unavailable; using NumPy histogram2d: %s", error)
    _publish_backend_state()


def _safe_histogram2d(x, y, xbins, ybins, weights=None):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xbins = np.asarray(xbins, dtype=np.float64)
    ybins = np.asarray(ybins, dtype=np.float64)
    if weights is not None:
        weights = np.asarray(weights, dtype=np.float64)
    _ensure_numba_histogram2d()
    if _numba_histogram2d is not None:
        try:
            return _numba_histogram2d(x, y, xbins, ybins, weights)
        except Exception as error:
            logger.warning("Numba histogram2d failed; using NumPy: %s", error)
    result, _, _ = np.histogram2d(x, y, bins=[xbins, ybins], weights=weights)
    return result.T


def _compute_bin_index_ext(values, edges):
    """Return NumPy-histogram bin indices plus one out-of-range sentinel.

    The sentinel is numbered ``nbins``.  It lets a later ``bincount`` include
    all values in one pass and then discard its final bin, preserving the
    inclusion of the exact rightmost edge without allocating a boolean mask.
    """
    values = np.asarray(values)
    edges = np.asarray(edges)
    nbins = len(edges) - 1
    indices = np.searchsorted(edges, values, side="right") - 1
    at_right_edge = (indices == nbins) & (values == edges[-1])
    if np.any(at_right_edge):
        indices = np.where(at_right_edge, nbins - 1, indices)
    invalid = (indices < 0) | (indices >= nbins)
    return np.where(invalid, nbins, indices).astype(np.int32), nbins


def _hist1d_bincount(indices, nbins, weights=None):
    """Accumulate a 1D histogram from extended bin indices."""
    return np.bincount(indices, weights=weights, minlength=nbins + 1)[:nbins]


def _hist2d_bincount(xindices, nx, yindices, ny, weights=None):
    """Accumulate ``(y, x)`` 2D counts from extended bin indices."""
    combined = yindices.astype(np.int64)
    combined *= nx + 1
    combined += xindices
    counts = np.bincount(combined, weights=weights, minlength=(nx + 1) * (ny + 1))
    return counts.reshape(ny + 1, nx + 1)[:ny, :nx]


__all__ = [
    "_ensure_numba_histogram2d",
    "_safe_histogram2d",
]
