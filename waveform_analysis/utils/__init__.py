"""
Utils module - 工具函数
"""

try:
    from waveform_analysis.core.processing.loader import (
        WaveformLoaderCSV as _WaveformLoader,
    )
    from waveform_analysis.core.processing.loader import (
        get_raw_files,
        get_waveforms,
        get_waveforms_generator,
    )
except ImportError:
    from waveform_analysis.core.processing.loader import (
        WaveformLoader as _WaveformLoader,
    )
    from waveform_analysis.core.processing.loader import (
        get_raw_files,
        get_waveforms,
        get_waveforms_generator,
    )

from .daq import DAQAnalyzer, DAQRun
from .event_filters import (
    extract_channel_attributes,
    filter_coincidence_events,
    filter_events_by_function,
)
from .io import parse_files_generator

RawFileLoader = _WaveformLoader

__all__ = [
    "DAQRun",
    "DAQAnalyzer",
    "RawFileLoader",
    "get_raw_files",
    "get_waveforms",
    "get_waveforms_generator",
    "filter_events_by_function",
    "filter_coincidence_events",
    "extract_channel_attributes",
]
