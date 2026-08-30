"""
波形可视化工具 - 专用波形浏览和分析界面

本模块提供波形数据的高级可视化功能，支持交互式浏览和分析。

主要功能:
- 单事件/多通道波形展示
- Hit/Peak 自动标注和高亮
- 交互式事件浏览器
- 支持自定义通道选择
- Plotly 驱动的响应式界面
- Peak 多通道波形重建和求和显示

可视化组件:
- plot_waveforms: 核心绘图函数（Plotly 交互式）
- plot_peak_channels_with_sum: Peak 多通道波形展示（matplotlib）
- 多子图布局：每个通道独立显示
- Hit 标记：在波形上显示检测到的峰值
- 工具栏：缩放、平移、导出图像

典型应用:
- 质量控制：快速检查波形形状
- Hit 验证：确认峰值检测正确性
- Peak 重建：查看 peak 的多通道组成
- 数据探索：浏览不同事件的波形特征
- 报告生成：导出高质量的波形图像

Examples:
    >>> from waveform_analysis.utils.visualization.waveform_visualizer import plot_waveforms
    >>> import numpy as np
    >>> # 单结构化数组（含 channel 字段）
    >>> plot_waveforms(st_waveforms, event_index=5, channels=[0, 1])
    >>>
    >>> # Peak 多通道波形展示（简洁用法）
    >>> fig, axes = plot_peak_channels_with_sum(
    ...     peak_id=42,
    ...     context=context,
    ...     run_id="run_001",
    ... )
    >>>
    >>> # 批量绘制多个 peak（高效用法）
    >>> plot_func = create_peak_plotter(context=context, run_id="run_001")
    >>> for peak_id in [42, 43, 44]:
    ...     fig, axes = plot_func(peak_id=peak_id)

Note:
    - plot_waveforms 需要 Plotly: pip install plotly
    - plot_peak_channels_with_sum 需要 matplotlib
"""

import numpy as np

from waveform_analysis.core.hardware.channel import HardwareChannel


def _parse_channel_selector(channel: HardwareChannel | tuple[int, int] | str) -> HardwareChannel:
    if isinstance(channel, HardwareChannel):
        return channel
    if isinstance(channel, tuple) and len(channel) == 2:
        return HardwareChannel(int(channel[0]), int(channel[1]))
    if isinstance(channel, str) and ":" in channel:
        board, ch = channel.split(":", 1)
        return HardwareChannel(int(board.strip()), int(ch.strip()))
    raise ValueError(
        f"Invalid channel selector {channel!r}; expected HardwareChannel, (board, channel), "
        'or "board:channel".'
    )


def _channel_label(channel: HardwareChannel) -> str:
    return f"B{channel.board}:Ch{channel.channel}"


def plot_waveforms(
    waveforms: np.ndarray | list[np.ndarray],
    hits: np.ndarray | None = None,
    event_index: int = 0,
    channels: list[HardwareChannel | tuple[int, int] | str] | None = None,
    title: str = "Waveform Viewer",
):
    """
    Creates an interactive Plotly figure for browsing waveforms and peak annotations.

    Args:
        waveforms: List of numpy arrays (one per channel) or a single 2D array.
        hits: Optional structured array of peaks (HIT_DTYPE).
        event_index: The index of the event to display.
        channels: List of channel indices to show.
        title: Plot title.
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        print("Please install plotly: pip install plotly")
        return

    if isinstance(waveforms, np.ndarray) and waveforms.dtype.names is not None:
        if "channel" not in waveforms.dtype.names or "board" not in waveforms.dtype.names:
            raise ValueError("waveforms missing 'board'/'channel' fields")
        if channels is None:
            channels = sorted(
                {
                    HardwareChannel(int(board), int(ch))
                    for board, ch in zip(waveforms["board"], waveforms["channel"], strict=False)
                }
            )
        else:
            channels = [_parse_channel_selector(channel) for channel in channels]
        waveform_lookup = {
            hw_channel: waveforms[
                (waveforms["board"] == hw_channel.board)
                & (waveforms["channel"] == hw_channel.channel)
            ]
            for hw_channel in channels
        }
    else:
        if isinstance(waveforms, np.ndarray) and waveforms.ndim == 2:
            # Single channel case
            waveforms = [waveforms]
        if channels is None:
            channels = list(range(len(waveforms)))
        waveform_lookup = {ch: waveforms[ch] for ch in channels}

    fig = make_subplots(
        rows=len(channels),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=[
            _channel_label(ch) if isinstance(ch, HardwareChannel) else f"Channel {ch}"
            for ch in channels
        ],
    )

    for i, ch_idx in enumerate(channels):
        ch_waves = waveform_lookup.get(ch_idx)
        if ch_waves is None:
            continue
        if event_index >= len(ch_waves):
            continue

        wave = ch_waves[event_index]
        # If it's a structured array from WaveformStruct
        if hasattr(wave, "dtype") and "wave" in wave.dtype.names:
            y = wave["wave"]
            baseline = wave["baseline"]
        else:
            y = wave
            baseline = 0

        x = np.arange(len(y))

        # Plot waveform
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                name=(
                    _channel_label(ch_idx)
                    if isinstance(ch_idx, HardwareChannel)
                    else f"CH{ch_idx} Wave"
                ),
                line={"width": 1},
            ),
            row=i + 1,
            col=1,
        )

        # Plot baseline if available
        if baseline != 0:
            fig.add_trace(
                go.Scatter(
                    x=[0, len(y)],
                    y=[baseline, baseline],
                    name=(
                        f"{_channel_label(ch_idx)} Baseline"
                        if isinstance(ch_idx, HardwareChannel)
                        else f"CH{ch_idx} Baseline"
                    ),
                    line={"dash": "dash", "color": "gray"},
                ),
                row=i + 1,
                col=1,
            )

        # Plot peaks if available
        if hits is not None:
            # Filter peaks for this channel and event
            if isinstance(ch_idx, HardwareChannel):
                board_mask = hits["board"] == ch_idx.board if "board" in hits.dtype.names else True
                ch_hits = hits[
                    board_mask
                    & (hits["channel"] == ch_idx.channel)
                    & (hits["record_index"] == event_index)
                ]
            else:
                ch_hits = hits[(hits["channel"] == ch_idx) & (hits["record_index"] == event_index)]
            for hit in ch_hits:
                pos = int(hit["hit_sample_idx"]) if "hit_sample_idx" in hit.dtype.names else 0
                start = (
                    int(round(hit["hit_left_sample_idx"]))
                    if "hit_left_sample_idx" in hit.dtype.names
                    else pos
                )
                end = (
                    int(round(hit["hit_right_sample_idx"]))
                    if "hit_right_sample_idx" in hit.dtype.names
                    else pos
                )
                if end < start:
                    start, end = end, start
                start = max(0, start)
                end = min(len(y) - 1, end)
                y_peak = y[pos] if 0 <= pos < len(y) else baseline

                # Highlight peak region
                fig.add_vrect(
                    x0=start,
                    x1=end,
                    fillcolor="red",
                    opacity=0.2,
                    line_width=0,
                    row=i + 1,
                    col=1,
                )
                # Add marker for peak position
                fig.add_trace(
                    go.Scatter(
                        x=[pos],
                        y=[y_peak],
                        mode="markers",
                        marker={"color": "red", "symbol": "x"},
                        name=f"Peak @ {pos}",
                        showlegend=False,
                    ),
                    row=i + 1,
                    col=1,
                )

    fig.update_layout(
        height=300 * len(channels), title_text=f"{title} - Event {event_index}", showlegend=True
    )
    fig.update_xaxes(title_text="Sample Index")
    fig.update_yaxes(title_text="ADC")

    return fig


def create_interactive_browser(context, run_id: str):
    """
    Returns a function that can be used with ipywidgets.interact to browse events.
    """
    # This is intended for use in a Jupyter Notebook
    waveforms = context.get_data(run_id, "st_waveforms")
    hits = context.get_data(run_id, "hit")

    def browse(event_index=0):
        fig = plot_waveforms(waveforms, hits, event_index=event_index)
        fig.show()

    return browse


def _plot_peak_channels_with_sum_impl(
    peak_id,
    *,
    peaklet_components: np.ndarray,
    hit_merged: np.ndarray,
    hit_merged_components: np.ndarray,
    hit_threshold: np.ndarray,
    wave_pool: np.ndarray,
    record_lookup: dict,
    peaks_raw: np.ndarray,
    peaklet_waveforms: np.ndarray,
    peaklet_waveform_pool: np.ndarray,
    pad: int = 30,
    group_by: str = "board_channel",
):
    """
    内部实现：绘制 peak 的多通道波形（假设所有数据已经提供）。

    这是实际的绘图逻辑，由 plot_peak_channels_with_sum 和 create_peak_plotter 调用。
    用户通常不需要直接调用此函数。

    注意：sum waveform 直接使用 peaklet_waveforms 中已经计算好的求和波形，
    确保与 peak 特征计算时使用的波形一致。
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError(
            "plot_peak_channels_with_sum 需要 matplotlib。\n安装方法：pip install matplotlib"
        )

    # 获取属于该 peak 的所有 peaklet components
    comps = peaklet_components[peaklet_components["peak_id"] == int(peak_id)]
    merged_indices = comps["merged_index"].astype(int)
    hms = hit_merged[merged_indices]

    if len(hms) == 0:
        print(f"No hit_merged found for peak_id={peak_id}")
        return None, None

    def add_trace_from_record_window(
        traces,
        *,
        merged_index,
        hm,
        rec,
        sample_start,
        sample_end,
    ):
        """从 record 窗口提取波形片段并添加到 traces 列表"""
        dt_ns = int(rec["dt"])
        event_length = int(rec["event_length"])
        wave_offset = int(rec["wave_offset"])
        baseline = float(rec["baseline"])
        rec_t0 = int(rec["timestamp"])

        # 计算窗口范围（带 padding）
        s0 = max(0, int(sample_start) - pad)
        s1 = min(event_length, int(sample_end) + pad)
        if s1 <= s0:
            return

        # 提取原始波形
        raw = wave_pool[wave_offset + s0 : wave_offset + s1].astype(np.float32)

        # 根据极性计算信号
        polarity = str(rec["polarity"]) if "polarity" in rec.dtype.names else "negative"
        signal = raw - baseline if polarity == "positive" else baseline - raw

        # 计算绝对时间
        sample = np.arange(s0, s1)
        abs_time_ps = rec_t0 + sample * dt_ns * 1000

        # Hit 窗口的起止时间
        hit_start_ps = rec_t0 + int(sample_start) * dt_ns * 1000
        hit_end_ps = rec_t0 + int(sample_end) * dt_ns * 1000

        # 根据分组方式确定 key 和 label
        if group_by == "channel":
            key = int(hm["channel"])
            label = f"ch {key}"
        else:  # board_channel
            key = (int(hm["board"]), int(hm["channel"]))
            label = f"board {key[0]}, ch {key[1]}"

        traces.append(
            {
                "merged_index": int(merged_index),
                "key": key,
                "label": label,
                "abs_time_ps": abs_time_ps,
                "signal": signal,
                "hit_start_ps": hit_start_ps,
                "hit_end_ps": hit_end_ps,
                "dt_ns": dt_ns,
            }
        )

    traces = []

    # 遍历所有 hit_merged，提取波形
    for merged_index, hm in zip(merged_indices, hms, strict=False):
        sample_start = int(hm["sample_start"])
        sample_end = int(hm["sample_end"])

        # 检查是否为单 record 的 hit
        is_single_record = (
            bool(hm["is_single_record"])
            if "is_single_record" in hit_merged.dtype.names
            else sample_start >= 0 and sample_end >= 0
        )

        if is_single_record and sample_start >= 0 and sample_end >= 0:
            # 单 record hit，直接从 record 提取
            rec = record_lookup.get(int(hm["record_id"]))
            if rec is None:
                continue
            add_trace_from_record_window(
                traces,
                merged_index=merged_index,
                hm=hm,
                rec=rec,
                sample_start=sample_start,
                sample_end=sample_end,
            )
            continue

        # 跨 record 的 hit，需要从组件中提取
        hmc = hit_merged_components[hit_merged_components["merged_index"] == int(merged_index)]
        hit_indices = hmc["hit_index"].astype(int)
        hits = hit_threshold[hit_indices]

        for hit in hits:
            rec = record_lookup.get(int(hit["record_id"]))
            if rec is None:
                continue
            add_trace_from_record_window(
                traces,
                merged_index=merged_index,
                hm=hm,
                rec=rec,
                sample_start=int(hit["edge_start"]),
                sample_end=int(hit["edge_end"]),
            )

    if len(traces) == 0:
        print(f"No drawable waveform windows found for peak_id={peak_id}")
        return None, None

    # 计算相对时间（以事件最早时间为基准）
    event_t0 = min(int(t["abs_time_ps"][0]) for t in traces)

    for t in traces:
        t["time_ns"] = (t["abs_time_ps"] - event_t0) / 1000.0
        t["hit_start_ns"] = (t["hit_start_ps"] - event_t0) / 1000.0
        t["hit_end_ns"] = (t["hit_end_ps"] - event_t0) / 1000.0

    # 准备颜色映射
    keys = sorted({t["key"] for t in traces})
    cmap = plt.get_cmap("tab20", max(len(keys), 1))
    colors = {key: cmap(i) for i, key in enumerate(keys)}

    # 从 peaklet_waveforms 获取已经计算好的 sum waveform
    peaklet_waveform = peaklet_waveforms[peaklet_waveforms["peak_id"] == int(peak_id)]

    if len(peaklet_waveform) == 0:
        print(f"No peaklet_waveform found for peak_id={peak_id}")
        return None, None

    wf = peaklet_waveform[0]
    wave_offset = int(wf["wave_offset"])
    wave_length = int(wf["wave_length"])
    dt = int(wf["dt"])
    time_start_ps = int(wf["time_start"])

    # 提取求和波形
    sum_waveform = peaklet_waveform_pool[wave_offset : wave_offset + wave_length]

    # 计算求和波形的时间轴（使用事件最早时间为基准）
    event_t0 = min(int(t["abs_time_ps"][0]) for t in traces)
    sum_time_ns = (time_start_ps - event_t0) / 1000.0 + np.arange(wave_length) * dt

    # 计算 x 轴范围（包含所有通道的时间范围）
    t_min = min(t["time_ns"][0] for t in traces)
    t_max = max(t["time_ns"][-1] for t in traces)

    # 创建图形：第一行为求和波形（高度 2.5 倍），其余为各通道
    fig, axes = plt.subplots(
        len(keys) + 1,
        1,
        figsize=(16, max(7, 0.8 * len(keys) + 3.0)),
        sharex=True,
        squeeze=False,
        gridspec_kw={"height_ratios": [2.5] + [1] * len(keys)},
    )
    axes = axes.flatten()

    # 第一个子图：求和波形（使用 peaklet waveform）
    ax_sum = axes[0]
    ax_sum.plot(sum_time_ns, sum_waveform, color="k", lw=1.5)
    n_hits = int(peaks_raw[int(peak_id)]["n_hits"]) if int(peak_id) < len(peaks_raw) else "?"
    ax_sum.set_title(f"peak_id={peak_id}, summed waveform (from peaklet), peaks.n_hits={n_hits}")
    ax_sum.set_ylabel("sum signal")
    ax_sum.grid(True, alpha=0.3)

    # 记录已标记的 merged_index（避免重复标签）
    labeled_merged_indices = set()

    # 其余子图：各通道波形
    for ax, key in zip(axes[1:], keys, strict=False):
        channel_traces = [t for t in traces if t["key"] == key]
        color = colors[key]

        for t in channel_traces:
            # 绘制波形
            ax.plot(t["time_ns"], t["signal"], color=color, lw=1.2)
            # 高亮 hit 窗口
            ax.axvspan(t["hit_start_ns"], t["hit_end_ns"], color=color, alpha=0.15)

            # 标记 merged_index（每个 index 只标记一次）
            merged_index = int(t["merged_index"])
            if merged_index not in labeled_merged_indices and len(t["signal"]):
                ax.text(
                    0.5 * (t["hit_start_ns"] + t["hit_end_ns"]),
                    np.nanmax(t["signal"]),
                    str(merged_index),
                    color=color,
                    fontsize=8,
                    ha="center",
                    va="bottom",
                )
                labeled_merged_indices.add(merged_index)

        ax.set_ylabel(channel_traces[0]["label"])
        ax.grid(True, alpha=0.3)

    # 设置 x 轴
    axes[-1].set_xlabel("Time from event start (ns)")
    axes[-1].set_xlim(t_min, t_max)

    plt.tight_layout()
    plt.show()

    return fig, axes


def create_peak_plotter(context, run_id: str):
    """
    创建一个预加载数据的 peak 绘图函数，适用于批量绘制多个 peak。

    此函数预先从 context 加载所有需要的数据（一次性），然后返回一个
    快速的绘图函数。适合在循环中绘制多个 peak，避免重复加载数据。

    参数
    ----------
    context : Context
        DAQAnalyzer 的 context 对象。
    run_id : str
        Run ID。

    返回
    -------
    plot_func : callable
        预加载数据的绘图函数，签名为：
        plot_func(peak_id, pad=30, group_by="board_channel") -> (fig, axes)

    示例
    --------
    >>> # 批量绘制（推荐用法，快速）
    >>> plot_func = create_peak_plotter(context=ctx, run_id=run_id)
    >>> for peak_id in [42, 43, 44]:
    ...     fig, axes = plot_func(peak_id=peak_id)
    >>>
    >>> # 等价于但比下面的方式快得多：
    >>> for peak_id in [42, 43, 44]:
    ...     fig, axes = plot_peak_channels_with_sum(
    ...         peak_id=peak_id, context=ctx, run_id=run_id
    ...     )  # 每次都重新加载数据（慢）

    注意
    -----
    - 预先加载的数据包括：peaklet_components, hit_merged, hit_merged_components,
      hit_threshold, wave_pool, records, peaks, peaklet_waveforms, peaklet_waveform_pool
    - 返回的函数会保持对这些数据的引用，内存占用会持续到函数对象被释放
    """
    # 预先加载所有数据（只加载一次）
    print(f"预加载数据 from run_id={run_id}...")
    peaklet_components = context.get_data(run_id, "peaklet_components")
    hit_merged = context.get_data(run_id, "hit_merged")
    hit_merged_components = context.get_data(run_id, "hit_merged_components")
    hit_threshold = context.get_data(run_id, "hit_threshold")
    wave_pool = context.get_data(run_id, "wave_pool")
    records = context.get_data(run_id, "records")
    peaks_raw = context.get_data(run_id, "peaks")
    peaklet_waveforms = context.get_data(run_id, "peaklet_waveforms")
    peaklet_waveform_pool = context.get_data(run_id, "peaklet_waveform_pool")
    record_lookup = {int(rec["record_id"]): rec for rec in records}
    print("数据加载完成，可以开始快速绘图")

    def plot_func(peak_id, pad: int = 30, group_by: str = "board_channel"):
        """快速绘制 peak 的多通道波形（数据已预加载）"""
        return _plot_peak_channels_with_sum_impl(
            peak_id=peak_id,
            peaklet_components=peaklet_components,
            hit_merged=hit_merged,
            hit_merged_components=hit_merged_components,
            hit_threshold=hit_threshold,
            wave_pool=wave_pool,
            record_lookup=record_lookup,
            peaks_raw=peaks_raw,
            peaklet_waveforms=peaklet_waveforms,
            peaklet_waveform_pool=peaklet_waveform_pool,
            pad=pad,
            group_by=group_by,
        )

    return plot_func


def plot_peak_channels_with_sum(
    peak_id,
    *,
    context,
    run_id: str,
    pad: int = 30,
    group_by: str = "board_channel",
):
    """
    绘制指定 peak 的多通道波形及其求和波形。

    此函数重建 peak 的所有组成通道波形，并在顶部显示求和波形，
    每个通道独立显示在自己的子图中。所有需要的数据会自动从 context 获取。

    参数
    ----------
    peak_id : int
        要可视化的 peak ID。
    context : Context
        DAQAnalyzer 的 context 对象，用于获取所有需要的数据。
    run_id : str
        Run ID。
    pad : int, default=30
        在 hit 边界外扩展的采样点数。
    group_by : {"channel", "board_channel"}, default="board_channel"
        通道分组方式：
        - "channel": 按通道号分组
        - "board_channel": 按 (板号, 通道号) 分组

    返回
    -------
    fig : matplotlib.figure.Figure or None
        生成的图形对象，如果没有数据则返回 None。
    axes : numpy.ndarray or None
        子图轴对象数组，如果没有数据则返回 None。

    示例
    --------
    >>> # 单次调用（简洁）
    >>> fig, axes = plot_peak_channels_with_sum(
    ...     peak_id=42,
    ...     context=context,
    ...     run_id="run_001",
    ... )
    >>>
    >>> # 批量调用（推荐使用 create_peak_plotter）
    >>> plot_func = create_peak_plotter(context=ctx, run_id=run_id)
    >>> for peak_id in [42, 43, 44]:
    ...     fig, axes = plot_func(peak_id=peak_id)

    注意
    -----
    - 需要 matplotlib 库
    - 波形按时间对齐，使用事件内的相对时间（纳秒）
    - **sum waveform 直接使用 peaklet_waveforms 中已经计算好的求和波形**
    - merged_index 标签显示在每个 hit 窗口上方
    - **批量绘制多个 peak 时，使用 create_peak_plotter() 可以显著提高性能**
    """
    # 从 context 获取所有需要的数据
    peaklet_components = context.get_data(run_id, "peaklet_components")
    hit_merged = context.get_data(run_id, "hit_merged")
    hit_merged_components = context.get_data(run_id, "hit_merged_components")
    hit_threshold = context.get_data(run_id, "hit_threshold")
    wave_pool = context.get_data(run_id, "wave_pool")
    records = context.get_data(run_id, "records")
    peaks_raw = context.get_data(run_id, "peaks")
    peaklet_waveforms = context.get_data(run_id, "peaklet_waveforms")
    peaklet_waveform_pool = context.get_data(run_id, "peaklet_waveform_pool")
    record_lookup = {int(rec["record_id"]): rec for rec in records}

    return _plot_peak_channels_with_sum_impl(
        peak_id=peak_id,
        peaklet_components=peaklet_components,
        hit_merged=hit_merged,
        hit_merged_components=hit_merged_components,
        hit_threshold=hit_threshold,
        wave_pool=wave_pool,
        record_lookup=record_lookup,
        peaks_raw=peaks_raw,
        peaklet_waveforms=peaklet_waveforms,
        peaklet_waveform_pool=peaklet_waveform_pool,
        pad=pad,
        group_by=group_by,
    )
