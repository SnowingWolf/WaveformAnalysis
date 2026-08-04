"""S1-S2 配对选择插件 - 兼容 shim。

``S1S2PairSelectionPlugin``（provides="s1_s2_pairs"）已迁至
:mod:`waveform_analysis.core.plugins.builtin.s1_s2_pairs`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.s1_s2_pairs import S1S2PairSelectionPlugin

__all__ = ["S1S2PairSelectionPlugin"]
