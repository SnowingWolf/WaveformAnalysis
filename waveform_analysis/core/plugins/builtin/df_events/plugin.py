"""GroupedEventsPlugin 类实现 - 按时间窗口分组多通道事件。"""

from typing import Any

from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.plugins.core.spec import OutputSchema


class GroupedEventsPlugin(Plugin):
    """Plugin to group events by time window."""

    provides = "df_events"
    depends_on = ["df"]
    description = "Group events across channels within a configurable time window."
    version = "0.0.1"
    output_schema = OutputSchema(kind="dataframe", doc="Grouped multi-channel event table.")
    save_when = "always"
    options = {
        "time_window_ns": Option(
            default=100.0,
            type=float,
            help="Maximum time separation in nanoseconds for grouping events.",
        ),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        """
        按时间窗口分组多通道事件

        在指定的时间窗口内识别多通道同时触发的事件，并将它们分组。
        支持 Numba 加速和多进程并行处理。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 df

        Returns:
            pd.DataFrame: 分组后的事件

        Examples:
            >>> df_events = ctx.get_data('run_001', 'df_events')
            >>> print(f"事件组数: {df_events['event_id'].nunique()}")
        """
        from waveform_analysis.core.processing.analyzer import EventAnalyzer

        df = context.get_data(run_id, "df")
        tw = context.get_config(self, "time_window_ns")

        # We need n_channels and start_channel_slice from context config
        n_channels = context.config.get("n_channels", 2)
        start_channel_slice = context.config.get("start_channel_slice", 6)

        analyzer = EventAnalyzer(n_channels=n_channels, start_channel_slice=start_channel_slice)
        # 从context配置中获取优化参数（如果存在）
        use_numba = context.config.get("use_numba", True)
        n_processes = context.config.get("n_processes", None)
        return analyzer.group_events(df, tw, use_numba=use_numba, n_processes=n_processes)


__all__ = ["GroupedEventsPlugin"]
