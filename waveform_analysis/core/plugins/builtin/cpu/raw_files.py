"""Raw Files Plugin - 兼容 shim。

``RawFileNamesPlugin``（provides="raw_files"）已迁至
:mod:`waveform_analysis.core.plugins.builtin.raw_files`。本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.raw_files import RawFileNamesPlugin

__all__ = ["RawFileNamesPlugin"]
