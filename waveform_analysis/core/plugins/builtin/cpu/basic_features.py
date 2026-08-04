"""Basic Features Plugin - 兼容 shim。

``BasicFeaturesPlugin``（provides="basic_features"）与 ``BASIC_FEATURES_DTYPE``
已迁至 :mod:`waveform_analysis.core.plugins.builtin.basic_features`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.basic_features import (
    BASIC_FEATURES_DTYPE,
    BasicFeaturesPlugin,
)

__all__ = ["BasicFeaturesPlugin", "BASIC_FEATURES_DTYPE"]
