"""HitMergePlugin 类实现 - 合并临近 hit（同通道，允许跨波形/跨文件）。"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.hit_merged._compute import (
    HIT_MERGED_DTYPE,
    _build_enriched_for_hits,
    _build_merged_from_cluster_rows,
    _compute_canonical_cluster_rows,
    _hits_to_merged_fast,
    _materialize_array,
)
from waveform_analysis.core.plugins.builtin.hit_threshold import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.core.base import Option
from waveform_analysis.core.plugins.core.batch_processing import BatchProcessingPlugin


class HitMergePlugin(BatchProcessingPlugin):
    """Merge nearby hits from hit_threshold within the same channel."""

    provides = "hit_merged"
    depends_on = ["hit_threshold"]
    description = "Merge nearby threshold hits per channel with time-gap and max-width constraints."
    version = "2.1.0"
    save_when = "always"
    output_dtype = HIT_MERGED_DTYPE
    agent_doc = {
        "overview": (
            "HitMergePlugin 是波形分析中最核心的后处理插件之一，负责将 hit_threshold "
            "产出的过阈 hit 按时间邻近性合并为统一的 hit_merged 记录。它不直接修改原始 "
            "hit_threshold 数据，而是生成新的结构化输出，同时提供 cluster 级别的成员关系"
            "（hit_merge_clusters）供下游诊断使用。\n\n"
            "该插件由三部分协同工作：HitMergePlugin（主合并逻辑）、HitMergeClustersPlugin"
            "（导出 cluster 成员关系）和 HitMergedComponentsPlugin（验证与展开 component）。"
            '合并策略的核心是"同板同通道、同 dt、邻近链式合并"——即只有相同 (board, channel) '
            "且采样间隔相同的 hit 才能归入同一 cluster，并通过时间 gap 和总宽度限制控制 cluster 的"
            "生长。\n\n"
            "合并窗口的中点 anchor 策略确保上下游一致：多 hit cluster 选取最接近合并时间窗口中心"
            "的 hit 作为 anchor，写入 position、timestamp、channel、record_id 等关键字段。"
            "跨 record 时，sample_start/sample_end/width 标记为 -1，time_start/time_end 始终有效。\n\n"
            "该插件不依赖外部级联状态，所有合并判断完全由配置 merge_gap_ns、max_total_width_ns "
            "和 dt 推导的绝对时间窗口决定。"
        ),
        "workflow_steps": [
            "**识别可合并片段**：`hit_threshold` 中的每一行都是一个过阈信号片段，插件判断哪些相邻片段应视为同一次通道响应。",
            "**保持通道与采样刻度一致**：只合并同一 `(board, channel)` 的片段；采样间隔不同的片段始终分开，避免把不同时间刻度的信号混在一起。",
            "**按时间连接相邻片段**：两个片段之间的空档不超过 `merge_gap_ns` 时，可以接入同一个合并窗口。将 `merge_gap_ns` 设为 `<= 0` 会关闭合并。",
            "**限制链式合并的总时长**：即使每一对相邻片段都很接近，只要合并后的完整窗口超过 `max_total_width_ns`，后续片段仍会从新的 `hit_merged` 开始。",
            "**选择代表 hit**：一个合并窗口包含多个片段时，选取最接近窗口时间中心的原始 hit，继承它的 position、timestamp、channel 和 record_id。",
            "**记录窗口与成员关系**：输出保存合并后的时间范围及成员索引；若成员跨越多个 record，则没有唯一的 sample 窗口，`sample_start`、`sample_end` 和 `width` 会标记为无效值。",
        ],
        "workflow_diagram": (
            "flowchart TD\n"
            '  A["读取并加载 hit_threshold 数据"] --> B{记录为空?}\n'
            '  B -- "是" --> Z["返回空结果"]\n'
            '  B -- "否" --> C["读取合并配置<br/>(merge_gap_ns / max_total_width_ns / dt)" ]\n'
            '  C --> D["按同板同通道、<br/>时间邻近链式分组"]\n'
            '  D --> E{"合并已关闭?<br/>(merge_gap_ns <= 0)"}\n'
            '  E -- "是" --> F["直接映射: 每条 hit 对应一条输出"]\n'
            '  E -- "否" --> G["补充 hits 时间窗口信息"]\n'
            '  G --> H["按分组构建合并结果"]\n'
            '  F --> I["选取代表 hit 输出<br/>(跨 record 时 sample 字段为 -1)"]\n'
            "  H --> I\n"
            '  I --> J["供下游消费<br/>(hit_merged_features / peaklets / hit_grouped)"]\n'
        ),
        "behavior_notes": [
            "Only hits with the same `(board, channel)` are eligible for merging; boardless inputs use board `0` as the compatibility value.",
            "`merge_gap_ns <= 0` disables merging and maps each `hit_threshold` row to one `hit_merged` row.",
            "The merge decision uses absolute hit windows derived from `timestamp`, sample window fields, `dt`, and the configured pre-trigger offset.",
            "Hits with different resolved `dt` values are not merged into the same cluster.",
            "`max_total_width_ns` limits the total absolute width of chained merges, so a locally adjacent hit can still start a new cluster when the accumulated window would exceed the limit.",
        ],
        "field_notes": {
            "merged_id": "Unique identifier for this hit_merged record, equal to its row index (0-based) in the output array. Used for tracking and referencing specific merged hits.",
            "position": "Anchor hit position; for multi-hit clusters this is the hit closest to the merged window midpoint.",
            "time_start": "Absolute start time (ps) of the merged window; always valid regardless of whether components span records.",
            "time_end": "Absolute end time (ps) of the merged window; always valid regardless of whether components span records.",
            "sample_start": "Merged sample window start when all components belong to one record; `-1` when the cluster spans records.",
            "sample_end": "Merged sample window end when all components belong to one record; `-1` when the cluster spans records.",
            "width": "Merged sample-window width; `-1.0` when the cluster spans records or otherwise cannot resolve a direct sample window.",
            "dt": "Resolved sampling interval from the anchor hit or compatible `dt` configuration fallback.",
            "timestamp": "Anchor hit timestamp; for multi-hit clusters this follows the same anchor rule as `position`.",
            "board": "Hardware board from the anchor hit; boardless inputs use compatibility value `0`.",
            "channel": "Hardware channel from the anchor hit; merging never crosses channel boundaries.",
            "record_id": "Anchor hit record id, not necessarily a shared record id for every component.",
            "component_offset": "Start row in `hit_merge_clusters` for this cluster's contiguous membership rows.",
            "component_count": "Number of contiguous `hit_merge_clusters` membership rows for this cluster.",
            "is_single_record": "True when all component hits belong to the same record (fast path available); False when spanning records.",
        },
        "config_notes": {
            "merge_gap_ns": "Maximum boundary gap in ns; values `<= 0` disable merging.",
            "max_total_width_ns": "Maximum total absolute cluster width in ns for chained merges.",
            "dt": "Compatibility fallback sampling interval in ns, used only when `hit_threshold` lacks a `dt` field.",
        },
        "cluster_contract": [
            "`hit_merged` computes canonical cluster membership from its own config; `hit_merge_clusters` exports the same membership rows for diagnostics and inspection.",
            "Rows consumed by one `hit_merged` row must be contiguous in the canonical membership order.",
            "`cluster_index` values must be sorted, contiguous, and gap-free from `0` to `len(hit_merged) - 1`.",
            "`component_offset` and `component_count` point back into the exact membership slice used by `hit_merged_components`.",
        ],
        "failure_modes": [
            "`hit_threshold` is missing required `channel` data, so same-channel grouping cannot be resolved.",
            "`hit_threshold` lacks `dt` and no compatible `dt` config fallback is available.",
            "Canonical cluster rows are not ordered by contiguous, gap-free `cluster_index` values.",
            "Cluster rows reference hit indices that are outside the materialized `hit_threshold` array.",
        ],
        "downstream_consumers": [
            "hit_merged_components",
            "hit_merged_features",
            "hit_grouped",
            "peaklets",
            "peaklet_components",
        ],
        "downstream_notes": [
            "Field semantics and row ordering changes propagate to component expansion, waveform feature extraction, cross-channel grouping, and peaklet membership.",
            "Changing `component_offset`/`component_count` requires matching updates to `hit_merge_clusters` ordering and all component consumer tests.",
            "Changing anchor-field semantics affects downstream `position`, `timestamp`, `record_id`, and channel aggregation behavior.",
        ],
        "agent_change_notes": [
            "v2.1.0: Added `merged_id` field as unique identifier equal to row index. This is a backward-compatible addition; downstream plugins auto-adapt via dtype.names checks.",
            "v2.0.0: Added `time_start`, `time_end`, `is_single_record` fields to support cross-record merging.",
            "Changing merge behavior, output field semantics, or dtype requires a `version` bump because cache lineage depends on the plugin contract.",
            "Keep `hit_merged` and `hit_merged_components` in sync; membership ordering is part of the downstream contract.",
            "After contract changes, regenerate agent docs and run targeted tests for `hit_merge`, `hit_merged_components`, `hit_merged_features`, `hit_grouped`, and `peaklets` consumers as appropriate.",
        ],
    }

    options = {
        "merge_gap_ns": Option(
            default=0.0,
            type=float,
            help="最大边界间距（ns），<=0 表示不合并",
        ),
        "max_total_width_ns": Option(
            default=10000.0,
            type=float,
            help="链式合并后的最大总宽度（ns）",
        ),
        "dt": Option(
            default=None,
            type=int,
            help="采样间隔（ns）。仅在输入 hit_threshold 缺少 dt 字段时作为兼容补充。",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        from waveform_analysis.core.processing.time_utils import get_pre_trigger_offset_ps

        hits = _materialize_array(
            context.get_data(run_id, "hit_threshold"),
            "hit_merged hit_threshold input",
            THRESHOLD_HIT_DTYPE,
        )
        if len(hits) == 0:
            return np.zeros(0, dtype=HIT_MERGED_DTYPE)

        pre_trigger_ps = get_pre_trigger_offset_ps(context)
        cluster_rows, explicit_dt, merge_disabled = _compute_canonical_cluster_rows(
            hits, context, self, pre_trigger_ps
        )

        if merge_disabled:
            return _hits_to_merged_fast(hits, explicit_dt=explicit_dt, plugin_name=self.provides)

        enriched = _build_enriched_for_hits(
            hits, explicit_dt=explicit_dt, plugin_name=self.provides, pre_trigger_ps=pre_trigger_ps
        )

        return _build_merged_from_cluster_rows(hits, cluster_rows, enriched)
