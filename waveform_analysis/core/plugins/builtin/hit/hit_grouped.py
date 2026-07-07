"""
Hit Grouped Plugin - Hit 分组插件

**加速器**: CPU (NumPy/Numba)
**功能**: 按绝对 hit 窗口将多通道的 merged hits 分组为事件级符合窗口

本插件将 hit_merged 数据按时间窗口分组，用于事件级分析。
已标记为 deprecated，推荐使用新的 S1-S2 配对工作流。
"""

from typing import Any

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import (
    require_dt_array,
    resolve_dt_config,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.event_grouping import group_hit_windows


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
