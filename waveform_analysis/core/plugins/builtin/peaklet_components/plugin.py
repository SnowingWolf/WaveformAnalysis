"""peaklet_components bundle - provides 'peaklet_components'。"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.peaklets._compute import (
    PEAKLET_COMPONENTS_DTYPE,
    _cluster_merged_hit_boundaries,
    _empty_components,
    _fill_peaklet_components_numba,
    _resolve_peaklet_component_config,
)
from waveform_analysis.core.plugins.core.base import Option
from waveform_analysis.core.plugins.core.batch_processing import BatchProcessingPlugin
from waveform_analysis.core.processing.chunk import Chunk


class PeakletComponentsPlugin(BatchProcessingPlugin):
    """Return flat peaklet-to-hit_merged membership rows."""

    provides = "peaklet_components"
    lineage_virtual = True
    depends_on = ["hit_merged"]
    description = "Return per-peaklet component hit_merged indices."
    version = "1.4.0"
    output_dtype = PEAKLET_COMPONENTS_DTYPE
    save_when = "always"
    parallel = False

    options = {
        "time_window_ns": Option(default=100.0, type=float, help="跨通道 peaklet 合并时间窗口"),
        "max_total_width_ns": Option(default=10000.0, type=float, help="peaklet 最大总宽度"),
        "dt": Option(default=None, type=int, help="保留兼容配置；优先使用输入 hit_merged 的 dt"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        return self.compute_array(context, run_id, **kwargs)

    def compute_array(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("peaklet_components expects hit_merged as a structured array")
        if len(merged) == 0:
            return _empty_components()

        time_window_ns = float(_resolve_peaklet_component_config(context, self, "time_window_ns"))
        max_total_width_ns = float(
            _resolve_peaklet_component_config(context, self, "max_total_width_ns")
        )
        resolve_dt_config(context, self, deprecated_keys=("sampling_interval_ns", "dt_ns"))
        order, cluster_starts, cluster_ends = _cluster_merged_hit_boundaries(
            merged,
            time_window_ns=time_window_ns,
            max_total_width_ns=max_total_width_ns,
        )
        out = np.empty(len(order), dtype=PEAKLET_COMPONENTS_DTYPE)
        _fill_peaklet_components_numba(
            order,
            cluster_starts,
            cluster_ends,
            out["peak_id"],
            out["merged_index"],
        )
        return out

    def get_lineage(self, context: Any, *, dependency_resolver=None) -> dict[str, Any]:
        config = {
            "time_window_ns": _resolve_peaklet_component_config(context, self, "time_window_ns"),
            "max_total_width_ns": _resolve_peaklet_component_config(
                context, self, "max_total_width_ns"
            ),
            "dt": _resolve_peaklet_component_config(context, self, "dt"),
        }
        return {
            "plugin_class": self.__class__.__name__,
            "plugin_version": self.version,
            "description": self.description,
            "config": config,
            "depends_on": {
                "hit_merged": (dependency_resolver or context.get_lineage)("hit_merged")
            },
        }

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        components = self.compute_array(context, run_id, **kwargs)
        return Chunk(
            data=components,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )


__all__ = ["PeakletComponentsPlugin"]
