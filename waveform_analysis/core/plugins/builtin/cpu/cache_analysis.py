"""Cache analysis plugin - 兼容 shim。

``CacheAnalysisPlugin``（provides="cache_analysis"）已迁至
:mod:`waveform_analysis.core.plugins.builtin.cache_analysis`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.cache_analysis import CacheAnalysisPlugin

__all__ = ["CacheAnalysisPlugin"]
