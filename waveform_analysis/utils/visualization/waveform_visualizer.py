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
    >>> waveforms = [np.random.randn(100, 500) for _ in range(2)]
    >>> plot_waveforms(waveforms, event_index=5, channels=[0, 1])

Note:
    本模块需要 Plotly:
    pip install plotly
"""
from typing import List, Optional, Union

import numpy as np


def plot_waveforms(
    waveforms: Union[np.ndarray, List[np.ndarray]],
    hits: Optional[np.ndarray] = None,
    event_index: int = 0,
    channels: Optional[List[int]] = None,
    title: str = "Waveform Viewer",
):
    """
    Creates an interactive Plotly figure for browsing waveforms and hits.

    Args:
        waveforms: List of numpy arrays (one per channel) or a single 2D array.
        hits: Optional structured array of hits (PEAK_DTYPE).
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

    if isinstance(waveforms, np.ndarray) and waveforms.ndim == 2:
        # Single channel case
        waveforms = [waveforms]

    if channels is None:
        channels = list(range(len(waveforms)))

    fig = make_subplots(
        rows=len(channels),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=[f"Channel {ch}" for ch in channels],
    )

    for i, ch_idx in enumerate(channels):
        ch_waves = waveforms[ch_idx]
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
        fig.add_trace(go.Scatter(x=x, y=y, name=f"CH{ch_idx} Wave", line=dict(width=1)), row=i + 1, col=1)

        # Plot baseline if available
        if baseline != 0:
            fig.add_trace(
                go.Scatter(
                    x=[0, len(y)],
                    y=[baseline, baseline],
                    name=f"CH{ch_idx} Baseline",
                    line=dict(dash="dash", color="gray"),
                ),
                row=i + 1,
                col=1,
            )

        # Plot hits if available
        if hits is not None:
            # Filter hits for this channel and event
            ch_hits = hits[(hits["channel"] == ch_idx) & (hits["event_index"] == event_index)]
            for hit in ch_hits:
                # Highlight hit area
                fig.add_vrect(
                    x0=hit["time"],
                    x1=hit["time"] + hit["width"],
                    fillcolor="red",
                    opacity=0.2,
                    line_width=0,
                    row=i + 1,
                    col=1,
                )
                # Add marker for peak
                fig.add_trace(
                    go.Scatter(
                        x=[hit["time"] + hit["width"] / 2],
                        y=[hit["height"] + baseline],
                        mode="markers",
                        marker=dict(color="red", symbol="x"),
                        name=f"Hit @ {hit['time']}",
                        showlegend=False,
                    ),
                    row=i + 1,
                    col=1,
                )

    fig.update_layout(height=300 * len(channels), title_text=f"{title} - Event {event_index}", showlegend=True)
    fig.update_xaxes(title_text="Sample Index")
    fig.update_yaxes(title_text="ADC")

    return fig


def create_interactive_browser(context, run_id: str):
    """
    Returns a function that can be used with ipywidgets.interact to browse events.
    """
    # This is intended for use in a Jupyter Notebook
    waveforms = context.get_data(run_id, "st_waveforms")
    hits = context.get_data(run_id, "hits")

    def browse(event_index=0):
        fig = plot_waveforms(waveforms, hits, event_index=event_index)
        fig.show()

    return browse
