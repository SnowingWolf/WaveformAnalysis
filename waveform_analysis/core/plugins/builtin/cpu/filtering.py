"""CPU Filtering Plugin - 兼容 shim。

``FilteredWaveformsPlugin``（provides="filtered_waveforms"）及共享滤波执行层
（``build_filter_batches`` / ``filter_wave_pool_batch`` 等）已迁至
:mod:`waveform_analysis.core.plugins.builtin.filtered_waveforms`。
本模块仅向后兼容转发全部符号（含 records 侧依赖的共享执行函数）。
"""

from waveform_analysis.core.plugins.builtin.filtered_waveforms.plugin import (
    FILTER_ENGINE_VERSION,
    FILTER_OPTION_NAMES,
    BatchSelector,
    FilteredWaveformsPlugin,
    apply_filter_to_record_wave,
    build_channel_batches,
    build_channel_selectors,
    build_filter_batches,
    create_filtered_waveform_dtype,
    filter_wave_pool_batch,
    get_filter_base_values,
    resolve_filter_config,
    selector_length,
)

__all__ = [
    "FilteredWaveformsPlugin",
    "FILTER_ENGINE_VERSION",
    "FILTER_OPTION_NAMES",
    "BatchSelector",
    "get_filter_base_values",
    "resolve_filter_config",
    "create_filtered_waveform_dtype",
    "apply_filter_to_record_wave",
    "build_channel_selectors",
    "build_channel_batches",
    "selector_length",
    "build_filter_batches",
    "filter_wave_pool_batch",
]
