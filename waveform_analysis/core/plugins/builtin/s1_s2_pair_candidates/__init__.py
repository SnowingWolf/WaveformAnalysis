"""s1_s2_pair_candidates bundle - provides 's1_s2_pair_candidates'。

S1S2PairCandidatesPlugin 以 S2 为 anchor，在漂移时间窗口内向前搜索所有物理上
允许的 S1 候选，输出候选表（``S1_S2_PAIR_CANDIDATES_DTYPE``）。
"""

from waveform_analysis.core.plugins.builtin.s1_s2_pair_candidates.plugin import (
    FLAG_CLOSE_COMPETITOR,
    FLAG_MULTI_S1_CANDIDATE,
    FLAG_MULTI_S2_CANDIDATE,
    FLAG_NEAR_CHUNK_BOUNDARY,
    FLAG_ORPHAN_S1,
    FLAG_ORPHAN_S2,
    FLAG_RATIO_IN_RANGE,
    FLAG_S1_LOW_QUALITY,
    FLAG_S2_LOW_QUALITY,
    FLAG_VALID_TIME,
    S1_S2_PAIR_CANDIDATES_DTYPE,
    S1S2PairCandidatesPlugin,
)

__all__ = [
    "S1S2PairCandidatesPlugin",
    "S1_S2_PAIR_CANDIDATES_DTYPE",
    "FLAG_VALID_TIME",
    "FLAG_RATIO_IN_RANGE",
    "FLAG_S1_LOW_QUALITY",
    "FLAG_S2_LOW_QUALITY",
    "FLAG_MULTI_S1_CANDIDATE",
    "FLAG_MULTI_S2_CANDIDATE",
    "FLAG_CLOSE_COMPETITOR",
    "FLAG_ORPHAN_S1",
    "FLAG_ORPHAN_S2",
    "FLAG_NEAR_CHUNK_BOUNDARY",
]
