"""能量重建插件 - 兼容 shim。

``EnergyReconstructionPlugin``（provides="energy_reconstruction"）、
``ENERGY_RECONSTRUCTION_DTYPE`` 与全部 ``FLAG_*`` 常量已迁至
:mod:`waveform_analysis.core.plugins.builtin.energy_reconstruction`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.energy_reconstruction import (
    ENERGY_RECONSTRUCTION_DTYPE,
    FLAG_ENERGY_NOT_IMPLEMENTED,
    FLAG_ENERGY_RECONSTRUCTED,
    FLAG_LOW_S1_SIGNAL,
    FLAG_LOW_S2_SIGNAL,
    FLAG_S1_ENERGY_VALID,
    FLAG_S2_ENERGY_VALID,
    FLAG_SATURATED_S2,
    EnergyReconstructionPlugin,
)

__all__ = [
    "EnergyReconstructionPlugin",
    "ENERGY_RECONSTRUCTION_DTYPE",
    "FLAG_ENERGY_RECONSTRUCTED",
    "FLAG_S1_ENERGY_VALID",
    "FLAG_S2_ENERGY_VALID",
    "FLAG_LOW_S1_SIGNAL",
    "FLAG_LOW_S2_SIGNAL",
    "FLAG_SATURATED_S2",
    "FLAG_ENERGY_NOT_IMPLEMENTED",
]
