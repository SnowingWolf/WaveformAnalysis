"""peaklets bundle - provides 'peaklets'。"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.peaklets._compute import (
    PEAKLET_DTYPE,
    _abs_window,
    _empty_peaklets,
    _prepare_component_groups,
    _summarize_peaklets_numba,
)
from waveform_analysis.core.plugins.core.base import Option
from waveform_analysis.core.plugins.core.batch_processing import BatchProcessingPlugin
from waveform_analysis.core.processing.chunk import Chunk


class PeakletPlugin(BatchProcessingPlugin):
    """Build lightweight cross-channel peaklet candidates from hit_merged rows."""

    provides = "peaklets"
    depends_on = ["hit_merged", "peaklet_components"]
    description = "Build lightweight cross-channel peaklets from hit_merged intervals."
    version = "1.2.0"
    output_dtype = PEAKLET_DTYPE
    save_when = "always"
    parallel = False
    agent_doc = {
        "overview": (
            "PeakletPlugin 负责在 hit_merged 与 peaklet_components 之上构建轻量级的跨通道 "
            "peaklet 候选对象。它本身不检测峰形，而是按 peaklet_components 提供的成员关系，"
            "把同一逻辑事件（可能横跨多个 (board, channel) 的 hit_merged 行）聚合为一条 "
            "peaklet 记录，并汇总出绝对时间范围、参与 hit 数与去重后的通道数。\n\n"
            "该插件是 hit 层与 peak 层之间的桥梁：下游的 peaklet_features 特征计算、"
            "peaklet_waveforms / peaklet_waveform_pool 波形还原以及最终的 peaks 表都以 "
            "peaklets 的行索引作为 peak_id，因此本插件的行序与 peak_id 约定是后续所有 "
            "peaklet 消费插件对齐的基础。\n\n"
            "实现上先按 peak_id 建立分组成员表并校验组件引用的合法性，再调用 Numba 聚合内核 "
            "`_summarize_peaklets_numba` 单次遍历完成时间范围、n_hits 与 n_channels 的汇总，"
            "输出为按行对齐的 PEAKLET_DTYPE 结构化数组。"
        ),
        "workflow_steps": [
            "读取输入：从 context 获取 `hit_merged` 与 `peaklet_components` 结构化数组；任一为空时直接返回空 peaklets 数组。",
            "推导 peaklet 数量：以 `peaklet_components['peak_id']` 的最大值加 1 作为 n_peaklets，不依赖外部计数状态。",
            "校验组件引用：调用 `_prepare_component_groups` 按 peak_id 建立分组成员表，并确保每个 `merged_index` 都落在 `hit_merged` 的行范围内，越界即抛错。",
            "计算绝对时间窗口：由 `hit_merged` 的时间戳与采样窗口推导每条记录的绝对起止时间（`_abs_window`），供跨通道聚合使用。",
            "聚合摘要：通过 Numba 内核 `_summarize_peaklets_numba` 对每组组件汇总最小/最大绝对时间、`n_hits` 与去重后的 `n_channels`，并连续记录成员在 `peaklet_components` 中的 `component_offset` 与 `component_count`。",
            "写回输出：返回按 `peak_id`（行序）排序的 `PEAKLET_DTYPE` 结构化数组。",
        ],
        "behavior_notes": [
            "Only `peaklet_components` row membership matters; per-channel hit details are not preserved here and are re-derived downstream via `peaklet_channels`.",
            "`time_start`/`time_end` are the min/max of member absolute windows and `center_time` is their midpoint `(time_start + time_end) // 2`.",
            "`n_hits` sums `hit_merged['component_count']` when present, otherwise counts members one by one; `n_channels` counts distinct `(board, channel)` pairs among members.",
            "`component_offset` accumulates contiguously across peaklets, so it points exactly into `peaklet_components`.",
            "Empty `peaklet_components` or non-positive peak-id range produce an empty `PEAKLET_DTYPE` array rather than an error.",
            "`dt` config is a compatibility fallback resolved via `resolve_dt_config`; the effective sample interval is taken from `hit_merged` when available.",
        ],
        "field_notes": {
            "time_start": "The earliest absolute start time (ps) across all member components.",
            "time_end": "The latest absolute end time (ps) across all member components.",
            "center_time": "Midpoint of `time_start` and `time_end` (ps).",
            "n_hits": "Total hit count aggregated over members (from `hit_merged['component_count']` when present).",
            "n_channels": "Count of distinct `(board, channel)` pairs among members.",
            "component_offset": "Start row in `peaklet_components` for this peaklet's contiguous membership rows.",
            "component_count": "Number of contiguous `peaklet_components` membership rows for this peaklet.",
        },
        "config_notes": {
            "time_window_ns": "跨通道 peaklet 合并时间窗口（ns）。由上游 peaklet_components 消费并判定成员关系；本插件只消费其分组结果。",
            "max_total_width_ns": "peaklet 最大总宽度（ns），限制链式合并总时长；同样由 peaklet_components 消费。",
            "dt": "兼容性采样间隔（ns）回退配置，仅在输入缺少 dt 时使用；优先采用 `hit_merged` 的 dt。",
        },
        "failure_modes": [
            "`hit_merged` 不是结构化数组时抛出 `ValueError`。",
            "`peaklet_components` 不是结构化数组时抛出 `ValueError`。",
            "存在 `peaklet_components` 行的 `merged_index` 越界（超出 `hit_merged` 行范围）时抛出 `ValueError`。",
            "`peaklet_id` 分组不连续或成员索引错乱时，`component_offset`/`component_count` 指向的成员切片会失真，下游 `peaklet_channels` 的一致性校验将失败。",
        ],
        "downstream_consumers": [
            "peaklet_channels",
            "peaklet_features",
            "peaklet_waveforms",
            "peaks",
        ],
        "downstream_notes": [
            "`peaks` 直接以 peaklets 的行序作为 `peak_id`，任何行序或 `component_offset`/`component_count` 变更都会传播到最终 peaks 表。",
            "`peaklet_channels` 会校验成员数与 `peaklet_components` 的一致性，因此本插件的成员关系语义必须与 peaklet_components 保持同步。",
        ],
        "agent_change_notes": [
            "聚合字段语义或 `component_offset`/`component_count` 的变化会级联影响 `peaklet_channels`、`peaklet_features`、`peaklet_waveforms` 与 `peaks` 的消费逻辑。",
            "修改后请运行 peaklets 相关定向测试（test_peaklets_plugin 等）并重新生成 agent 文档。",
        ],
    }

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
            raise ValueError("peaklets expects hit_merged as a structured array")
        if len(merged) == 0:
            return _empty_peaklets()
        components = context.get_data(run_id, "peaklet_components")
        if not isinstance(components, np.ndarray):
            raise ValueError("peaklets expects peaklet_components as a structured array")

        return self._compute_peaklets(merged=merged, components=components, context=context)

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        components = context.get_data(run_id, "peaklet_components")
        if not isinstance(components, np.ndarray):
            raise ValueError("peaklets expects peaklet_components as a structured array")
        peaklets = self._compute_peaklets(merged=chunk.data, components=components, context=context)
        return Chunk(
            data=peaklets,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )

    def _compute_peaklets(
        self, *, merged: np.ndarray, components: np.ndarray, context: Any
    ) -> np.ndarray:
        resolve_dt_config(context, self, deprecated_keys=("sampling_interval_ns", "dt_ns"))
        if len(components) == 0:
            return _empty_peaklets()

        n_peaklets = int(np.max(components["peak_id"])) + 1
        if n_peaklets <= 0:
            return _empty_peaklets()

        grouped_merged_indices, group_starts, group_ends = _prepare_component_groups(
            components, n_peaklets
        )
        if np.any(grouped_merged_indices < 0) or np.any(grouped_merged_indices >= len(merged)):
            raise ValueError("peaklets found peaklet_components row with out-of-range merged_index")

        abs_starts, abs_ends = _abs_window(merged)
        merged_names = merged.dtype.names or ()
        boards = (
            merged["board"].astype(np.int64, copy=False)
            if "board" in merged_names
            else np.zeros(len(merged), dtype=np.int64)
        )
        channels = merged["channel"].astype(np.int64, copy=False)
        has_component_counts = "component_count" in merged_names
        component_counts = (
            merged["component_count"].astype(np.int64, copy=False)
            if has_component_counts
            else np.empty(0, dtype=np.int64)
        )

        out = np.zeros(n_peaklets, dtype=PEAKLET_DTYPE)
        _summarize_peaklets_numba(
            grouped_merged_indices,
            group_starts,
            group_ends,
            abs_starts,
            abs_ends,
            boards,
            channels,
            component_counts,
            has_component_counts,
            out,
        )
        return out


__all__ = ["PeakletPlugin"]
