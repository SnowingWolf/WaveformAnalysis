"""records bundle - provides 'records'。

本 bundle 是 records 家族的算法属主：共享计算（RecordsBundle 缓存、bundle 构建、
``_RecordsBundlePluginBase``）位于 ``_compute``，兄弟 bundle ``wave_pool``
单向依赖本模块。
"""

from waveform_analysis.core.plugins.builtin.records.plugin import RecordsPlugin

__all__ = ["RecordsPlugin"]
