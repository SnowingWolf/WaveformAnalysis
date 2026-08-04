"""energy_reconstruction bundle - provides 'energy_reconstruction'。

EnergyReconstructionPlugin 从选定的 S1-S2 配对重建事件能量，输出
``ENERGY_RECONSTRUCTION_DTYPE``。当前为结构占位版本：能量值填 NaN 并标记
``FLAG_ENERGY_NOT_IMPLEMENTED``。
"""

from waveform_analysis.core.plugins.builtin.energy_reconstruction.plugin import (
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
