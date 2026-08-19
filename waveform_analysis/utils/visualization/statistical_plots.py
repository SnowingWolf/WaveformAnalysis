"""
统计图表 - 多变量分布和相关性可视化

本模块提供统计分析相关的可视化函数，用于探索数据分布、变量相关性和参数空间。

主要功能
--------
- corner_hist: 散点矩阵（corner plot），展示多变量的两两关系
  * 对角线显示单变量分布直方图
  * 下三角显示二维直方图
  * 支持对数刻度和自定义分箱
- plot_1d_cut_on_corner: 在 corner plot 上绘制单变量切割线
- plot_2d_cut_on_corner: 在 corner plot 上绘制二维切割曲线

典型应用
--------
- Hit/Peak 特征相关性分析（如 area vs height vs width）
- 参数空间探索和调优
- 质量控制：识别异常分布，标记切割阈值
- 特征工程：发现变量关系，可视化边界条件
- 数据筛选可视化：叠加展示筛选前后的分布对比

依赖
----
- matplotlib（必需）：绘图引擎
- numpy（必需）：数值计算

示例
--------
>>> from waveform_analysis.utils import corner_hist, plot_1d_cut_on_corner
>>> import numpy as np
>>>
>>> # 分析 hit 特征
>>> data = [hits['area'], hits['height'], hits['width']]
>>> fig, axes = corner_hist(
...     data,
...     names=['Area', 'Height', 'Width'],
...     scales=['log', 'log', 'log'],
...     bins=100,
... )
>>>
>>> # 添加切割线标识阈值
>>> plot_1d_cut_on_corner(axes, ['Area', 'Height', 'Width'],
...                       'Height', 1.3e4, color='red', label='Threshold')
>>>
>>> fig.savefig('hit_features_corner.png')
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

# 检查 matplotlib 可用性
try:
    from matplotlib.colors import LogNorm, Normalize
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Numba 加速支持（延迟初始化）
_NUMBA_AVAILABLE = None
_numba_histogram2d = None

__all__ = ["corner_hist", "plot_1d_cut_on_corner", "plot_2d_cut_on_corner"]


def _ensure_numba_histogram2d():
    """延迟初始化 Numba 加速的 2D 直方图函数。

    采用项目标准模式：全局变量 + 延迟导入 + 错误处理。
    参考：hit_merge.py, hit_finder.py
    """
    global _NUMBA_AVAILABLE, _numba_histogram2d

    if _NUMBA_AVAILABLE is not None:
        return  # 已经初始化过

    try:
        from numba import njit

        @njit(cache=True, nogil=True)
        def _histogram2d_core(x, y, xedges, yedges, weights):
            """Numba JIT 编译的 2D 直方图核心计算。

            参数
            ----
            x, y : ndarray
                数据点坐标，长度必须相同。
            xedges, yedges : ndarray
                bin 边界数组。
            weights : ndarray or None
                权重数组，长度与 x/y 相同，或为 None。

            返回
            ----
            H : ndarray
                2D 直方图，形状 (len(yedges)-1, len(xedges)-1)，
                已转置以匹配 np.histogram2d 的输出格式。

            性能
            ----
            首次调用会触发 JIT 编译（~1-2秒），后续调用使用缓存。
            对于 100k 点，相比 np.histogram2d 可获得 5-10x 加速。
            """
            nx = len(xedges) - 1
            ny = len(yedges) - 1
            H = np.zeros((nx, ny), dtype=np.float64)

            n = len(x)
            for i in range(n):
                xi = x[i]
                yi = y[i]

                # 使用 searchsorted 找到 bin 索引
                # side='right' 确保边界行为与 np.histogram2d 一致
                ix = np.searchsorted(xedges, xi, side="right") - 1
                iy = np.searchsorted(yedges, yi, side="right") - 1

                # 边界检查：只有在有效范围内的点才计入
                if 0 <= ix < nx and 0 <= iy < ny:
                    if weights is None:
                        H[ix, iy] += 1.0
                    else:
                        H[ix, iy] += weights[i]

            # 转置以匹配 numpy 的 (y, x) 约定
            return H.T

        _numba_histogram2d = _histogram2d_core
        _NUMBA_AVAILABLE = True
        logger.debug("Numba 2D 直方图加速已启用")

    except Exception as e:
        _NUMBA_AVAILABLE = False
        _numba_histogram2d = None
        logger.debug(f"Numba 不可用，将使用 NumPy 版本: {e}")


def _safe_histogram2d(x, y, xbins, ybins, weights=None):
    """安全的 2D 直方图计算，自动选择最优实现。

    优先使用 Numba 加速版本，失败时降级到 NumPy。

    参数
    ----
    x, y : ndarray
        数据点坐标。
    xbins, ybins : ndarray
        bin 边界数组。
    weights : ndarray or None
        权重数组。

    返回
    ----
    H : ndarray
        2D 直方图，形状 (len(ybins)-1, len(xbins)-1)。
    """
    # 确保数据类型兼容 Numba（统一为 float64）
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xbins = np.asarray(xbins, dtype=np.float64)
    ybins = np.asarray(ybins, dtype=np.float64)

    if weights is not None:
        weights = np.asarray(weights, dtype=np.float64)

    # 尝试使用 Numba 加速版本
    _ensure_numba_histogram2d()

    if _numba_histogram2d is not None:
        try:
            return _numba_histogram2d(x, y, xbins, ybins, weights)
        except Exception as e:
            logger.warning(f"Numba 2D 直方图计算失败，降级到 NumPy: {e}")

    # Fallback 到 NumPy 实现
    H, _, _ = np.histogram2d(x, y, bins=[xbins, ybins], weights=weights)
    return H.T


def corner_hist(
    data: list | tuple,
    names: list[str] | None = None,
    bins: int | list | tuple = 100,
    ranges: list[tuple[float, float]] | None = None,
    scales: str | list[str] = "linear",
    weights: np.ndarray | None = None,
    figsize_per_panel: float = 3.0,
    cmap: str = "viridis",
    hist_color: str = "C0",
    hist2d_norm: str | None = "log",
    hist2d_vmin: float = 1,
    hist2d_vmax: float | None = None,
    add_colorbar: bool = False,
    title: str | None = None,
    min_count: int = 1,
    hist_alpha: float = 1.0,
    hist2d_alpha: float = 1.0,
    fig=None,
    axes=None,
    triangle: str = "lower",
    label_mode: str = "outer",
    label_fontsize: int = 11,
    label_fontweight: str = "bold",
    tick_labelsize: int = 8,
    diag_title: bool = True,
    show_ticks: bool = True,
    show_ticklabels: bool | tuple | None = None,
    hist_density: bool = False,
):
    """
    绘制散点矩阵（corner plot）用于多变量分布分析。

    散点矩阵展示多个变量之间的两两关系：
    - 对角线：单变量直方图
    - 下三角：二维直方图（热图）
    - 上三角：可配置（空白/显示/完整矩阵）

    适用于探索变量相关性、参数空间和数据质量。

    参数
    ----------
    data : list or tuple of 1D arrays
        待分析的变量列表。每个元素为一维数组，所有数组长度必须相同。
        示例：data = [area, height, width]
    names : list of str, optional
        变量名称列表，长度应与 data 相同。若为 None，则自动生成
        形如 'x0', 'x1' 的名称。
    bins : int or list or tuple, default=100
        直方图分箱规范。可以是：

        - int：所有变量使用相同的分箱数
        - list/tuple：每个变量指定不同的分箱数或边界
          示例：bins = [np.logspace(1, 7, 200), np.logspace(2, 5, 200)]
    ranges : list of tuple, optional
        每个变量的数据范围 (min, max)。
        示例：ranges = [(1e1, 1e7), (1e2, 1e5), (1e1, 1e5)]
    scales : str or list of str, default='linear'
        坐标轴刻度类型。可以是：

        - 'linear'：线性刻度
        - 'log'：对数刻度
        - list：每个变量指定不同刻度，如 ['log', 'log', 'linear']
    weights : ndarray, optional
        事件权重，长度与每个数据数组相同。
    figsize_per_panel : float, default=3.0
        每个子图的尺寸（英寸）。
    cmap : str, default='viridis'
        二维直方图的颜色映射。
    hist_color : str, default='C0'
        一维直方图的线条颜色。
    hist2d_norm : {'log', None}, default='log'
        二维直方图的归一化方式：

        - 'log'：对数归一化
        - None：线性归一化
    hist2d_vmin : float, default=1
        二维直方图颜色映射的最小值。
    hist2d_vmax : float, optional
        二维直方图颜色映射的最大值。
    add_colorbar : bool, default=False
        是否为每个二维直方图添加颜色条。
    title : str, optional
        图形标题。
    min_count : int, default=1
        二维直方图中显示的最小计数。低于此值的箱子被遮蔽。
    hist_alpha : float, default=1.0
        对角线 1D 直方图的透明度（0-1）。
    hist2d_alpha : float, default=1.0
        非对角线 2D 直方图的透明度（0-1）。
    fig : matplotlib.figure.Figure, optional
        已有图形对象。与 axes 一起使用可在现有图上叠加新数据。
    axes : numpy.ndarray, optional
        已有子图轴数组，形状为 (n, n)。与 fig 一起使用。
    triangle : {'lower', 'upper', 'full'}, default='lower'
        控制显示区域：

        - 'lower'：只显示下三角
        - 'upper'：只显示上三角
        - 'full'：显示完整矩阵
    label_mode : {'outer', 'all', 'diag', 'none'}, default='outer'
        标签显示模式：

        - 'outer'：只在外圈显示标签
        - 'all'：每个子图都显示标签
        - 'diag'：只在对角线显示 x 轴标签
        - 'none'：不显示标签
    label_fontsize : int, default=11
        轴标签字体大小。
    label_fontweight : str, default='bold'
        轴标签字体粗细。
    tick_labelsize : int, default=8
        刻度标签字体大小。
    diag_title : bool, default=True
        是否在对角线子图上方显示变量名作为标题。
    show_ticks : bool, default=True
        是否显示刻度标记。若为 False，所有子图的刻度标记将被隐藏，
        但刻度标签的显示仍由 label_mode 控制。
    show_ticklabels : bool or tuple or None, default=None
        是否显示刻度标签（数字 ticker）。用于在每个子图上显示数字刻度：

        - None：跟随 label_mode。内部子图的刻度标签被隐藏，
          只有外圈子图显示刻度标签（默认行为，向后兼容）。
        - True：所有子图都显示刻度标签。
        - False：所有子图都隐藏刻度标签。
        - tuple：如 (True, False)，对所有子图分别控制 x/y 轴刻度标签，
          即所有子图的 x 轴是否显示、所有子图的 y 轴是否显示。
    hist_density : bool, default=False
        对角线 1D 直方图是否按概率密度归一化（density=True，积分=1）。
        默认 False = 原始计数。叠加对比前后景时建议 True，让两层用同一归一化可直接比形状。

    返回
    -------
    fig : matplotlib.figure.Figure
        生成的图形对象。
    axes : numpy.ndarray
        子图轴对象数组，形状为 (n, n)，其中 n 是变量数量。

    异常
    -------
    TypeError
        当 data 不是 list 或 tuple 时抛出。
    ValueError
        当 data 为空、数组维度不一致或长度不匹配时抛出。
        当 triangle 或 label_mode 参数值无效时抛出。
        当 fig 和 axes 仅提供其中之一时抛出。
    ImportError
        当 matplotlib 未安装时抛出。

    示例
    --------
    >>> from waveform_analysis.utils import corner_hist
    >>> import numpy as np
    >>>
    >>> # 基本用法
    >>> data = [np.random.randn(1000) for _ in range(3)]
    >>> fig, axes = corner_hist(data, names=['X', 'Y', 'Z'])
    >>> fig.savefig('corner_basic.png')
    >>>
    >>> # 对数刻度分析 hit 特征
    >>> data = [
    ...     np.random.lognormal(5, 1, 1000),  # Area
    ...     np.random.lognormal(3, 0.5, 1000),  # Height
    ...     np.random.lognormal(2, 0.3, 1000),  # Width
    ... ]
    >>> fig, axes = corner_hist(
    ...     data,
    ...     names=['Area', 'Height', 'Width'],
    ...     scales=['log', 'log', 'log'],
    ...     bins=[np.logspace(1, 7, 100), np.logspace(2, 5, 100), np.logspace(1, 5, 100)],
    ...     ranges=[(1e1, 1e7), (1e2, 1e5), (1e1, 1e5)],
    ... )
    >>> fig.savefig('corner_log.png')
    >>>
    >>> # 叠加对比：mask 前后数据
    >>> fig, axes = corner_hist(data_before, names=names, hist_color='blue',
    ...                         hist_alpha=0.5, hist2d_alpha=0.5)
    >>> fig, axes = corner_hist(data_after, names=names, hist_color='red',
    ...                         hist_alpha=0.5, hist2d_alpha=0.5,
    ...                         fig=fig, axes=axes)
    >>> fig.savefig('corner_comparison.png')

    注意
    -----
    - 本函数依赖 matplotlib 库
    - 对数刻度要求数据为正值，负值和零会被自动过滤
    - 大量数据点可能导致绘图速度较慢，建议使用合适的 bins 数量
    - 使用 fig/axes 叠加时，确保两次调用的 names 顺序一致

    另见
    --------
    plot_waveforms : 波形时序可视化
    """
    if not MATPLOTLIB_AVAILABLE:
        raise ImportError("corner_hist 需要 matplotlib 库。\n" "安装方法：pip install matplotlib")

    if triangle not in ("lower", "upper", "full"):
        raise ValueError("triangle must be 'lower', 'upper', or 'full'.")

    if label_mode not in ("outer", "all", "diag", "none"):
        raise ValueError("label_mode must be 'outer', 'all', 'diag', or 'none'.")

    if show_ticklabels is not None and not isinstance(show_ticklabels, bool | tuple | list):
        raise ValueError("show_ticklabels 应为 bool、tuple、list 或 None。")
    if isinstance(show_ticklabels, tuple | list):
        if len(show_ticklabels) != 2:
            raise ValueError("show_ticklabels 元组长度应为 2（分别对应 x 轴、y 轴）。")

    # 参数验证
    if not isinstance(data, list | tuple):
        raise TypeError("data 应该是 list 或 tuple 类型的 1D 数组集合。")

    data = [np.asarray(x) for x in data]
    n = len(data)

    if n == 0:
        raise ValueError("data 为空。")

    length = len(data[0])
    for i, x in enumerate(data):
        if x.ndim != 1:
            raise ValueError(f"data[{i}] 不是 1D 数组（维度：{x.ndim}）。")
        if len(x) != length:
            raise ValueError("data 中所有数组的长度必须相同。")

    # 处理变量名
    if names is None:
        names = [f"x{i}" for i in range(n)]
    else:
        names = list(names)

    if len(names) != n:
        raise ValueError(f"names 长度（{len(names)}）应与 data 长度（{n}）相同。")

    # 扩展标量参数为列表
    def expand_param(param, default=None, name="parameter"):
        if param is None:
            return [default for _ in range(n)]

        if isinstance(param, str):
            return [param for _ in range(n)]

        if isinstance(param, int | float | np.integer | np.floating):
            return [param for _ in range(n)]

        if isinstance(param, list | tuple):
            if len(param) != n:
                raise ValueError(f"{name} 长度应为 {n}，得到 {len(param)}。")
            return list(param)

        return [param for _ in range(n)]

    scales = expand_param(scales, default="linear", name="scales")
    ranges = expand_param(ranges, default=None, name="ranges")

    for s in scales:
        if s not in ("linear", "log"):
            raise ValueError("scales 只支持 'linear' 或 'log'。")

    # 处理 bins 参数
    if isinstance(bins, int | np.integer):
        bins = [int(bins) for _ in range(n)]
    elif isinstance(bins, list | tuple):
        if len(bins) != n:
            raise ValueError(f"bins 长度应为 {n}，得到 {len(bins)}。")
        bins = list(bins)
    else:
        bins = [bins for _ in range(n)]

    # 全局过滤：有限值、范围、对数刻度
    # 向量化实现：收集所有条件，一次性合并
    conditions = []

    for x, r, scale in zip(data, ranges, scales, strict=False):
        conditions.append(np.isfinite(x))

        if r is not None:
            lo, hi = r
            conditions.append((x >= lo) & (x <= hi))

        if scale == "log":
            conditions.append(x > 0)

    # 使用 logical_and.reduce 一次性合并所有条件，避免多次中间数组创建
    mask = np.logical_and.reduce(conditions) if conditions else np.ones(length, dtype=bool)

    data = [x[mask] for x in data]

    if weights is not None:
        weights = np.asarray(weights)
        if len(weights) != length:
            raise ValueError("weights 长度应与数据数组长度相同。")
        weights = weights[mask]

    # 解析分箱边界
    def resolve_bins(x, b, r, scale):
        # 显式指定的分箱边界
        if not isinstance(b, int | np.integer):
            edges = np.asarray(b)
            if edges.ndim != 1 or len(edges) < 2:
                raise ValueError("显式 bins 必须是一维 bin edge 数组，且长度至少为 2。")
            return edges

        nbin = int(b)
        if nbin <= 0:
            raise ValueError("bins 必须为正整数。")

        if r is not None:
            lo, hi = r
        else:
            # 空数据或全 NaN 的处理
            if len(x) == 0 or not np.any(np.isfinite(x)):
                # 返回默认范围
                lo, hi = 0.0, 1.0
            else:
                lo, hi = np.nanmin(x), np.nanmax(x)

        if not np.isfinite(lo) or not np.isfinite(hi):
            # 如果仍然无效，使用默认范围
            lo, hi = 0.0, 1.0

        if lo == hi:
            eps = 1e-12 if lo == 0 else abs(lo) * 1e-12
            lo -= eps
            hi += eps

        if scale == "log":
            if lo <= 0:
                positive = x[x > 0] if len(x) > 0 else np.array([])
                if len(positive) == 0:
                    # 对数刻度但无正值数据，使用默认对数范围
                    lo = 1e-3
                    hi = 1.0
                else:
                    lo = np.nanmin(positive)

            if hi <= 0:
                hi = 1.0  # 默认上限

            return np.logspace(np.log10(lo), np.log10(hi), nbin + 1)

        return np.linspace(lo, hi, nbin + 1)

    bin_edges = [
        resolve_bins(x, b, r, scale)
        for x, b, r, scale in zip(data, bins, ranges, scales, strict=False)
    ]

    # 创建或复用图形
    if (fig is None) != (axes is None):
        raise ValueError("fig 和 axes 要么同时提供，要么都不提供。")

    created_new_figure = fig is None and axes is None

    if created_new_figure:
        fig, axes = plt.subplots(
            n,
            n,
            figsize=(figsize_per_panel * n, figsize_per_panel * n),
            squeeze=False,
        )
    else:
        axes = np.asarray(axes)
        if axes.shape != (n, n):
            raise ValueError(f"axes 形状应为 ({n}, {n})，得到 {axes.shape}。")

    if hist2d_norm == "log":
        norm = LogNorm(vmin=hist2d_vmin, vmax=hist2d_vmax)
    elif hist2d_norm is None:
        norm = Normalize(vmin=hist2d_vmin, vmax=hist2d_vmax)
    else:
        raise ValueError("hist2d_norm 只支持 'log' 或 None。")

    for i in range(n):
        for j in range(n):
            ax = axes[i, j]

            # 控制显示 lower / upper / full
            if triangle == "lower" and i < j:
                if created_new_figure:
                    ax.axis("off")
                continue

            if triangle == "upper" and i > j:
                if created_new_figure:
                    ax.axis("off")
                continue

            x = data[j]
            y = data[i]

            xname = names[j]
            yname = names[i]

            xbins = bin_edges[j]
            ybins = bin_edges[i]

            xscale = scales[j]
            yscale = scales[i]

            # 对角线：1D 直方图
            if i == j:
                ax.hist(
                    x,
                    bins=xbins,
                    weights=weights,
                    histtype="step",
                    linewidth=1.5,
                    color=hist_color,
                    alpha=hist_alpha,
                    density=hist_density,
                )

                ax.set_xscale(xscale)
                ax.set_yscale("log")

            # 非对角线：2D 直方图
            else:
                # 使用 Numba 加速版本（自动降级到 NumPy）
                H = _safe_histogram2d(x, y, xbins, ybins, weights)
                H = np.ma.masked_less(H, min_count)

                # 只有在有有效数据时才绘制
                if H.count() > 0:  # masked array 的 count() 返回未遮蔽的元素数
                    mesh = ax.pcolormesh(
                        xbins,
                        ybins,
                        H,
                        cmap=cmap,
                        norm=norm,
                        shading="auto",
                        alpha=hist2d_alpha,
                    )

                    if add_colorbar:
                        fig.colorbar(mesh, ax=ax)

                ax.set_xscale(xscale)
                ax.set_yscale(yscale)

            # label 控制
            if label_mode == "outer":
                if triangle == "upper":
                    show_xlabel = i == 0
                    show_ylabel = j == n - 1
                else:
                    show_xlabel = i == n - 1
                    show_ylabel = j == 0

            elif label_mode == "all":
                show_xlabel = True
                show_ylabel = True

            elif label_mode == "diag":
                show_xlabel = i == j
                show_ylabel = False

            elif label_mode == "none":
                show_xlabel = False
                show_ylabel = False

            # 解析刻度标签显示（数字 ticker）
            if show_ticklabels is None:
                show_xticklabels = show_xlabel
                show_yticklabels = show_ylabel
            elif isinstance(show_ticklabels, tuple | list):
                show_xticklabels, show_yticklabels = show_ticklabels
            else:
                show_xticklabels = show_yticklabels = bool(show_ticklabels)

            if show_xlabel:
                ax.set_xlabel(
                    xname,
                    fontsize=label_fontsize,
                    fontweight=label_fontweight,
                )
            else:
                ax.set_xlabel("")

            if show_ylabel:
                ax.set_ylabel(
                    yname,
                    fontsize=label_fontsize,
                    fontweight=label_fontweight,
                )
            else:
                ax.set_ylabel("")

            # Hiding tick labels through ``tick_params`` avoids constructing
            # replacement Text artists on every panel (which is costly for a
            # corner matrix) while preserving the visible-label contract.
            if not show_xticklabels:
                ax.tick_params(axis="x", which="both", labelbottom=False, labeltop=False)
            if not show_yticklabels:
                ax.tick_params(axis="y", which="both", labelleft=False, labelright=False)

            if diag_title and i == j:
                ax.set_title(
                    xname,
                    fontsize=label_fontsize + 1,
                    fontweight=label_fontweight,
                )

            ax.tick_params(axis="both", which="both", labelsize=tick_labelsize)

            # 控制刻度标记显示
            if not show_ticks:
                ax.tick_params(
                    axis="both",
                    which="both",
                    left=False,
                    right=False,
                    top=False,
                    bottom=False,
                )

    if title is not None:
        fig.suptitle(
            title,
            y=1.02,
            fontsize=label_fontsize + 2,
            fontweight=label_fontweight,
        )

    fig.tight_layout()
    return fig, axes


def _axes_matrix(axes, n):
    """
    确保 axes 是一个 n x n 的数组。

    参数
    ----------
    axes : array-like
        轴对象数组。
    n : int
        维度大小。

    返回
    -------
    numpy.ndarray
        形状为 (n, n) 的轴数组。
    """
    axarr = np.asarray(axes)
    if axarr.ndim == 1:
        axarr = axarr.reshape(n, n)
    return axarr


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
    """
    在 corner plot 的所有涉及指定变量的面板上绘制单变量切割线。

    用于在散点矩阵上标记单变量的阈值或切割条件，例如：
    - height < 1.3e4
    - n_hits > 200
    - area >= 100

    切割线会出现在：
    - 对角线直方图：作为垂直线
    - 非对角线面板：当 x 或 y 轴为该变量时，作为垂直或水平线

    参数
    ----------
    axes : numpy.ndarray
        由 corner_hist 返回的子图轴数组，形状为 (n, n)。
    names : list of str
        变量名称列表，与创建 corner plot 时使用的顺序一致。
    var : str
        要绘制切割线的变量名，必须在 names 中。
    value : float
        切割线的位置（变量的值）。
    triangle : {'lower', 'upper', 'full'}, default='lower'
        corner plot 的显示模式，应与创建时使用的值一致：

        - 'lower'：只在下三角绘制
        - 'upper'：只在上三角绘制
        - 'full'：在完整矩阵绘制
    color : str, default='crimson'
        切割线的颜色。
    linestyle : str, default='--'
        切割线的线型，如 '-', '--', '-.', ':'。
    linewidth : float, default=1.5
        切割线的宽度。
    label : str, optional
        图例标签。仅在对角线直方图上显示一次。

    示例
    --------
    >>> from waveform_analysis.utils import corner_hist, plot_1d_cut_on_corner
    >>> import numpy as np
    >>>
    >>> # 创建 corner plot
    >>> data = [hits['area'], hits['height'], hits['width']]
    >>> names = ['Area', 'Height', 'Width']
    >>> fig, axes = corner_hist(data, names=names, scales='log')
    >>>
    >>> # 添加 height 的切割线
    >>> plot_1d_cut_on_corner(
    ...     axes, names, 'Height', 1.3e4,
    ...     color='red', label='Height threshold'
    ... )
    >>>
    >>> # 添加 area 的切割线
    >>> plot_1d_cut_on_corner(
    ...     axes, names, 'Area', 100,
    ...     color='blue', linestyle=':', label='Area min'
    ... )
    >>>
    >>> fig.savefig('corner_with_cuts.png')

    注意
    -----
    - var 必须存在于 names 中，否则会引发 ValueError
    - triangle 参数应与创建 corner plot 时使用的值一致
    - label 只会在对角线直方图上显示一次，避免重复图例

    另见
    --------
    corner_hist : 创建散点矩阵
    plot_2d_cut_on_corner : 绘制二维切割曲线
    """
    n = len(names)
    axarr = _axes_matrix(axes, n)

    try:
        k = names.index(var)
    except ValueError:
        raise ValueError(f"变量 '{var}' 不在 names 列表中: {names}")

    for row in range(n):
        for col in range(n):
            ax = axarr[row, col]

            if ax is None or not ax.get_visible():
                continue

            # 下三角：配对面板满足 row > col
            if triangle == "lower" and row < col:
                continue

            # 上三角：配对面板满足 row < col
            if triangle == "upper" and row > col:
                continue

            # 对角线直方图：变量在 x 轴上
            if row == col == k:
                ax.axvline(
                    value,
                    color=color,
                    linestyle=linestyle,
                    linewidth=linewidth,
                    label=label,
                )

            # 非对角线：x = names[col], y = names[row]
            elif col == k:
                # 变量在 x 轴，绘制垂直线
                ax.axvline(
                    value,
                    color=color,
                    linestyle=linestyle,
                    linewidth=linewidth,
                )

            elif row == k:
                # 变量在 y 轴，绘制水平线
                ax.axhline(
                    value,
                    color=color,
                    linestyle=linestyle,
                    linewidth=linewidth,
                )


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
    """
    在 corner plot 的对应面板上绘制二维切割曲线 y = y_func(x)。

    用于在散点矩阵上标记两个变量之间的关系或边界条件，例如：
    - height = 10 ** (k * log10(area) + b)
    - width_max = a * sqrt(area)
    - energy_threshold = c * height

    曲线会出现在 (xvar, yvar) 对应的非对角线面板上。

    参数
    ----------
    axes : numpy.ndarray
        由 corner_hist 返回的子图轴数组，形状为 (n, n)。
    names : list of str
        变量名称列表，与创建 corner plot 时使用的顺序一致。
    xvar : str
        x 轴变量名，必须在 names 中。
    yvar : str
        y 轴变量名，必须在 names 中。
    y_func : callable
        函数 y = y_func(x)，接受 numpy 数组并返回对应的 y 值。
    triangle : {'lower', 'upper', 'full'}, default='lower'
        corner plot 的显示模式，应与创建时使用的值一致：

        - 'lower'：在下三角查找面板（y 在行，x 在列）
        - 'upper'：在上三角查找面板（x 在行，y 在列）
        - 'full'：优先在 (yvar, xvar) 位置绘制
    x_range : tuple of float, optional
        x 值的范围 (xmin, xmax)。若为 None，则使用轴的当前 xlim。
    n_points : int, default=300
        曲线的采样点数。
    color : str, default='crimson'
        曲线颜色。
    linestyle : str, default='-'
        曲线线型，如 '-', '--', '-.', ':'。
    linewidth : float, default=2.0
        曲线宽度。
    label : str, optional
        图例标签。

    示例
    --------
    >>> from waveform_analysis.utils import corner_hist, plot_2d_cut_on_corner
    >>> import numpy as np
    >>>
    >>> # 创建 corner plot
    >>> data = [hits['area'], hits['height'], hits['width']]
    >>> names = ['Area', 'Height', 'Width']
    >>> fig, axes = corner_hist(data, names=names, scales='log')
    >>>
    >>> # 添加 height vs area 的关系曲线
    >>> def height_model(area):
    ...     return 10 ** (0.5 * np.log10(area) + 1.5)
    >>>
    >>> plot_2d_cut_on_corner(
    ...     axes, names, 'Area', 'Height', height_model,
    ...     color='orange', linewidth=2.5, label='Expected relation'
    ... )
    >>>
    >>> # 添加 width 上限
    >>> def width_max(area):
    ...     return 2.0 * np.sqrt(area)
    >>>
    >>> plot_2d_cut_on_corner(
    ...     axes, names, 'Area', 'Width', width_max,
    ...     color='green', linestyle='--', label='Width limit'
    ... )
    >>>
    >>> fig.savefig('corner_with_2d_cuts.png')

    注意
    -----
    - xvar 和 yvar 必须都存在于 names 中
    - y_func 应该能够处理 numpy 数组输入
    - 如果轴是对数刻度，函数会自动使用 logspace 采样
    - triangle 参数应与创建 corner plot 时使用的值一致

    另见
    --------
    corner_hist : 创建散点矩阵
    plot_1d_cut_on_corner : 绘制单变量切割线
    """
    n = len(names)
    axarr = _axes_matrix(axes, n)

    try:
        ix = names.index(xvar)
    except ValueError:
        raise ValueError(f"变量 '{xvar}' 不在 names 列表中: {names}")

    try:
        iy = names.index(yvar)
    except ValueError:
        raise ValueError(f"变量 '{yvar}' 不在 names 列表中: {names}")

    # 根据 triangle 模式确定面板位置
    if triangle == "lower":
        row, col = iy, ix
    elif triangle == "upper":
        row, col = ix, iy
    else:
        # 对于完整矩阵，优先使用 yvar 作为行，xvar 作为列
        row, col = iy, ix

    ax = axarr[row, col]

    if ax is None or not ax.get_visible():
        logger.warning(f"面板 ({row}, {col}) 对应 ({xvar}, {yvar}) 不可见，跳过绘制。")
        return

    # 确定 x 范围
    if x_range is None:
        xlo, xhi = ax.get_xlim()
    else:
        xlo, xhi = x_range

    # 根据 x 轴刻度选择采样方式
    if ax.get_xscale() == "log":
        x = np.logspace(np.log10(xlo), np.log10(xhi), n_points)
    else:
        x = np.linspace(xlo, xhi, n_points)

    y = y_func(x)

    ax.plot(
        x,
        y,
        color=color,
        linestyle=linestyle,
        linewidth=linewidth,
        label=label,
    )
