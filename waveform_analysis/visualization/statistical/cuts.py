"""Cut overlay renderers for corner plots."""

import logging

import numpy as np

logger = logging.getLogger(__name__)


def _axes_matrix(axes, size):
    result = np.asarray(axes)
    return result.reshape(size, size) if result.ndim == 1 else result


def plot_1d_cut_on_corner(
    axes,
    names,
    var,
    value,
    *,
    triangle="lower",
    color="crimson",
    linestyle="--",
    linewidth=1.5,
    label=None,
):
    matrix = _axes_matrix(axes, len(names))
    try:
        variable_index = names.index(var)
    except ValueError:
        raise ValueError(f"变量 '{var}' 不在 names 列表中: {names}") from None
    for row in range(len(names)):
        for column in range(len(names)):
            axis = matrix[row, column]
            if axis is None or not axis.get_visible():
                continue
            if triangle == "lower" and row < column or triangle == "upper" and row > column:
                continue
            if row == column == variable_index:
                axis.axvline(
                    value, color=color, linestyle=linestyle, linewidth=linewidth, label=label
                )
            elif column == variable_index:
                axis.axvline(value, color=color, linestyle=linestyle, linewidth=linewidth)
            elif row == variable_index:
                axis.axhline(value, color=color, linestyle=linestyle, linewidth=linewidth)


def plot_2d_cut_on_corner(
    axes,
    names,
    xvar,
    yvar,
    y_func,
    *,
    triangle="lower",
    x_range=None,
    n_points=300,
    color="crimson",
    linestyle="-",
    linewidth=2.0,
    label=None,
):
    matrix = _axes_matrix(axes, len(names))
    try:
        x_index = names.index(xvar)
    except ValueError:
        raise ValueError(f"变量 '{xvar}' 不在 names 列表中: {names}") from None
    try:
        y_index = names.index(yvar)
    except ValueError:
        raise ValueError(f"变量 '{yvar}' 不在 names 列表中: {names}") from None
    row, column = (x_index, y_index) if triangle == "upper" else (y_index, x_index)
    axis = matrix[row, column]
    if axis is None or not axis.get_visible():
        logger.warning("面板 (%s, %s) 对应 (%s, %s) 不可见，跳过绘制。", row, column, xvar, yvar)
        return
    lower, upper = axis.get_xlim() if x_range is None else x_range
    x = (
        np.logspace(np.log10(lower), np.log10(upper), n_points)
        if axis.get_xscale() == "log"
        else np.linspace(lower, upper, n_points)
    )
    axis.plot(x, y_func(x), color=color, linestyle=linestyle, linewidth=linewidth, label=label)


__all__ = ["plot_1d_cut_on_corner", "plot_2d_cut_on_corner"]
