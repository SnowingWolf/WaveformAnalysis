"""basic_features bundle - provides 'basic_features'。

BasicFeaturesPlugin 计算波形的基础特征（height/amp/area/max_abs_diff），
输出 ``BASIC_FEATURES_DTYPE`` 结构化数组。支持 records-backed 波形池与
st_waveforms / filtered_waveforms 波形源。
"""

from waveform_analysis.core.plugins.builtin.basic_features.plugin import (
    BASIC_FEATURES_DTYPE,
    BasicFeaturesPlugin,
)

__all__ = ["BasicFeaturesPlugin", "BASIC_FEATURES_DTYPE"]
