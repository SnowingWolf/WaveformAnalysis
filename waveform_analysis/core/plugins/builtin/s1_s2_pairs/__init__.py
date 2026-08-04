"""s1_s2_pairs bundle - provides 's1_s2_pairs'。

S1S2PairSelectionPlugin 对候选进行打分并选择最佳配对，输出仍是候选表
（``S1_S2_PAIR_CANDIDATES_DTYPE``，其中 selected 标志被填充）。
"""

from waveform_analysis.core.plugins.builtin.s1_s2_pairs.plugin import (
    S1S2PairSelectionPlugin,
)

__all__ = ["S1S2PairSelectionPlugin"]
