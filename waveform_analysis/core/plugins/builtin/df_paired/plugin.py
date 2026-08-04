"""PairedEventsPlugin 类实现 - 配对跨通道符合事件。"""

from typing import Any

from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.core.plugins.core.spec import OutputSchema


class PairedEventsPlugin(Plugin):
    """Plugin to pair events across channels."""

    provides = "df_paired"
    depends_on = ["df_events"]
    description = "Pair grouped events across channels for coincidence analysis."
    version = "0.0.1"
    output_schema = OutputSchema(kind="dataframe", doc="Paired coincidence event table.")
    save_when = "always"

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        """
        配对跨通道的符合事件

        识别满足时间符合条件的多通道事件对，用于符合测量分析。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 df_events

        Returns:
            pd.DataFrame: 配对事件

        Examples:
            >>> df_paired = ctx.get_data('run_001', 'df_paired')
            >>> print(f"配对数: {len(df_paired)}")
        """
        from waveform_analysis.core.processing.analyzer import EventAnalyzer

        df_events = context.get_data(run_id, "df_events")

        n_channels = context.config.get("n_channels", 2)
        start_channel_slice = context.config.get("start_channel_slice", 6)
        time_window_ns = context.config.get("time_window_ns", 100.0)  # 从配置获取时间窗口

        analyzer = EventAnalyzer(n_channels=n_channels, start_channel_slice=start_channel_slice)
        return analyzer.pair_events(df_events, time_window_ns=time_window_ns)


__all__ = ["PairedEventsPlugin"]
