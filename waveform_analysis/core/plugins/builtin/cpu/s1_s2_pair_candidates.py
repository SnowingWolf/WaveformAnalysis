"""S1-S2 配对候选生成插件

此插件生成所有物理允许的 S1-S2 配对候选,不做选择判断。
采用 S2 为 anchor 的设计,向前搜索时间窗口内的 S1 候选。

Author: Claude Code
Version: 0.1.0
"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.peaklet_s1_s2_classifier import (
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
        ("rank_for_s1", "i2"),  # 此 S2 在该 S1 所有候选中的排名 (1-based)
        ("rank_for_s2", "i2"),  # 此 S1 在该 S2 所有候选中的排名 (1-based)
        ("n_s1_candidates_for_s2", "i2"),  # 该 S2 有多少个 S1 候选
        ("n_s2_candidates_for_s1", "i2"),  # 该 S1 有多少个 S2 候选
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
    depends_on = ["peaklet_s1_s2", "peaks"]
    description = "Generate all physically allowed S1-S2 pairing candidates"
    version = "0.1.0"
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
        peaklet_s1_s2 = context.get_data(run_id, "peaklet_s1_s2")
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
        s1_peaks, s2_peaks = self._split_s1_s2(peaks, peaklet_s1_s2)

        # 应用面积阈值
        if min_s1_area is not None:
            s1_peaks = [p for p in s1_peaks if p["area"] >= min_s1_area]
        if min_s2_area is not None:
            s2_peaks = [p for p in s2_peaks if p["area"] >= min_s2_area]

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

    def _split_s1_s2(self, peaks: np.ndarray, peaklet_s1_s2: np.ndarray):
        """分离 S1 和 S2 peaks"""
        # 构建 peak_id -> label 映射
        label_map = {int(row["peak_id"]): int(row["label"]) for row in peaklet_s1_s2}

        s1_peaks = []
        s2_peaks = []

        for peak in peaks:
            peak_id = int(peak["peak_id"])
            label = label_map.get(peak_id, 0)

            if label == LABEL_S1:
                s1_peaks.append(peak)
            elif label == LABEL_S2:
                s2_peaks.append(peak)

        return s1_peaks, s2_peaks

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
        s1_peaks_sorted = sorted(s1_peaks, key=lambda p: p[time_field])
        s2_peaks_sorted = sorted(s2_peaks, key=lambda p: p[time_field])

        # 提取 S1 时间数组用于二分搜索
        s1_times = np.array([int(p[time_field]) for p in s1_peaks_sorted], dtype=np.int64)

        candidates_list = []
        pair_id_counter = 0

        # 主循环: 对每个 S2, 向前搜索 S1 候选
        for s2_idx, s2_peak in enumerate(s2_peaks_sorted):
            s2_time = int(s2_peak[time_field])

            # 计算 S1 有效时间范围
            # S1 必须在 S2 之前, 漂移时间在 [min, max] 内
            s1_time_min = s2_time - max_drift_ps
            s1_time_max = s2_time - min_drift_ps

            # O(log N) 二分查找
            left_idx = np.searchsorted(s1_times, s1_time_min, side="left")
            right_idx = np.searchsorted(s1_times, s1_time_max, side="right")

            # 遍历候选 S1
            for s1_idx in range(left_idx, right_idx):
                s1_peak = s1_peaks_sorted[s1_idx]
                s1_time = int(s1_peak[time_field])

                # 计算 observables
                drift_time_ps = s2_time - s1_time
                drift_time_ns = float(drift_time_ps / 1000.0)

                s1_area = float(s1_peak["area"])
                s2_area = float(s2_peak["area"])

                # log10(S2/S1), 避免除零
                if s1_area > 0:
                    log10_s2_s1 = float(np.log10(s2_area / s1_area))
                else:
                    log10_s2_s1 = 0.0

                # 提取宽度 (转换为 ns)
                s1_width = float(s1_peak["width"] / 1000.0)  # ps -> ns
                s2_width = float(s2_peak["width"] / 1000.0)

                # 创建候选记录
                candidate = {
                    "pair_id": pair_id_counter,
                    "s1_peak_id": int(s1_peak["peak_id"]),
                    "s2_peak_id": int(s2_peak["peak_id"]),
                    "s1_index": s1_idx,
                    "s2_index": s2_idx,
                    "s1_time": s1_time,
                    "s2_time": s2_time,
                    "drift_time": drift_time_ps,
                    "drift_time_ns": drift_time_ns,
                    "s1_area": s1_area,
                    "s2_area": s2_area,
                    "log10_s2_s1": log10_s2_s1,
                    "s1_width": s1_width,
                    "s2_width": s2_width,
                    "s1_n_channels": int(s1_peak["n_channels"]),
                    "s2_n_channels": int(s2_peak["n_channels"]),
                    # Score components (第二层填充)
                    "score_total": 0.0,
                    "score_time": 0.0,
                    "score_s1_quality": 0.0,
                    "score_s2_quality": 0.0,
                    "score_ratio": 0.0,
                    "score_pattern": 0.0,
                    "score_ambiguity": 0.0,
                    # Ranking (后续填充)
                    "rank_for_s1": 0,
                    "rank_for_s2": 0,
                    "n_s1_candidates_for_s2": 0,
                    "n_s2_candidates_for_s1": 0,
                    "delta_score_to_next_best": 0.0,
                    # Flags
                    "flags": FLAG_VALID_TIME,
                    "selected": False,
                }

                candidates_list.append(candidate)
                pair_id_counter += 1

        # 转换为结构化数组
        if len(candidates_list) == 0:
            return np.zeros(0, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)

        candidates = np.zeros(len(candidates_list), dtype=S1_S2_PAIR_CANDIDATES_DTYPE)
        for i, cand in enumerate(candidates_list):
            for key in cand:
                candidates[i][key] = cand[key]

        return candidates

    def _compute_ambiguity_stats(self, candidates: np.ndarray):
        """统计 ambiguity 信息 (in-place 修改)"""
        if len(candidates) == 0:
            return

        # 统计每个 S2 有多少个 S1 候选
        s2_to_candidates = {}
        for cand in candidates:
            s2_id = int(cand["s2_peak_id"])
            if s2_id not in s2_to_candidates:
                s2_to_candidates[s2_id] = []
            s2_to_candidates[s2_id].append(cand)

        for _s2_id, cands in s2_to_candidates.items():
            n_s1_cands = len(cands)
            for cand in cands:
                cand["n_s1_candidates_for_s2"] = n_s1_cands
                if n_s1_cands > 1:
                    cand["flags"] |= FLAG_MULTI_S1_CANDIDATE

        # 统计每个 S1 有多少个 S2 候选
        s1_to_candidates = {}
        for cand in candidates:
            s1_id = int(cand["s1_peak_id"])
            if s1_id not in s1_to_candidates:
                s1_to_candidates[s1_id] = []
            s1_to_candidates[s1_id].append(cand)

        for _s1_id, cands in s1_to_candidates.items():
            n_s2_cands = len(cands)
            for cand in cands:
                cand["n_s2_candidates_for_s1"] = n_s2_cands
                if n_s2_cands > 1:
                    cand["flags"] |= FLAG_MULTI_S2_CANDIDATE

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
            "s1_width": float(s1_peak["width"] / 1000.0),
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
            "s2_width": float(s2_peak["width"] / 1000.0),
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
