"""S1-S2 配对候选生成插件。

这个插件只负责“生成候选”，不负责“选择最终配对”。
它先把 `peak_classification` 的结果拆成 S1 和 S2，然后以 S2 为 anchor，
在漂移时间窗口内向前搜索所有物理上允许的 S1 候选。

为什么这样设计：
- S2 通常对应漂移后的电离信号，时间更靠后，适合作为锚点
- 以 S2 为中心向前找 S1，可以直接把因果约束写成时间窗口
- 候选生成和候选选择分层后，后续可以独立调分数、歧义规则和质量筛选

核心原理：
- 先按 `peak_id -> label` 建表，只接受 `LABEL_S1` 和 `LABEL_S2`
- `LABEL_UNKNOWN` 和 `LABEL_S1_S2` 不参与配对
- 对每个 S2，只在 `[t_S2 - max_drift_time, t_S2 - min_drift_time]` 内找 S1
- 用时间有序数组 + 二分搜索，把候选筛选从全扫描降到局部搜索
- 只记录候选对、观测量、排名和歧义标志，不做最终裁决

输出字段分成几类：
- Identity: `pair_id`、`s1_peak_id`、`s2_peak_id`、索引字段
- Timing: `s1_time`、`s2_time`、`drift_time`、`drift_time_ns`
- Observables: `s1_area`、`s2_area`、`log10_s2_s1`、宽度、通道数
- Score: 预留给第二层插件打分使用
- Ranking: 记录某个候选在局部竞争中的排序和歧义程度
- Flags: 标记时间边界、孤立信号、多候选冲突等情况

计算方式：
- `drift_time = t_S2 - t_S1`
- `drift_time_ns = drift_time / 1000`
- `s1_width` 和 `s2_width` 直接沿用 `peaks.width`，单位为 ns
- 候选时间窗口为 `[t_S2 - max_drift_time, t_S2 - min_drift_time]`
- `log10_s2_s1 = log10(s2_area / s1_area)`，若 `s1_area <= 0` 则记为 `0.0`
- `score_*` 字段在这一层不计算，统一置零，留给后续插件补充分数
- `rank_for_s1` 和 `rank_for_s2` 由后续排序步骤填充；当前阶段只统计局部候选数
- `FLAG_MULTI_S1_CANDIDATE` 和 `FLAG_MULTI_S2_CANDIDATE` 表示同一事件存在多个竞争配对
- 孤立信号的 `pair_id = -1`，对应缺失端的 id、index、time、drift 字段都用 `-1` 或 `0`

默认约束：
- `t_S2 > t_S1`
- `min_drift_time <= t_S2 - t_S1 <= max_drift_time`
- 可选最小面积阈值用于清理噪声候选

这一步的输出是“候选表”，后续插件可以基于分数、歧义和质量标志，
再从这些候选里选出最终的 S1-S2 配对。
"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.peak_classification import (
    LABEL_S1,
    LABEL_S2,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin

# ============================================================================
# Flags 定义
# ============================================================================

# 时间和质量标志
FLAG_VALID_TIME = 1 << 0  # 在时间窗口内
FLAG_RATIO_IN_RANGE = 1 << 1  # S2/S1 在合理范围 (可选)
FLAG_S1_LOW_QUALITY = 1 << 2  # S1 质量低
FLAG_S2_LOW_QUALITY = 1 << 3  # S2 质量低

# 歧义标志
FLAG_MULTI_S1_CANDIDATE = 1 << 4  # 该 S2 有多个 S1 候选
FLAG_MULTI_S2_CANDIDATE = 1 << 5  # 该 S1 有多个 S2 候选
FLAG_CLOSE_COMPETITOR = 1 << 6  # 次优候选分数接近

# 孤立信号标志
FLAG_ORPHAN_S1 = 1 << 7  # 孤立 S1 (无 S2 配对)
FLAG_ORPHAN_S2 = 1 << 8  # 孤立 S2 (无 S1 配对)

# 边界问题标志
FLAG_NEAR_CHUNK_BOUNDARY = 1 << 9  # 接近数据块边界,配对可能不完整


# ============================================================================
# 数据结构定义
# ============================================================================

S1_S2_PAIR_CANDIDATES_DTYPE = np.dtype(
    [
        # === Identity ===
        ("pair_id", "i8"),  # 候选对唯一标识
        ("s1_peak_id", "i8"),  # S1 的 peak_id
        ("s2_peak_id", "i8"),  # S2 的 peak_id (anchor)
        ("s1_index", "i4"),  # S1 在 s1_peaks 数组中的索引
        ("s2_index", "i4"),  # S2 在 s2_peaks 数组中的索引
        # === Timing (ps 精度) ===
        ("s1_time", "i8"),  # S1 时间戳 (ps)
        ("s2_time", "i8"),  # S2 时间戳 (ps)
        ("drift_time", "i8"),  # 漂移时间 (ps)
        ("drift_time_ns", "f4"),  # 漂移时间 (ns, 易读)
        # === Raw observables ===
        ("s1_area", "f4"),  # S1 信号面积
        ("s2_area", "f4"),  # S2 信号面积
        ("log10_s2_s1", "f4"),  # log10(S2/S1) 能量比
        ("s1_width", "f4"),  # S1 宽度 (ns)
        ("s2_width", "f4"),  # S2 宽度 (ns)
        ("s1_n_channels", "i2"),  # S1 通道数
        ("s2_n_channels", "i2"),  # S2 通道数
        # === Score components (第二层填充) ===
        ("score_total", "f4"),  # 总分
        ("score_time", "f4"),  # 时间分数
        ("score_s1_quality", "f4"),  # S1 质量分数
        ("score_s2_quality", "f4"),  # S2 质量分数
        ("score_ratio", "f4"),  # S2/S1 比值分数
        ("score_pattern", "f4"),  # 模式匹配分数 (预留)
        ("score_ambiguity", "f4"),  # 歧义惩罚 (预留)
        # === Ranking / Ambiguity ===
        ("rank_for_s1", "i4"),  # 此 S2 在该 S1 所有候选中的排名 (1-based)
        ("rank_for_s2", "i4"),  # 此 S1 在该 S2 所有候选中的排名 (1-based)
        ("n_s1_candidates_for_s2", "i4"),  # 该 S2 有多少个 S1 候选
        ("n_s2_candidates_for_s1", "i4"),  # 该 S1 有多少个 S2 候选
        ("delta_score_to_next_best", "f4"),  # 与次优候选的分数差
        # === Flags (bit field) ===
        ("flags", "u4"),  # 状态标志位
        ("selected", "?"),  # 是否被选为最终配对
    ]
)


# ============================================================================
# 插件实现
# ============================================================================


class S1S2PairCandidatesPlugin(Plugin):
    """S1-S2 配对候选生成插件

    生成所有物理允许的 S1-S2 配对候选对。采用 S2 为 anchor 的设计,
    对每个 S2 向前搜索满足时间窗口约束的 S1 候选。

    Hard constraints (物理必须满足):
    - t_S2 > t_S1 (时间因果性)
    - min_drift_time < (t_S2 - t_S1) < max_drift_time (漂移时间窗口)
    - 可选: S1/S2 最小面积阈值

    不做的事:
    - 不判断哪个配对"更好"
    - 不强制唯一配对
    - 不做复杂的能量比筛选 (只存储 log10_s2_s1)

    输出:
    - 候选表,包含所有满足物理约束的 (S1, S2) 配对
    - selected=False (由第二层插件设置)
    - score=0.0 (由第二层插件计算)
    """

    provides = "s1_s2_pair_candidates"
    depends_on = ["peak_classification", "peaks"]
    description = "Generate all physically allowed S1-S2 pairing candidates"
    version = "0.1.3"
    save_when = "always"
    output_dtype = S1_S2_PAIR_CANDIDATES_DTYPE

    options = {
        "max_drift_time": Option(
            default=50000.0,
            type=float,
            help="最大漂移时间 (ns). 典型液氙 TPC 约 50 μs",
            min_value=0.0,
        ),
        "min_drift_time": Option(
            default=0.0,
            type=float,
            help="最小漂移时间 (ns). 用于过滤噪声",
            min_value=0.0,
        ),
        "time_field": Option(
            default="center_time",
            type=str,
            choices=["center_time", "time_start", "time_peak"],
            help="使用的时间字段",
        ),
        "min_s1_area": Option(
            default=None,
            type=(float, type(None)),
            help="S1 最小面积阈值 (可选)",
        ),
        "min_s2_area": Option(
            default=None,
            type=(float, type(None)),
            help="S2 最小面积阈值 (可选)",
        ),
        "allow_orphan_s1": Option(
            default=False,
            type=bool,
            help="是否输出孤立 S1 (无 S2 配对)",
        ),
        "allow_orphan_s2": Option(
            default=False,
            type=bool,
            help="是否输出孤立 S2 (无 S1 配对)",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        """生成 S1-S2 配对候选

        算法:
        1. 分离 S1 和 S2 peaks
        2. 预处理: 排序, 应用面积阈值
        3. 主循环: 对每个 S2, 使用二分搜索找到候选 S1 范围
        4. 提取 observables
        5. 统计 ambiguity 信息
        6. 可选: 处理孤立信号

        时间复杂度: O(M log N + K), K 是候选总数
        """
        # 获取依赖数据
        peak_classification = context.get_data(run_id, "peak_classification")
        peaks = context.get_data(run_id, "peaks")

        # 获取配置
        max_drift_ns = context.get_config(self, "max_drift_time")
        min_drift_ns = context.get_config(self, "min_drift_time")
        time_field = context.get_config(self, "time_field")
        min_s1_area = context.get_config(self, "min_s1_area")
        min_s2_area = context.get_config(self, "min_s2_area")
        allow_orphan_s1 = context.get_config(self, "allow_orphan_s1")
        allow_orphan_s2 = context.get_config(self, "allow_orphan_s2")

        # 转换为皮秒 (peaks 使用 ps 精度)
        max_drift_ps = int(max_drift_ns * 1000)
        min_drift_ps = int(min_drift_ns * 1000)

        # 分离 S1 和 S2
        s1_peaks, s2_peaks = self._split_s1_s2(peaks, peak_classification)

        # 应用面积阈值
        if min_s1_area is not None:
            s1_peaks = s1_peaks[s1_peaks["area"] >= min_s1_area]
        if min_s2_area is not None:
            s2_peaks = s2_peaks[s2_peaks["area"] >= min_s2_area]

        # 空数据处理
        if len(s1_peaks) == 0 or len(s2_peaks) == 0:
            return self._handle_empty_or_orphan_only(
                s1_peaks, s2_peaks, allow_orphan_s1, allow_orphan_s2
            )

        # 生成候选
        candidates = self._build_candidates(
            s1_peaks,
            s2_peaks,
            time_field,
            min_drift_ps,
            max_drift_ps,
        )

        # 统计 ambiguity 信息
        self._compute_ambiguity_stats(candidates)

        # 处理孤立信号
        if allow_orphan_s1 or allow_orphan_s2:
            orphan_records = self._generate_orphan_records(
                s1_peaks, s2_peaks, candidates, allow_orphan_s1, allow_orphan_s2
            )
            if len(orphan_records) > 0:
                candidates = np.concatenate([candidates, orphan_records])

        return candidates

    def _split_s1_s2(self, peaks: np.ndarray, peak_classification: np.ndarray):
        """分离 S1 和 S2 peaks

        注意：只有明确标记为 LABEL_S1 或 LABEL_S2 的 peaks 会被选入。
        LABEL_UNKNOWN 和 LABEL_S1_S2（混合信号）会被忽略，不参与配对。
        """
        if len(peaks) == 0 or len(peak_classification) == 0:
            return peaks[:0], peaks[:0]

        label_peak_ids = peak_classification["peak_id"].astype(np.int64, copy=False)
        label_order = np.argsort(label_peak_ids, kind="mergesort")
        sorted_label_peak_ids = label_peak_ids[label_order]
        peak_ids = peaks["peak_id"].astype(np.int64, copy=False)
        matched_pos = np.searchsorted(sorted_label_peak_ids, peak_ids, side="right") - 1
        matched = matched_pos >= 0
        matched[matched] &= sorted_label_peak_ids[matched_pos[matched]] == peak_ids[matched]

        labels = np.zeros(len(peaks), dtype=np.int8)
        labels[matched] = peak_classification["label"][label_order[matched_pos[matched]]]
        return peaks[labels == LABEL_S1], peaks[labels == LABEL_S2]

    def _build_candidates(
        self,
        s1_peaks: list,
        s2_peaks: list,
        time_field: str,
        min_drift_ps: int,
        max_drift_ps: int,
    ) -> np.ndarray:
        """生成所有候选对 (S2-anchor + 二分搜索)"""
        # 按时间排序
        s1_order = np.argsort(s1_peaks[time_field], kind="mergesort")
        s2_order = np.argsort(s2_peaks[time_field], kind="mergesort")
        s1_peaks_sorted = s1_peaks[s1_order]
        s2_peaks_sorted = s2_peaks[s2_order]

        # 提取 S1 时间数组用于二分搜索
        s1_times = s1_peaks_sorted[time_field].astype(np.int64, copy=False)
        s2_times = s2_peaks_sorted[time_field].astype(np.int64, copy=False)
        left_indices = np.searchsorted(s1_times, s2_times - max_drift_ps, side="left")
        right_indices = np.searchsorted(s1_times, s2_times - min_drift_ps, side="right")
        counts = right_indices - left_indices
        n_candidates = int(np.sum(counts))
        if n_candidates == 0:
            return np.zeros(0, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)

        nonzero_s2 = counts > 0
        s2_indices = np.repeat(
            np.flatnonzero(nonzero_s2).astype(np.int32, copy=False),
            counts[nonzero_s2].astype(np.int64, copy=False),
        )
        group_starts = np.repeat(
            np.r_[0, np.cumsum(counts[nonzero_s2], dtype=np.int64)[:-1]],
            counts[nonzero_s2].astype(np.int64, copy=False),
        )
        s1_indices = (
            np.repeat(
                left_indices[nonzero_s2].astype(np.int64, copy=False),
                counts[nonzero_s2].astype(np.int64, copy=False),
            )
            + np.arange(n_candidates, dtype=np.int64)
            - group_starts
        ).astype(np.int32, copy=False)

        s1_rows = s1_peaks_sorted[s1_indices]
        s2_rows = s2_peaks_sorted[s2_indices]
        s1_times = s1_rows[time_field].astype(np.int64, copy=False)
        s2_times = s2_rows[time_field].astype(np.int64, copy=False)
        drift_time_ps = s2_times - s1_times
        s1_area = s1_rows["area"].astype(np.float32, copy=False)
        s2_area = s2_rows["area"].astype(np.float32, copy=False)

        candidates = np.zeros(n_candidates, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)
        candidates["pair_id"] = np.arange(n_candidates, dtype=np.int64)
        candidates["s1_peak_id"] = s1_rows["peak_id"]
        candidates["s2_peak_id"] = s2_rows["peak_id"]
        candidates["s1_index"] = s1_indices
        candidates["s2_index"] = s2_indices
        candidates["s1_time"] = s1_times
        candidates["s2_time"] = s2_times
        candidates["drift_time"] = drift_time_ps
        candidates["drift_time_ns"] = drift_time_ps.astype(np.float32, copy=False) / 1000.0
        candidates["s1_area"] = s1_area
        candidates["s2_area"] = s2_area

        log10_s2_s1 = np.divide(
            s2_area,
            s1_area,
            out=np.ones(n_candidates, dtype=np.float32),
            where=s1_area > 0.0,
        )
        positive_s1 = s1_area > 0.0
        log10_s2_s1[positive_s1] = np.log10(log10_s2_s1[positive_s1])
        log10_s2_s1[~positive_s1] = 0.0
        candidates["log10_s2_s1"] = log10_s2_s1
        candidates["s1_width"] = s1_rows["width"].astype(np.float32, copy=False)
        candidates["s2_width"] = s2_rows["width"].astype(np.float32, copy=False)
        candidates["s1_n_channels"] = s1_rows["n_channels"]
        candidates["s2_n_channels"] = s2_rows["n_channels"]
        candidates["flags"] = FLAG_VALID_TIME

        return candidates

    def _compute_ambiguity_stats(self, candidates: np.ndarray):
        """统计 ambiguity 信息 (in-place 修改)"""
        if len(candidates) == 0:
            return

        s2_indices = candidates["s2_index"].astype(np.int64, copy=False)
        valid_s2 = s2_indices >= 0
        s2_counts = np.bincount(s2_indices[valid_s2]) if np.any(valid_s2) else np.zeros(0)
        s2_candidate_counts = np.zeros(len(candidates), dtype=np.int32)
        s2_candidate_counts[valid_s2] = s2_counts[s2_indices[valid_s2]].astype(np.int32, copy=False)
        candidates["n_s1_candidates_for_s2"] = s2_candidate_counts
        candidates["flags"][s2_candidate_counts > 1] |= FLAG_MULTI_S1_CANDIDATE

        s1_indices = candidates["s1_index"].astype(np.int64, copy=False)
        valid_s1 = s1_indices >= 0
        s1_counts = np.bincount(s1_indices[valid_s1]) if np.any(valid_s1) else np.zeros(0)
        s1_candidate_counts = np.zeros(len(candidates), dtype=np.int32)
        s1_candidate_counts[valid_s1] = s1_counts[s1_indices[valid_s1]].astype(np.int32, copy=False)
        candidates["n_s2_candidates_for_s1"] = s1_candidate_counts
        candidates["flags"][s1_candidate_counts > 1] |= FLAG_MULTI_S2_CANDIDATE

    def _handle_empty_or_orphan_only(
        self,
        s1_peaks: list,
        s2_peaks: list,
        allow_orphan_s1: bool,
        allow_orphan_s2: bool,
    ) -> np.ndarray:
        """处理空数据或只有一种类型 peak 的情况"""
        if len(s1_peaks) == 0 and len(s2_peaks) == 0:
            return np.zeros(0, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)

        orphan_records = []

        # 只有 S1, 无 S2
        if len(s2_peaks) == 0 and allow_orphan_s1:
            for idx, s1_peak in enumerate(s1_peaks):
                orphan_records.append(self._create_orphan_s1_record(s1_peak, idx))

        # 只有 S2, 无 S1
        if len(s1_peaks) == 0 and allow_orphan_s2:
            for idx, s2_peak in enumerate(s2_peaks):
                orphan_records.append(self._create_orphan_s2_record(s2_peak, idx))

        if len(orphan_records) == 0:
            return np.zeros(0, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)

        result = np.zeros(len(orphan_records), dtype=S1_S2_PAIR_CANDIDATES_DTYPE)
        for i, rec in enumerate(orphan_records):
            for key in rec:
                result[i][key] = rec[key]

        return result

    def _generate_orphan_records(
        self,
        s1_peaks: list,
        s2_peaks: list,
        candidates: np.ndarray,
        allow_orphan_s1: bool,
        allow_orphan_s2: bool,
    ) -> np.ndarray:
        """生成孤立信号记录"""
        orphan_records = []

        # 找出有配对的 S1 和 S2
        paired_s1_ids = {int(c["s1_peak_id"]) for c in candidates}
        paired_s2_ids = {int(c["s2_peak_id"]) for c in candidates}

        # 孤立 S1
        if allow_orphan_s1:
            for idx, s1_peak in enumerate(s1_peaks):
                if int(s1_peak["peak_id"]) not in paired_s1_ids:
                    orphan_records.append(self._create_orphan_s1_record(s1_peak, idx))

        # 孤立 S2
        if allow_orphan_s2:
            for idx, s2_peak in enumerate(s2_peaks):
                if int(s2_peak["peak_id"]) not in paired_s2_ids:
                    orphan_records.append(self._create_orphan_s2_record(s2_peak, idx))

        if len(orphan_records) == 0:
            return np.zeros(0, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)

        result = np.zeros(len(orphan_records), dtype=S1_S2_PAIR_CANDIDATES_DTYPE)
        for i, rec in enumerate(orphan_records):
            for key in rec:
                result[i][key] = rec[key]

        return result

    def _create_orphan_s1_record(self, s1_peak, s1_idx: int) -> dict:
        """创建孤立 S1 记录"""
        return {
            "pair_id": -1,
            "s1_peak_id": int(s1_peak["peak_id"]),
            "s2_peak_id": -1,  # 标记缺失
            "s1_index": s1_idx,
            "s2_index": -1,
            "s1_time": int(s1_peak["center_time"]),
            "s2_time": -1,
            "drift_time": -1,
            "drift_time_ns": -1.0,
            "s1_area": float(s1_peak["area"]),
            "s2_area": 0.0,
            "log10_s2_s1": 0.0,
            "s1_width": float(s1_peak["width"]),
            "s2_width": 0.0,
            "s1_n_channels": int(s1_peak["n_channels"]),
            "s2_n_channels": 0,
            "score_total": 0.0,
            "score_time": 0.0,
            "score_s1_quality": 0.0,
            "score_s2_quality": 0.0,
            "score_ratio": 0.0,
            "score_pattern": 0.0,
            "score_ambiguity": 0.0,
            "rank_for_s1": 0,
            "rank_for_s2": 0,
            "n_s1_candidates_for_s2": 0,
            "n_s2_candidates_for_s1": 0,
            "delta_score_to_next_best": 0.0,
            "flags": FLAG_ORPHAN_S1,
            "selected": False,
        }

    def _create_orphan_s2_record(self, s2_peak, s2_idx: int) -> dict:
        """创建孤立 S2 记录"""
        return {
            "pair_id": -1,
            "s1_peak_id": -1,  # 标记缺失
            "s2_peak_id": int(s2_peak["peak_id"]),
            "s1_index": -1,
            "s2_index": s2_idx,
            "s1_time": -1,
            "s2_time": int(s2_peak["center_time"]),
            "drift_time": -1,
            "drift_time_ns": -1.0,
            "s1_area": 0.0,
            "s2_area": float(s2_peak["area"]),
            "log10_s2_s1": 0.0,
            "s1_width": 0.0,
            "s2_width": float(s2_peak["width"]),
            "s1_n_channels": 0,
            "s2_n_channels": int(s2_peak["n_channels"]),
            "score_total": 0.0,
            "score_time": 0.0,
            "score_s1_quality": 0.0,
            "score_s2_quality": 0.0,
            "score_ratio": 0.0,
            "score_pattern": 0.0,
            "score_ambiguity": 0.0,
            "rank_for_s1": 0,
            "rank_for_s2": 0,
            "n_s1_candidates_for_s2": 0,
            "n_s2_candidates_for_s1": 0,
            "delta_score_to_next_best": 0.0,
            "flags": FLAG_ORPHAN_S2,
            "selected": False,
        }
