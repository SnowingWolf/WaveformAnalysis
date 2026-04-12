"""Shared helpers for streaming tests."""

import numpy as np

from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.core.plugins.core.streaming import StreamingPlugin
from waveform_analysis.core.processing.chunk import Chunk

RECORD_DTYPE = np.dtype(
    [
        ("time", "<i8"),
        ("dt", "<i4"),
        ("length", "<i4"),
        ("value", "<f8"),
    ]
)

SIMPLE_DTYPE = np.dtype(
    [
        ("timestamp", "<i8"),
        ("value", "<f8"),
    ]
)


def make_test_records(n=10, start_time=0, dt=10, length=100, gap=0):
    """Create test records with time fields."""
    data = np.zeros(n, dtype=RECORD_DTYPE)
    current_time = start_time
    for i in range(n):
        data[i]["time"] = current_time
        data[i]["dt"] = dt
        data[i]["length"] = length
        data[i]["value"] = float(i)
        current_time += dt * length + gap
    return data


def make_simple_data(n=10, start_time=0, step=100):
    """Create simple timestamped data."""
    data = np.zeros(n, dtype=SIMPLE_DTYPE)
    for i in range(n):
        data[i]["timestamp"] = start_time + i * step
        data[i]["value"] = float(i)
    return data


class SimpleStreamingPlugin(StreamingPlugin):
    provides = "simple_stream"
    depends_on = []
    output_dtype = SIMPLE_DTYPE
    chunk_size = 5
    parallel = False

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        return chunk


class TransformStreamingPlugin(StreamingPlugin):
    provides = "transform_stream"
    depends_on = ["source_data"]
    output_dtype = SIMPLE_DTYPE
    chunk_size = 5
    parallel = False

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        new_data = chunk.data.copy()
        new_data["value"] = new_data["value"] * 2
        return Chunk(
            data=new_data,
            start=chunk.start,
            end=chunk.end,
            run_id=chunk.run_id,
            data_type=self.provides,
            time_field=chunk.time_field,
        )


class StatefulStreamingPlugin(StreamingPlugin):
    provides = "stateful_stream"
    depends_on = []
    output_dtype = SIMPLE_DTYPE
    chunk_size = 5
    parallel = False
    is_stateful = True
    reset_on_break = True

    def __init__(self):
        super().__init__()
        self._counter = 0

    def reset_state(self):
        self._counter = 0

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        self._counter += 1
        new_data = chunk.data.copy()
        new_data["value"] = new_data["value"] + self._counter
        return Chunk(
            data=new_data,
            start=chunk.start,
            end=chunk.end,
            run_id=chunk.run_id,
            data_type=self.provides,
            time_field=chunk.time_field,
        )


class SourceDataPlugin(Plugin):
    provides = "source_data"
    output_dtype = SIMPLE_DTYPE

    def compute(self, context, run_id, **kwargs):
        return make_simple_data(20, start_time=0, step=100)
