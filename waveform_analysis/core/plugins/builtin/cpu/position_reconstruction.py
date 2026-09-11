"""位置重建插件 - 兼容 shim。

``PositionReconstructionPlugin``（provides="position_reconstruction"）、
``POSITION_RECONSTRUCTION_DTYPE`` 与全部 ``FLAG_*`` 常量已迁至
:mod:`waveform_analysis.core.plugins.builtin.position_reconstruction`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.position_reconstruction import (
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
