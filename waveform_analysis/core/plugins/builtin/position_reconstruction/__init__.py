"""position_reconstruction bundle - provides 'position_reconstruction'。

PositionReconstructionPlugin 从选定的 S1-S2 配对重建事件的三维空间坐标
(x, y, z)：Z 基于漂移时间，XY 基于电荷重心法。输出
``POSITION_RECONSTRUCTION_DTYPE``。
"""

from waveform_analysis.core.plugins.builtin.position_reconstruction.plugin import (
    FLAG_AMBIGUOUS_POSITION,
    FLAG_EDGE_EVENT,
    FLAG_LOW_S2_SIGNAL,
    FLAG_POSITION_VALID,
    FLAG_XY_RECONSTRUCTED,
    FLAG_Z_RECONSTRUCTED,
    POSITION_RECONSTRUCTION_DTYPE,
    PositionReconstructionPlugin,
)

__all__ = [
    "PositionReconstructionPlugin",
    "POSITION_RECONSTRUCTION_DTYPE",
    "FLAG_POSITION_VALID",
    "FLAG_Z_RECONSTRUCTED",
    "FLAG_XY_RECONSTRUCTED",
    "FLAG_LOW_S2_SIGNAL",
    "FLAG_EDGE_EVENT",
    "FLAG_AMBIGUOUS_POSITION",
]
