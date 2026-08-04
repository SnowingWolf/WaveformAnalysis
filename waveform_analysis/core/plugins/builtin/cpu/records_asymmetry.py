"""Records-backed waveform asymmetry mask plugin - 兼容 shim。

``RecordsAsymmetryMaskPlugin`` 与 Numba 内核已迁至 bundle ``records_asymmetry_mask``。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.records_asymmetry_mask.plugin import (
    RecordsAsymmetryMaskPlugin,
    _record_passes_asymmetry,
    fill_asymmetry_mask_numba_parallel,
    fill_asymmetry_mask_numba_serial,
)

__all__ = [
    "RecordsAsymmetryMaskPlugin",
    "_record_passes_asymmetry",
    "fill_asymmetry_mask_numba_parallel",
    "fill_asymmetry_mask_numba_serial",
]
