"""DataFrame Plugin - 兼容 shim。

``DataFramePlugin``（provides="df"）已迁至
:mod:`waveform_analysis.core.plugins.builtin.df`。本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.df import DataFramePlugin

__all__ = ["DataFramePlugin"]
