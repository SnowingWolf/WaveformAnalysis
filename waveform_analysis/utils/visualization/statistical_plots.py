"""
统计图表 - 多变量分布和相关性可视化

本模块提供统计分析相关的可视化函数，用于探索数据分布、变量相关性和参数空间。

主要功能
--------
- corner_hist: 散点矩阵（corner plot），展示多变量的两两关系
- 对角线显示单变量分布直方图
- 下三角显示二维直方图
- 支持对数刻度和自定义分箱

典型应用
--------
- Hit/Peak 特征相关性分析（如 area vs height vs width）
- 参数空间探索和调优
- 质量控制：识别异常分布
- 特征工程：发现变量关系

依赖
----
- matplotlib（必需）：绘图引擎
- numpy（必需）：数值计算

示例
--------
>>> from waveform_analysis.utils import corner_hist
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

__all__ = ["corner_hist"]


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
):
    """
    绘制散点矩阵（corner plot）用于多变量分布分析。

    散点矩阵展示多个变量之间的两两关系：
    - 对角线：单变量直方图
    - 下三角：二维直方图（热图）
    - 上三角：空白

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

    注意
    -----
    - 本函数依赖 matplotlib 库
    - 对数刻度要求数据为正值，负值和零会被自动过滤
    - 大量数据点可能导致绘图速度较慢，建议使用合适的 bins 数量

    另见
    --------
    plot_waveforms : 波形时序可视化
    """
    if not MATPLOTLIB_AVAILABLE:
        raise ImportError("corner_hist 需要 matplotlib 库。\n" "安装方法：pip install matplotlib")

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
    mask = np.ones(length, dtype=bool)

    for x, r, scale in zip(data, ranges, scales, strict=False):
        mask &= np.isfinite(x)

        if r is not None:
            lo, hi = r
            mask &= (x >= lo) & (x <= hi)

        if scale == "log":
            mask &= x > 0

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
            return np.asarray(b)

        nbin = int(b)

        if r is not None:
            lo, hi = r
        else:
            lo, hi = np.nanmin(x), np.nanmax(x)

        if scale == "log":
            if lo <= 0:
                positive = x[x > 0]
                if len(positive) == 0:
                    raise ValueError("对数刻度要求正值，但未找到正值数据。")
                lo = np.nanmin(positive)

            return np.logspace(np.log10(lo), np.log10(hi), nbin)

        return np.linspace(lo, hi, nbin)

    bin_edges = [
        resolve_bins(x, b, r, scale)
        for x, b, r, scale in zip(data, bins, ranges, scales, strict=False)
    ]

    # 创建图形
    fig, axes = plt.subplots(
        n,
        n,
        figsize=(figsize_per_panel * n, figsize_per_panel * n),
        squeeze=False,
    )

    if hist2d_norm == "log":
        norm = LogNorm(vmin=hist2d_vmin, vmax=hist2d_vmax)
    else:
        norm = Normalize(vmin=hist2d_vmin, vmax=hist2d_vmax)

    for i in range(n):
        for j in range(n):
            ax = axes[i, j]

            x = data[j]
            y = data[i]

            xname = names[j]
            yname = names[i]

            xbins = bin_edges[j]
            ybins = bin_edges[i]

            xscale = scales[j]
            yscale = scales[i]

            if i < j:
                # 上三角：隐藏
                ax.axis("off")
                continue

            # 对角线：1D 直方图
            if i == j:
                ax.hist(
                    x,
                    bins=xbins,
                    weights=weights,
                    histtype="step",
                    linewidth=1.5,
                    color=hist_color,
                )

                ax.set_xscale(xscale)
                ax.set_yscale("log")

            # 下三角：2D 直方图
            else:
                H, xedges, yedges = np.histogram2d(
                    x,
                    y,
                    bins=[xbins, ybins],
                    weights=weights,
                )

                H = H.T
                H = np.ma.masked_less(H, min_count)

                mesh = ax.pcolormesh(
                    xedges,
                    yedges,
                    H,
                    cmap=cmap,
                    norm=norm if hist2d_norm == "log" else None,
                    shading="auto",
                )

                ax.set_xscale(xscale)
                ax.set_yscale(yscale)

                if add_colorbar:
                    fig.colorbar(mesh, ax=ax)

            # 标签
            if i == n - 1:
                ax.set_xlabel(xname)
            else:
                ax.set_xticklabels([])

            if j == 0 and i != j:
                ax.set_ylabel(yname)
            elif j != 0:
                ax.set_yticklabels([])

            ax.tick_params(axis="both", which="both", labelsize=8)

    if title is not None:
        fig.suptitle(title, y=1.02, fontsize=14)

    fig.tight_layout()
    return fig, axes
