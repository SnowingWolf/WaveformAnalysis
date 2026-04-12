"""Shared helpers for DAQ adapter tests."""

import numpy as np


def make_v1725_single_wave_blob(
    *,
    channel: int = 0,
    timestamp: int = 1234,
    baseline: int = 321,
    trunc: bool = False,
    samples: np.ndarray | None = None,
) -> bytes:
    if samples is None:
        samples = np.array([11, 12], dtype=np.int16)
    samples = np.asarray(samples, dtype=np.int16)
    payload = samples.tobytes()

    event_header = bytearray(16)
    channel_mask = 1 << int(channel)
    event_header[4] = channel_mask & 0xFF
    event_header[11] = (channel_mask >> 8) & 0xFF

    ch_header = bytearray(12)
    ch_size = 3 + (len(payload) // 4)
    ch_header[0] = ch_size & 0xFF
    ch_header[1] = (ch_size >> 8) & 0xFF
    ch_header[2] = (ch_size >> 16) & 0x3F
    if trunc:
        ch_header[3] |= 0x40
    ch_header[4:10] = int(timestamp).to_bytes(6, byteorder="little", signed=False)
    ch_header[10:12] = int(baseline).to_bytes(2, byteorder="little", signed=False)
    return bytes(event_header + ch_header + payload)
