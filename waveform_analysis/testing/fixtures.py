"""Testing fixtures for plugin development."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.processing.waveform_struct import create_record_dtype

__all__ = [
    "make_fake_st_waveforms",
    "make_tiny_context",
]


def make_fake_st_waveforms(
    n_channels: int = 2,
    n_events: int = 3,
    wave_len: int = 20,
    start_timestamp: int = 0,
) -> List[np.ndarray]:
    """Create a minimal st_waveforms-like payload for tests.

    Returns a list of structured arrays, one per channel.
    """
    dtype = create_record_dtype(wave_len)
    st_waveforms: List[np.ndarray] = []

    for ch in range(n_channels):
        records = np.zeros(n_events, dtype=dtype)
        records["baseline"] = 0.0
        records["timestamp"] = start_timestamp + np.arange(n_events) * 100
        records["event_length"] = wave_len
        records["channel"] = ch
        for idx in range(n_events):
            records["wave"][idx] = np.arange(wave_len, dtype=np.float32) + ch
        st_waveforms.append(records)

    return st_waveforms


def make_tiny_context(
    storage_dir: Union[Path, str],
    run_id: str = "run_001",
    st_waveforms: Optional[List[np.ndarray]] = None,
) -> Context:
    """Create a Context with a temp storage dir and injected st_waveforms."""
    ctx = Context(storage_dir=str(storage_dir))
    if st_waveforms is None:
        st_waveforms = make_fake_st_waveforms()
    ctx._set_data(run_id, "st_waveforms", st_waveforms)
    return ctx
