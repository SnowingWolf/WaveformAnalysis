"""S1-S2 配对选择插件

此插件对候选进行打分并选择最佳配对。
第一版实现 largest 模式,其他模式预留接口。

Author: Claude Code
Version: 0.1.0
"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates import (
    FLAG_CLOSE_COMPETITOR,
    S1_S2_PAIR_CANDIDATES_DTYPE,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin


class S1S2PairSelectionPlugin(Plugin):
    """S1-S2 配对选择插件

    对候选进行打分并选择最佳配对。为每个 S2 选择最优的 S1。

    选择模式:
    - largest: 选择面积最大的 S1 (v0.1 实现)
    - nearest: 选择时间最近的 S1 (预留)
    - best_score: 综合打分 (预留)
    - all: 不做选择,保留所有候选 (预留)

    输出:
    - 修改 candidates 的 selected flag
    - 填充 score 字段
    - 计算 delta_score_to_next_best
    - 计算 rank_for_s2
    """

    provides = "s1_s2_pairs"
    depends_on = ["s1_s2_pair_candidates"]
    description = "Select best S1-S2 pairs from candidates"
    version = "0.1.0"
    save_when = "always"
    output_dtype = S1_S2_PAIR_CANDIDATES_DTYPE

    options = {
        "selection_mode": Option(
            default="largest",
            type=str,
            choices=["largest", "nearest", "best_score", "all"],
            help="选择策略: largest (最大S1), nearest (最近), best_score (综合), all (全部)",
        ),
        "close_competitor_threshold": Option(
            default=0.1,
            type=float,
            help="次优候选接近阈值。delta_score < threshold 时标记 FLAG_CLOSE_COMPETITOR",
            min_value=0.0,
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        """选择最佳配对

        算法:
        1. 获取候选
        2. 计算 score (根据 selection_mode)
        3. 为每个 S2 选择最优 S1
        4. 设置 selected flag
        5. 计算 delta_score_to_next_best
        6. 计算 rank_for_s2
        7. 标记 CLOSE_COMPETITOR
        """
        # 获取候选
        candidates = context.get_data(run_id, "s1_s2_pair_candidates")

        # 复制以避免修改原数据
        candidates = candidates.copy()

        # 空数据处理
        if len(candidates) == 0:
            return candidates

        # 获取配置
        selection_mode = context.get_config(self, "selection_mode")
        close_threshold = context.get_config(self, "close_competitor_threshold")

        # 计算 score
        self._compute_scores(candidates, selection_mode)

        # 选择最佳配对
        if selection_mode == "all":
            # all 模式: 所有候选都 selected
            candidates["selected"] = True
        else:
            # 其他模式: 为每个 S2 选择最优 S1
            self._select_best_pairs(candidates, close_threshold)

        return candidates

    def _compute_scores(self, candidates: np.ndarray, mode: str):
        """计算 score (in-place 修改)"""
        if mode == "largest":
            # largest 模式: score = S1 面积
            # 使用 log1p 避免面积差异过大导致数值问题
            candidates["score_s1_quality"] = np.log1p(candidates["s1_area"])
            candidates["score_total"] = candidates["score_s1_quality"]

        elif mode == "nearest":
            # nearest 模式: score = 1 - 归一化漂移时间 (预留)
            # 时间越短,分数越高
            drift_times = candidates["drift_time_ns"]
            if len(drift_times) > 0:
                min_drift = np.min(drift_times)
                max_drift = np.max(drift_times)
                if max_drift > min_drift:
                    normalized = (drift_times - min_drift) / (max_drift - min_drift)
                    candidates["score_time"] = 1.0 - normalized
                else:
                    candidates["score_time"] = 1.0
                candidates["score_total"] = candidates["score_time"]

        elif mode == "best_score":
            # best_score 模式: 综合打分 (预留)
            # score = w_time * score_time + w_s1 * score_s1 + w_s2 * score_s2
            # 目前使用简单的均等权重
            self._compute_quality_scores(candidates)
            candidates["score_total"] = (
                0.2 * candidates["score_time"]
                + 0.4 * candidates["score_s1_quality"]
                + 0.2 * candidates["score_s2_quality"]
                + 0.2 * candidates["score_ratio"]
            )

        else:
            # all 模式: 不计算 score
            pass

    def _compute_quality_scores(self, candidates: np.ndarray):
        """计算质量分数 (预留接口)

        这是一个预留的综合打分函数,未来可以根据 calibration data 优化。
        """
        # S1 质量: area + n_channels - width
        s1_area = np.maximum(candidates["s1_area"], 0)
        s1_width = np.maximum(candidates["s1_width"], 1)
        s1_nch = np.maximum(candidates["s1_n_channels"], 1)

        candidates["score_s1_quality"] = (
            np.log1p(s1_area) + 0.5 * np.log1p(s1_nch) - 0.5 * np.log1p(s1_width)
        )

        # S2 质量: area + n_channels
        s2_area = np.maximum(candidates["s2_area"], 0)
        s2_nch = np.maximum(candidates["s2_n_channels"], 1)

        candidates["score_s2_quality"] = np.log1p(s2_area) + 0.3 * np.log1p(s2_nch)

        # 时间分数 (归一化)
        drift_times = candidates["drift_time_ns"]
        if len(drift_times) > 0:
            min_drift = np.min(drift_times)
            max_drift = np.max(drift_times)
            if max_drift > min_drift:
                normalized = (drift_times - min_drift) / (max_drift - min_drift)
                candidates["score_time"] = 1.0 - normalized
            else:
                candidates["score_time"] = 1.0

        # S2/S1 比值分数 (预留,目前设为 0)
        candidates["score_ratio"] = 0.0

    def _select_best_pairs(self, candidates: np.ndarray, close_threshold: float):
        """为每个 S2 选择最优 S1 (in-place 修改)"""
        # 按 S2 分组
        s2_to_indices = {}
        for idx, cand in enumerate(candidates):
            s2_id = int(cand["s2_peak_id"])
            if s2_id not in s2_to_indices:
                s2_to_indices[s2_id] = []
            s2_to_indices[s2_id].append(idx)

        # 处理每个 S2 的候选
        for _s2_id, indices in s2_to_indices.items():
            # 获取该 S2 的所有候选
            s2_cands = candidates[indices]

            # 按 score_total 降序排序
            sorted_indices = np.argsort(-s2_cands["score_total"])
            sorted_cands = s2_cands[sorted_indices]

            # 计算 rank_for_s2
            for rank, idx in enumerate(sorted_indices):
                candidates[indices[idx]]["rank_for_s2"] = rank + 1  # 1-based

            if len(sorted_cands) == 1:
                # 唯一候选
                best_idx = indices[sorted_indices[0]]
                candidates[best_idx]["selected"] = True
                candidates[best_idx]["delta_score_to_next_best"] = np.inf

            else:
                # 多个候选: 选择最优
                best_idx = indices[sorted_indices[0]]
                second_best_idx = indices[sorted_indices[1]]

                candidates[best_idx]["selected"] = True

                # 计算 delta_score
                best_score = candidates[best_idx]["score_total"]
                second_score = candidates[second_best_idx]["score_total"]
                delta = best_score - second_score
                candidates[best_idx]["delta_score_to_next_best"] = delta

                # 标记竞争激烈
                if delta < close_threshold:
                    candidates[best_idx]["flags"] |= FLAG_CLOSE_COMPETITOR

        # 计算 rank_for_s1 (可选,预留)
        # 这需要按 S1 分组,计算每个 S1 在其所有 S2 候选中的排名
        self._compute_rank_for_s1(candidates)

    def _compute_rank_for_s1(self, candidates: np.ndarray):
        """计算每个 S1 的排名 (in-place 修改)"""
        # 按 S1 分组
        s1_to_indices = {}
        for idx, cand in enumerate(candidates):
            s1_id = int(cand["s1_peak_id"])
            if s1_id == -1:  # 跳过孤立 S2
                continue
            if s1_id not in s1_to_indices:
                s1_to_indices[s1_id] = []
            s1_to_indices[s1_id].append(idx)

        # 处理每个 S1 的候选
        for _s1_id, indices in s1_to_indices.items():
            if len(indices) == 1:
                candidates[indices[0]]["rank_for_s1"] = 1
            else:
                # 按 score_total 降序排序
                s1_cands = candidates[indices]
                sorted_indices = np.argsort(-s1_cands["score_total"])

                # 设置 rank
                for rank, idx in enumerate(sorted_indices):
                    candidates[indices[idx]]["rank_for_s1"] = rank + 1
