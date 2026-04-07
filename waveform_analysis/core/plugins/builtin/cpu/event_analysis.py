"""
Event Analysis Plugins - 事件分组与配对插件

**加速器**: CPU (NumPy/Numba)
**功能**: 多通道事件的时间窗口分组和符合配对

本模块包含三个相关的事件分析插件：
- GroupedEventsPlugin: 按时间窗口分组多通道事件
- HitGroupedPlugin: 按 hit 窗口分组多通道 hit_merged 事件
- PairedEventsPlugin: 配对跨通道的符合事件
"""

from typing import Any

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import (
    require_dt_array,
    resolve_dt_config,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.event_grouping import group_hit_windows


class GroupedEventsPlugin(Plugin):
    """Plugin to group events by time window."""

    provides = "df_events"
    depends_on = ["df"]
    description = "Group events across channels within a configurable time window."
    save_when = "always"
    options = {
        "time_window_ns": Option(default=100.0, type=float),
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


class HitGroupedPlugin(Plugin):
    """Plugin to group merged hits across channels using absolute hit windows."""

    provides = "hit_grouped"
    depends_on = ["hit_merged", "hit_merged_components", "hit_threshold"]
    description = "Group merged hits across channels into event-level coincidence windows."
    version = "0.5.0"
    save_when = "always"
    options = {
        "time_window_ns": Option(default=100.0, type=float),
        "dt": Option(
            default=None,
            type=int,
            help="采样间隔（ns）。仅在输入 hit_merged 缺少 dt 字段时作为兼容补充。",
        ),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        hits = context.get_data(run_id, "hit_merged")
        component_rows = context.get_data(run_id, "hit_merged_components")
        component_hits = context.get_data(run_id, "hit_threshold")
        time_window_ns = float(context.get_config(self, "time_window_ns"))
        explicit_dt = resolve_dt_config(
            context, self, deprecated_keys=("sampling_interval_ns", "dt_ns")
        )
        dt_values = require_dt_array(
            hits,
            explicit_dt=explicit_dt,
            plugin_name=self.provides,
            data_name="hit_merged",
        )
        return group_hit_windows(
            hits,
            time_window_ns=time_window_ns,
            dt_values=dt_values,
            component_rows=component_rows,
            component_hits=component_hits,
        )


class PairedEventsPlugin(Plugin):
    """Plugin to pair events across channels."""

    provides = "df_paired"
    depends_on = ["df_events"]
    description = "Pair grouped events across channels for coincidence analysis."
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
