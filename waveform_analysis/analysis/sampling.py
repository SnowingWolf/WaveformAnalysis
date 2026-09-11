"""Reusable density-aware sampling helpers.

The public sampler operates on DataFrame row positions and two numeric
coordinates.  It is independent of Context, plugin products, labels, and
particular waveform features so callers can reuse it for exploratory plots,
training subsets, and representative event selection.
"""

from __future__ import annotations

from collections.abc import Sequence
from numbers import Integral
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["adaptive_sample_count", "adaptive_stratified_sample_2d"]


def _is_integer_scalar(value: Any) -> bool:
    """Return whether ``value`` is a valid integer bin/count scalar."""

    return isinstance(value, Integral) and not isinstance(value, bool | np.bool_)


def _make_bin_edges(
    values: Sequence[float] | np.ndarray,
    spec: Any,
    value_range: Sequence[float] | None = None,
) -> np.ndarray:
    """Normalize one integer-or-edges bin specification to float edges."""

    values_array = np.asarray(values, dtype=float)
    if values_array.ndim != 1:
        raise ValueError("Bin values must be one-dimensional.")

    if _is_integer_scalar(spec):
        n_bins = int(spec)
        if n_bins <= 0:
            raise ValueError("Number of bins must be positive.")

        if value_range is None:
            finite = values_array[np.isfinite(values_array)]
            if finite.size == 0:
                raise ValueError("Cannot determine bin range from non-finite values.")
            lo = float(np.min(finite))
            hi = float(np.max(finite))
        else:
            try:
                range_array = np.asarray(value_range, dtype=float)
            except (TypeError, ValueError) as exc:
                raise ValueError("Bin range must contain exactly two finite values.") from exc
            if range_array.ndim != 1 or len(range_array) != 2:
                raise ValueError("Bin range must contain exactly two values.")
            lo, hi = map(float, range_array)

        if not np.isfinite(lo) or not np.isfinite(hi):
            raise ValueError("Bin range must be finite.")
        if hi <= lo:
            raise ValueError("Bin range must satisfy max > min.")
        return np.linspace(lo, hi, n_bins + 1, dtype=float)

    try:
        edges = np.asarray(spec, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Bin edges must be a one-dimensional numeric sequence.") from exc

    if edges.ndim != 1:
        raise ValueError("Bin edges must be one-dimensional.")
    if len(edges) < 2:
        raise ValueError("Bin edges must contain at least two values.")
    if not np.all(np.isfinite(edges)):
        raise ValueError("Bin edges must be finite.")
    if not np.all(np.diff(edges) > 0):
        raise ValueError("Bin edges must be strictly increasing.")
    return edges.astype(float, copy=True)


def _parse_2d_bins(
    x_values: Sequence[float] | np.ndarray,
    y_values: Sequence[float] | np.ndarray,
    bins: Any,
    range: Sequence[Sequence[float] | None] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Parse a scalar, two-integer, explicit, or mixed 2D bin specification."""

    if _is_integer_scalar(bins):
        x_spec = bins
        y_spec = bins
    else:
        try:
            if len(bins) != 2:
                raise ValueError("bins must be an integer or a length-2 sequence.")
            x_spec, y_spec = bins
        except TypeError as exc:
            raise ValueError("bins must be an integer or a length-2 sequence.") from exc

    if range is None:
        x_range = None
        y_range = None
    else:
        try:
            if len(range) != 2:
                raise ValueError("range must be ((xmin, xmax), (ymin, ymax)).")
            x_range, y_range = range
        except TypeError as exc:
            raise ValueError("range must be ((xmin, xmax), (ymin, ymax)).") from exc

    return (
        _make_bin_edges(x_values, x_spec, value_range=x_range),
        _make_bin_edges(y_values, y_spec, value_range=y_range),
    )


def _assign_bins_2d(
    x_values: Sequence[float] | np.ndarray,
    y_values: Sequence[float] | np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Assign values to half-open bins while including the final upper edge."""

    x_array = np.asarray(x_values, dtype=float)
    y_array = np.asarray(y_values, dtype=float)
    if x_array.ndim != 1 or y_array.ndim != 1 or len(x_array) != len(y_array):
        raise ValueError("x and y values must be one-dimensional arrays of equal length.")

    x_bin = np.searchsorted(x_edges, x_array, side="right") - 1
    y_bin = np.searchsorted(y_edges, y_array, side="right") - 1
    x_bin[x_array == x_edges[-1]] = len(x_edges) - 2
    y_bin[y_array == y_edges[-1]] = len(y_edges) - 2
    return x_bin.astype(np.int64, copy=False), y_bin.astype(np.int64, copy=False)


def _validate_sample_count_parameters(n_full: Any, n_max: Any) -> tuple[int, int]:
    if not _is_integer_scalar(n_full) or not _is_integer_scalar(n_max):
        raise ValueError("n_full and n_max must be integers.")
    n_full_int = int(n_full)
    n_max_int = int(n_max)
    if n_full_int < 0 or n_max_int < 0:
        raise ValueError("n_full and n_max must be non-negative.")
    if n_max_int < n_full_int:
        raise ValueError("n_max must be greater than or equal to n_full.")
    return n_full_int, n_max_int


def adaptive_sample_count(n: int, n_full: int = 4, n_max: int = 12) -> int:
    """Return the adaptive number of rows retained from a bin.

    Bins containing at most ``n_full`` rows are retained completely.  Larger
    bins follow a monotonic saturating curve capped by ``n_max``.  The result
    is always between zero and the bin occupancy ``n``.

    Parameters
    ----------
    n:
        Number of eligible rows in the bin.
    n_full:
        Largest occupancy that is always retained in full.
    n_max:
        Maximum number of rows retained from any bin.
    """

    if not _is_integer_scalar(n):
        raise ValueError("n must be an integer.")
    n_int = int(n)
    if n_int < 0:
        raise ValueError("n must be non-negative.")
    n_full_int, n_max_int = _validate_sample_count_parameters(n_full, n_max)

    if n_int <= n_full_int:
        return n_int
    if n_max_int == n_full_int:
        return n_max_int

    extra = n_max_int - n_full_int
    recommended = n_full_int + extra * (1.0 - np.exp(-(n_int - n_full_int) / extra))
    return min(n_int, n_max_int, int(np.ceil(recommended)))


def _resolve_sampling_values(data: Any, feature: Any, name: str) -> np.ndarray:
    if isinstance(feature, str):
        try:
            feature_values = data[feature]
        except (KeyError, IndexError, TypeError) as exc:
            raise KeyError(f"{name} column {feature!r} was not found in data.") from exc
    else:
        feature_values = feature

    try:
        values = np.asarray(feature_values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} values must be numeric and one-dimensional.") from exc
    if values.ndim != 1:
        raise ValueError(f"{name} values must be one-dimensional.")
    if len(values) != len(data):
        raise ValueError(f"{name} values must have the same length as data.")
    return values


def _empty_bin_info() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "x_bin",
            "y_bin",
            "x_left",
            "x_right",
            "y_left",
            "y_right",
            "occupancy",
            "n_sampled",
            "sampling_fraction",
            "representative_index",
        ]
    )


def adaptive_stratified_sample_2d(
    data: pd.DataFrame,
    x: str | Sequence[float] | np.ndarray,
    y: str | Sequence[float] | np.ndarray,
    bins: Any = 25,
    *,
    range: Sequence[Sequence[float] | None] | None = None,
    n_full: int = 4,
    n_max: int = 12,
    random_state: Any = None,
    representative: bool = True,
    return_bin_info: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    """Sample a DataFrame using occupancy-aware two-dimensional strata.

    ``bins`` accepts one integer, two integer specifications, two explicit
    edge vectors, or a mixed integer/edge-vector pair.  ``range`` applies only
    to axes whose bin specification is an integer.  Rows with non-finite
    coordinates or coordinates outside the resolved edges are excluded.

    Each sparse bin retains all of its rows.  A dense bin retains an adaptive
    count capped by ``n_max``.  When ``representative`` is true and the bin has
    a positive quota, the row nearest the normalized bin centre is included
    before the remaining rows are sampled without replacement.

    The returned DataFrame is a copy that preserves the input columns and
    index.  Row order follows bin-processing order rather than global input
    order.  Set ``return_bin_info=True`` to also receive one diagnostics row
    per occupied bin.
    """

    if not hasattr(data, "iloc"):
        raise TypeError("data must provide pandas-style iloc row selection.")
    n_full_int, n_max_int = _validate_sample_count_parameters(n_full, n_max)
    adaptive_sample_count(0, n_full=n_full_int, n_max=n_max_int)

    x_array = _resolve_sampling_values(data, x, "x")
    y_array = _resolve_sampling_values(data, y, "y")
    finite = np.isfinite(x_array) & np.isfinite(y_array)
    finite_x = x_array[finite]
    finite_y = y_array[finite]
    x_edges, y_edges = _parse_2d_bins(
        finite_x if finite.any() else x_array,
        finite_y if finite.any() else y_array,
        bins=bins,
        range=range,
    )
    x_bin, y_bin = _assign_bins_2d(x_array, y_array, x_edges, y_edges)

    n_x_bins = len(x_edges) - 1
    n_y_bins = len(y_edges) - 1
    inside = finite & (x_bin >= 0) & (x_bin < n_x_bins) & (y_bin >= 0) & (y_bin < n_y_bins)
    valid_positions = np.flatnonzero(inside).astype(np.int64, copy=False)
    rng = np.random.default_rng(random_state)
    selected_parts: list[np.ndarray] = []
    info_rows: list[dict[str, Any]] = []

    if len(valid_positions):
        flat_bins = x_bin[valid_positions] * n_y_bins + y_bin[valid_positions]
        order = np.argsort(flat_bins, kind="stable")
        sorted_bins = flat_bins[order]
        starts = np.r_[0, np.flatnonzero(np.diff(sorted_bins)) + 1]
        ends = np.r_[starts[1:], len(order)]

        for start, end in zip(starts, ends, strict=False):
            group_positions = valid_positions[order[int(start) : int(end)]]
            flat_bin = int(sorted_bins[int(start)])
            x_index, y_index = divmod(flat_bin, n_y_bins)
            occupancy = len(group_positions)
            n_take = adaptive_sample_count(
                occupancy,
                n_full=n_full_int,
                n_max=n_max_int,
            )

            representative_position: int | None = None
            if n_take == 0:
                chosen = np.empty(0, dtype=np.int64)
            elif representative:
                x_center = (x_edges[x_index] + x_edges[x_index + 1]) / 2.0
                y_center = (y_edges[y_index] + y_edges[y_index + 1]) / 2.0
                x_width = x_edges[x_index + 1] - x_edges[x_index]
                y_width = y_edges[y_index + 1] - y_edges[y_index]
                distance = ((x_array[group_positions] - x_center) / x_width) ** 2 + (
                    (y_array[group_positions] - y_center) / y_width
                ) ** 2
                representative_offset = int(np.argmin(distance))
                representative_position = int(group_positions[representative_offset])
                if n_take > 1:
                    remaining = np.delete(group_positions, representative_offset)
                    random_positions = rng.choice(remaining, size=n_take - 1, replace=False)
                    chosen = np.concatenate(
                        [
                            np.asarray([representative_position], dtype=np.int64),
                            np.asarray(random_positions, dtype=np.int64),
                        ]
                    )
                else:
                    chosen = np.asarray([representative_position], dtype=np.int64)
            elif n_take == occupancy:
                chosen = group_positions.copy()
            else:
                chosen = np.asarray(
                    rng.choice(group_positions, size=n_take, replace=False),
                    dtype=np.int64,
                )

            selected_parts.append(chosen)
            info_rows.append(
                {
                    "x_bin": int(x_index),
                    "y_bin": int(y_index),
                    "x_left": float(x_edges[x_index]),
                    "x_right": float(x_edges[x_index + 1]),
                    "y_left": float(y_edges[y_index]),
                    "y_right": float(y_edges[y_index + 1]),
                    "occupancy": int(occupancy),
                    "n_sampled": int(n_take),
                    "sampling_fraction": float(n_take / occupancy),
                    "representative_index": (
                        data.index[representative_position]
                        if representative_position is not None
                        else None
                    ),
                }
            )

    selected_positions = (
        np.concatenate(selected_parts).astype(np.int64, copy=False)
        if selected_parts
        else np.empty(0, dtype=np.int64)
    )
    sampled = data.iloc[selected_positions].copy()
    if not return_bin_info:
        return sampled
    bin_info = pd.DataFrame(info_rows) if info_rows else _empty_bin_info()
    return sampled, bin_info
