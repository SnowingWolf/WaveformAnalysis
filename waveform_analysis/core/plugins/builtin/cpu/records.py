"""Records/wave_pool 插件 - 兼容 shim。

``RecordsPlugin`` / ``WavePoolPlugin`` / ``WavePoolFilteredPlugin`` 与共享的
``RecordsBundle`` 缓存逻辑（``_RecordsBundlePluginBase``、``get_records_bundle`` 等）
已分别迁至 bundle ``records`` / ``wave_pool`` / ``wave_pool_filtered``
（算法属主 ``builtin.records``，共享计算位于其 ``_compute``）。

本模块仅向后兼容转发全部符号。既有测试通过字符串路径 mock ``cpu.records.*``
（如 ``build_records_from_raw_files`` / ``_build_polarity_lookup`` /
``_cleanup_stale_bundles``），因此这些私有名也必须在此暴露；``records._compute``
在调用点懒加载这些名字以保证 mock 生效。
"""

from waveform_analysis.core.plugins.builtin.cpu._record_utils import RecordLookup
from waveform_analysis.core.plugins.builtin.cpu.waveforms import _build_polarity_lookup
from waveform_analysis.core.plugins.builtin.records._compute import (
    _apply_records_polarity,
    _build_records_bundle,
    _cleanup_stale_bundles,
    _records_from_bundle,
    _RecordsBundlePluginBase,
    _resolve_bundle_config_plugin,
    _resolve_records_upstream_depends,
    _wave_pool_from_bundle,
    get_records_bundle,
    get_records_bundle_cache_key,
)
from waveform_analysis.core.plugins.builtin.records.plugin import RecordsPlugin
from waveform_analysis.core.plugins.builtin.wave_pool.plugin import WavePoolPlugin
from waveform_analysis.core.plugins.builtin.wave_pool_filtered.plugin import (
    WavePoolFilteredPlugin,
)
from waveform_analysis.core.processing.records_builder import (
    build_records_from_raw_files,
    build_records_from_st_waveforms_sharded,
    build_records_from_v1725_files,
)

__all__ = [
    "RecordsPlugin",
    "WavePoolPlugin",
    "WavePoolFilteredPlugin",
    "_RecordsBundlePluginBase",
    "_apply_records_polarity",
    "_build_polarity_lookup",
    "_build_records_bundle",
    "_cleanup_stale_bundles",
    "_records_from_bundle",
    "_resolve_bundle_config_plugin",
    "_resolve_records_upstream_depends",
    "_wave_pool_from_bundle",
    "build_records_from_raw_files",
    "build_records_from_st_waveforms_sharded",
    "build_records_from_v1725_files",
    "get_records_bundle",
    "get_records_bundle_cache_key",
    "RecordLookup",
]
