"""raw_files bundle - provides 'raw_files'。

RawFileNamesPlugin 扫描数据目录并按通道分组原始 CSV 文件，是数据处理流程的起点。
支持 DAQ 集成，可以直接从 DAQ 元数据中获取文件列表。
"""

from waveform_analysis.core.plugins.builtin.raw_files.plugin import RawFileNamesPlugin

__all__ = ["RawFileNamesPlugin"]
