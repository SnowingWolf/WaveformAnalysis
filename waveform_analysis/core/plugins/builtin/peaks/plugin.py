"""peaks bundle - provides 'peaks'。"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.peaklets._compute import (
    PEAKS_DTYPE,
    _empty_peaks,
)
from waveform_analysis.core.plugins.core.base import Plugin


class PeaksPlugin(Plugin):
    """Build the final user-facing peaks table from peaklet metadata and features."""

    provides = "peaks"
    depends_on = ["peaklets", "peaklet_features", "peaklet_channels"]
    description = "Build final peaks table from peaklets and waveform-derived features."
    version = "4.0.1"
    output_dtype = PEAKS_DTYPE
    save_when = "always"
    agent_doc = {
        "overview": (
            "PeaksPlugin 是分析链末端的用户级插件，把 peaklet 层面的元数据与 peaklet_features "
            "导出的波形派生特征合并为最终的用户可见 peaks 表。它不重新计算任何物理量，只负责把 "
            "特征按 `peak_id` 稳定地对齐到 `peaklets` 的行序，并以其行索引作为 `peak_id`。\n\n"
            "由于 `peaklet_features` 的特征行是按 peak_id 解析的，PeaksPlugin 采用稳定排序 + "
            "`searchsorted` 的方式将每个 peaklet 精确匹配到其特征行：任何 peaklet 缺失对应特征都"
            "会被认定为数据不一致并抛出异常，从而保证 peaks 表总是完整、且与 peaklets 一一对齐。\n\n"
            "peaks 表同时携带峰形时序字段（rise_time、fall_time、width_25_75、area、height 等）"
            "与聚合规模字段（n_hits、n_channels），是上游 S1/S2 分类与物理筛选（peak_classification、"
            "s1_s2_pair_candidates）的唯一输入入口。"
        ),
        "workflow_steps": [
            "读取输入：从 context 获取 `peaklets` 与 `peaklet_features` 结构化数组；`peaklets` 为空时返回空 peaks 数组。",
            "排序特征行：以 `peaklet_features['peak_id']` 作稳定排序（mergesort），得到按 peak_id 递增的特征序列。",
            "对齐 peaklet：对每个 `peak_id`（即 peaklet 行号）用 `searchsorted` 定位特征行，并校验特征行的 peak_id 与 peaklet 一致；任一 peaklet 找不到特征则抛错。",
            "复制波形特征：将 time_start、time_end、time_peak、center_time、rise_time、fall_time、width_25_75、rise_time_10_50、range_90p_area、area、height、width 从对齐后的特征行复制到输出。",
            "填入峰规模信息：从 `peaklets` 复制 `n_hits` 与 `n_channels`。",
            "返回结果：输出 `PEAKS_DTYPE` 结构化数组，行序与 `peaklets` 完全一致，`peak_id` 即行索引。",
        ],
        "behavior_notes": [
            "`peaks` and `peaklets` are strictly 1:1: every peaklet row must have a matching `peaklet_features` row or compute raises.",
            "`peak_id` equals the row index in the output array and matches the corresponding `peaklets` row.",
            "Extra `peaklet_features` rows whose `peak_id` is not present in `peaklets` are simply not selected; they do not fail the plugin.",
            "The plugin performs no physics computation; all waveform quantities originate from `peaklet_features`.",
        ],
        "field_notes": {
            "peak_id": "Unique peak identifier, equal to the row index in `peaks` and aligned to the `peaklets` row of the same index.",
            "time_start": "Absolute start time (ps) of the peak window, copied from `peaklet_features`.",
            "time_end": "Absolute end time (ps) of the peak window, copied from `peaklet_features`.",
            "time_peak": "Absolute time (ps) of the peak maximum, copied from `peaklet_features`.",
            "center_time": "Center time (ps), copied from `peaklet_features`.",
            "rise_time": "Rise time (ns) from 10% to peak, copied from `peaklet_features`.",
            "fall_time": "Fall time (ns) between the 50% and 90% cumulative-area quantiles, copied from `peaklet_features`.",
            "width_25_75": "Width (ns) between the 25% and 75% area quantiles.",
            "rise_time_10_50": "Rise time (ns) between the 10% and 50% area quantiles.",
            "range_90p_area": "Time span (ns) covering the central 90% of the pulse area (5%-95%).",
            "area": "Integrated pulse area (sum of samples).",
            "height": "Peak height (maximum sample value).",
            "width": "Width (ns) of the peak window.",
            "n_hits": "Number of hit_merged rows aggregating to this peak, copied from `peaklets`.",
            "n_channels": "Channel aggregation scale of this peak (distinct (board, channel) pairs), copied from `peaklets`.",
        },
        "failure_modes": [
            "`peaklets` 或 `peaklet_features` 不是结构化数组时抛出 `ValueError`。",
            "存在某个 peaklet 在 `peaklet_features` 中找不到相同 `peak_id` 的特征行时抛出 `ValueError`，通常意味着上游缓存或成员关系错位。",
            "上游 `peaklet_features` 与 `peaklets` 的 `peak_id` 语义不一致（如特征缺失整段 peaklet）会触发上述异常而使 peaks 无法物化。",
        ],
        "downstream_consumers": [
            "peak_classification",
            "s1_s2_pair_candidates",
        ],
        "downstream_notes": [
            "`peak_classification` 直接以 peaks 特征做 S1/S2 分类，任何特征字段语义变化都会改变分类结果。",
            "`s1_s2_pair_candidates` 以 peaks（尤其经过分类后的 peak）生成物理候选配对，依赖 peaks 的时序与规模字段。",
        ],
        "agent_change_notes": [
            "输出字段或对齐规则的变动会影响 `peak_classification` 与 `s1_s2_pair_candidates`，请同步运行对应定向测试并重新生成文档。",
        ],
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        peaklets = context.get_data(run_id, "peaklets")
        if not isinstance(peaklets, np.ndarray):
            raise ValueError("peaks expects peaklets as a structured array")
        if len(peaklets) == 0:
            return _empty_peaks()
        features = context.get_data(run_id, "peaklet_features")
        if not isinstance(features, np.ndarray):
            raise ValueError("peaks expects peaklet_features as a structured array")

        feature_peaklet_ids = features["peak_id"].astype(np.int64, copy=False)
        feature_order = np.argsort(feature_peaklet_ids, kind="mergesort")
        sorted_peaklet_ids = feature_peaklet_ids[feature_order]

        peaklet_ids = np.arange(len(peaklets), dtype=np.int64)
        matched_pos = np.searchsorted(sorted_peaklet_ids, peaklet_ids, side="right") - 1
        matched = matched_pos >= 0
        matched[matched] &= sorted_peaklet_ids[matched_pos[matched]] == peaklet_ids[matched]
        if not np.all(matched):
            missing_peaklet_id = int(peaklet_ids[~matched][0])
            raise ValueError(
                f"peaks could not resolve peaklet_features for peaklet_id={missing_peaklet_id}"
            )

        aligned_features = features[feature_order[matched_pos]]
        out = np.zeros(len(peaklets), dtype=PEAKS_DTYPE)
        out["peak_id"] = peaklet_ids
        for field in (
            "time_start",
            "time_end",
            "time_peak",
            "center_time",
            "rise_time",
            "fall_time",
            "width_25_75",
            "rise_time_10_50",
            "range_90p_area",
            "area",
            "height",
            "width",
        ):
            out[field] = aligned_features[field]
        out["n_hits"] = peaklets["n_hits"]
        out["n_channels"] = peaklets["n_channels"]
        return out


__all__ = ["PeaksPlugin"]
