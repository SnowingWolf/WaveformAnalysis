"""
Shared dtype definitions for core processing.
"""

from __future__ import annotations

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

# 初始化 exporter
export, __all__ = exporter()

# Strax-inspired dtypes for structured data
# Record: A single waveform with metadata
DEFAULT_WAVE_LENGTH = export(1500, name="DEFAULT_WAVE_LENGTH")

ST_WAVEFORM_DTYPE = export(
    [
        ("baseline", "f8"),  # float64 for baseline (computed by WaveformStruct)
        ("baseline_upstream", "f8"),  # float64 for upstream baseline (optional)
        ("timestamp", "i8"),  # int64 for ps-level timestamps (ADC raw)
        ("dt", "i4"),  # sample interval (ns, aligned to time)
        ("event_length", "i4"),  # int32, consistent with RECORDS_DTYPE
        ("channel", "i2"),  # int16 for channel index (physical channel number)
        ("wave", "i2", (DEFAULT_WAVE_LENGTH,)),  # int16 for ADC data
    ],
    name="ST_WAVEFORM_DTYPE",
)


@export
def create_record_dtype(wave_length: int) -> np.dtype:
    """
    根据实际的波形长度动态创建 ST_WAVEFORM_DTYPE。

    参数:@
        wave_length: 波形数据的实际长度（采样点数）

    返回:
        动态创建的 ST_WAVEFORM_DTYPE，wave 字段长度为 wave_length

    示例:
        >>> dtype = create_record_dtype(1600)
        >>> arr = np.zeros(10, dtype=dtype)
        >>> print(arr["wave"].shape)  # (10, 1600)
    """
    return np.dtype(
        [
            ("baseline", "f8"),  # float64 for baseline (computed)
            ("baseline_upstream", "f8"),  # float64 for upstream baseline (optional)
            ("timestamp", "i8"),  # int64 for ps-level timestamps (ADC raw)
            ("dt", "i4"),  # sample interval (ns, aligned to time)
            ("event_length", "i4"),  # int32, consistent with RECORDS_DTYPE
            ("channel", "i2"),  # int16 for channel index (physical channel number)
            ("wave", "i2", (wave_length,)),  # int16 for ADC data
        ]
    )


# Peak: A detected peak in a waveform
PEAK_DTYPE = export(
    [
        ("time", "i8"),  # time of the peak
        ("area", "f4"),  # area of the peak
        ("height", "f4"),  # height of the peak
        ("width", "f4"),  # width of the peak
        ("channel", "i2"),  # channel index
        ("event_index", "i8"),  # index of the event in the dataset
    ],
    name="PEAK_DTYPE",
)

RECORDS_DTYPE = export(
    np.dtype(
        [
            ("timestamp", "i8"),  # ADC timestamp (ps)
            ("pid", "i4"),  # partition id (tie-breaker)
            ("channel", "i2"),  # physical channel
            ("baseline", "f8"),  # baseline (computed by WaveformStruct)
            ("baseline_upstream", "f8"),  # baseline from upstream plugin (optional)
            ("event_id", "i8"),  # sequential id after sorting
            ("dt", "i4"),  # sample interval (ns, aligned to time)
            ("trigger_type", "i2"),  # trigger type code
            ("flags", "u4"),  # bit flags
            ("wave_offset", "i8"),  # index in wave_pool
            ("event_length", "i4"),  # waveform length in samples
            ("time", "i8"),  # system time (ns, optional semantics)
        ]
    ),
    name="RECORDS_DTYPE",
)

EVENTS_DTYPE = export(RECORDS_DTYPE, name="EVENTS_DTYPE")
