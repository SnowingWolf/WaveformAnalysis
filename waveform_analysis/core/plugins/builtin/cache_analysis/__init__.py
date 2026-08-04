"""cache_analysis bundle - provides 'cache_analysis'。

CacheAnalysisPlugin 收集缓存统计并可选返回过滤后的缓存条目与诊断问题，
用于交互式检查，默认不写入主缓存。
"""

from waveform_analysis.core.plugins.builtin.cache_analysis.plugin import (
    CacheAnalysisPlugin,
)

__all__ = ["CacheAnalysisPlugin"]
