"""S1-S2 配对候选生成插件 - 兼容 shim。

``S1S2PairCandidatesPlugin``（provides="s1_s2_pair_candidates"）、
``S1_S2_PAIR_CANDIDATES_DTYPE`` 与全部 ``FLAG_*`` 常量已迁至
:mod:`waveform_analysis.core.plugins.builtin.s1_s2_pair_candidates`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.s1_s2_pair_candidates import (
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
