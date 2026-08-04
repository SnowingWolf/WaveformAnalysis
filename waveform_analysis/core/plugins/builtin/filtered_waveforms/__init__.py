"""filtered_waveforms bundle - provides 'filtered_waveforms'。

FilteredWaveformsPlugin 对 ``st_waveforms`` 中每个事件的波形应用数字滤波
（Butterworth 带通 / Savitzky-Golay），输出与输入同构、仅 ``wave`` 字段为
float32 的结构化数组。共享滤波执行层（``build_filter_batches`` /
``filter_wave_pool_batch`` 等）位于 ``plugin``。
"""

from waveform_analysis.core.plugins.builtin.filtered_waveforms.plugin import (
    FilteredWaveformsPlugin,
)

__all__ = ["FilteredWaveformsPlugin"]
