"""
通用可视化工具 - 交互式波形和事件浏览器

本模块提供基于 Plotly 的交互式波形可视化工具。

主要功能:
- 多通道波形的交互式绘图
- Hit/Peak 事件的高亮显示
- 支持事件索引浏览
- 自动布局和通道分组
- 响应式交互（缩放、平移、悬停）

可视化特性:
- 子图布局：每个通道独立显示，共享 X 轴
- Hit 标记：自动在波形上标记检测到的 Hit
- 交互式控制：Plotly 工具栏支持缩放、导出等操作
- 自定义样式：可配置标题、颜色、布局

Examples:
    >>> from waveform_analysis.utils.visualization.visulizer import plot_waveforms
    >>> waveforms = [ch0_waves, ch1_waves]  # 每个通道的波形数组
    >>> plot_waveforms(waveforms, event_index=0, title="Run 001")

Note:
    需要安装 Plotly:
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
        fig.add_trace(
            go.Scatter(x=x, y=y, name=f"CH{ch_idx} Wave", line={"width": 1}), row=i + 1, col=1
        )

        # Plot baseline if available
        if baseline != 0:
            fig.add_trace(
                go.Scatter(
                    x=[0, len(y)],
                    y=[baseline, baseline],
                    name=f"CH{ch_idx} Baseline",
                    line={"dash": "dash", "color": "gray"},
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
                        marker={"color": "red", "symbol": "x"},
                        name=f"Hit @ {hit['time']}",
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
    hits = context.get_data(run_id, "hits")

    def browse(event_index=0):
        fig = plot_waveforms(waveforms, hits, event_index=event_index)
        fig.show()

    return browse
