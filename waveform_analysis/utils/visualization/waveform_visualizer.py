"""
波形可视化工具 - 专用波形浏览和分析界面

本模块提供波形数据的高级可视化功能，支持交互式浏览和分析。

主要功能:
- 单事件/多通道波形展示
- Hit/Peak 自动标注和高亮
- 交互式事件浏览器
- 支持自定义通道选择
- Plotly 驱动的响应式界面

可视化组件:
- plot_waveforms: 核心绘图函数
- 多子图布局：每个通道独立显示
- Hit 标记：在波形上显示检测到的峰值
- 工具栏：缩放、平移、导出图像

典型应用:
- 质量控制：快速检查波形形状
- Hit 验证：确认峰值检测正确性
- 数据探索：浏览不同事件的波形特征
- 报告生成：导出高质量的波形图像

Examples:
    >>> from waveform_analysis.utils.visualization.waveform_visualizer import plot_waveforms
    >>> import numpy as np
    >>> # 单结构化数组（含 channel 字段）
    >>> plot_waveforms(st_waveforms, event_index=5, channels=[0, 1])

Note:
    本模块需要 Plotly:
    pip install plotly
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
