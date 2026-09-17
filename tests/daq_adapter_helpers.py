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


def make_vx2730_bin_bytes(
    events: list[dict],
    *,
    header: int = 0xCAED,
    n_samples: int = 4,
) -> bytes:
    """Build a CoMPASS VX2730 .BIN payload.

    Each event dict may contain board, channel, timestamp, energy, energy_cal,
    energy_short, flags, wave_code and samples; missing fields default to 0.
    """
    blob = bytearray(int(header).to_bytes(2, byteorder="little"))
    for event in events:
        blob += int(event.get("board", 0)).to_bytes(2, "little")
        blob += int(event.get("channel", 0)).to_bytes(2, "little")
        blob += int(event.get("timestamp", 0)).to_bytes(8, "little")
        if header & 0x1:
            blob += int(event.get("energy", 0)).to_bytes(2, "little")
        if header & 0x2:
            blob += np.float64(event.get("energy_cal", 0.0)).tobytes()
        if header & 0x4:
            blob += int(event.get("energy_short", 0)).to_bytes(2, "little")
        blob += int(event.get("flags", 0)).to_bytes(4, "little")
        if header & 0x8:
            samples = np.asarray(event.get("samples", np.zeros(n_samples)), dtype="<u2")
            blob += int(event.get("wave_code", 1)).to_bytes(1, "little")
            blob += int(event.get("n_samples", len(samples))).to_bytes(4, "little")
            blob += samples.tobytes()
    return bytes(blob)
