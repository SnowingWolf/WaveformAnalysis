# -*- coding: utf-8 -*-
"""
Standalone demo for custom StreamingPlugin implementations.

This file is not imported by the package. It defines example streaming plugins and
shows how to register and iterate over a streaming pipeline.
"""

from typing import Any

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.foundation.constants import FeatureDefaults
from waveform_analysis.core.plugins.builtin.cpu import RawFilesPlugin, WaveformsPlugin
from waveform_analysis.core.plugins.core.streaming import StreamingPlugin, get_streaming_context
from waveform_analysis.core.processing.chunk import Chunk, get_endtime
from waveform_analysis.core.processing.waveform_struct import WaveformStruct


class StreamingStWaveformsPlugin(StreamingPlugin):
    """Stream structured waveforms from raw waveforms."""

    provides = "st_waveforms_stream"
    depends_on = ["waveforms"]
    description = "Stream structured waveforms from raw waveforms"

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        """Convert raw waveforms in a chunk into structured waveforms."""
        if isinstance(chunk.data, list):
            waveforms = chunk.data
        elif isinstance(chunk.data, np.ndarray):
            waveforms = [chunk.data]
        else:
            return None

        struct = WaveformStruct(waveforms)
        start_channel_slice = context.config.get("start_channel_slice", 0)
        st_waveforms = struct.structure_waveforms(
            show_progress=False,
            start_channel_slice=start_channel_slice,
        )

        if len(st_waveforms) == 0:
            return None

        merged = np.concatenate(st_waveforms) if len(st_waveforms) > 1 else st_waveforms[0]
        if len(merged) > 0 and "time" in merged.dtype.names:
            time_values = merged["time"]
            endtime = get_endtime(merged)
            start_time = int(np.min(time_values))
            end_time = int(np.max(endtime))
        else:
            start_time = chunk.start
            end_time = chunk.end

        return Chunk(
            data=merged,
            start=start_time,
            end=end_time,
            run_id=run_id,
            data_type=self.provides,
        )


class StreamingBasicFeaturesPlugin(StreamingPlugin):
    """Compute height and area features from structured waveforms."""

    provides = "basic_features_stream"
    depends_on = ["st_waveforms_stream"]
    description = "Stream basic features (height and area) from structured waveforms"

    def __init__(self) -> None:
        super().__init__()
        self.peaks_range = FeatureDefaults.PEAK_RANGE
        self.charge_range = FeatureDefaults.CHARGE_RANGE

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        if len(chunk.data) == 0:
            return None

        waves = chunk.data["wave"]
        baselines = chunk.data["baseline"]
        if waves.ndim != 2:
            return None

        start_p, end_p = self.peaks_range
        start_c, end_c = self.charge_range

        waves_p = waves[:, start_p:end_p]
        height_vals = np.max(waves_p, axis=1) - np.min(waves_p, axis=1)

        waves_c = waves[:, start_c:end_c]
        area_vals = np.sum(baselines[:, np.newaxis] - waves_c, axis=1)

        feature_dtype = np.dtype(
            [
                ("time", "<i8"),
                ("height", "<f4"),
                ("area", "<f4"),
            ]
        )
        n_items = len(height_vals)
        features = np.zeros(n_items, dtype=feature_dtype)
        if "time" in chunk.data.dtype.names:
            features["time"] = chunk.data["time"][:n_items]
        else:
            features["time"] = np.arange(n_items)
        features["height"] = height_vals
        features["area"] = area_vals

        return Chunk(
            data=features,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )


class StreamingFilterPlugin(StreamingPlugin):
    """Filter chunks by area range."""

    provides = "filtered_stream"
    depends_on = ["basic_features_stream"]
    description = "Filter chunks based on conditions"

    def __init__(self) -> None:
        super().__init__()
        self.min_area = 0.0
        self.max_area = np.inf

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        if len(chunk.data) == 0:
            return None

        if "area" in chunk.data.dtype.names:
            mask = (chunk.data["area"] >= self.min_area) & (
                chunk.data["area"] <= self.max_area
            )
            filtered_data = chunk.data[mask]
        else:
            filtered_data = chunk.data

        if len(filtered_data) == 0:
            return None

        if "time" in filtered_data.dtype.names:
            time_values = filtered_data["time"]
            if "endtime" in filtered_data.dtype.names:
                endtime = get_endtime(filtered_data)
            else:
                endtime = time_values
            start_time = int(np.min(time_values))
            end_time = int(np.max(endtime))
        else:
            start_time = chunk.start
            end_time = chunk.end

        return Chunk(
            data=filtered_data,
            start=start_time,
            end=end_time,
            run_id=run_id,
            data_type=self.provides,
        )


def run_demo(run_id: str = "run_001", data_root: str = "DAQ") -> None:
    """Run a minimal streaming pipeline demo."""
    ctx = Context(config={"data_root": data_root})
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        StreamingStWaveformsPlugin(),
        StreamingBasicFeaturesPlugin(),
        StreamingFilterPlugin(),
    )

    stream_ctx = get_streaming_context(ctx, run_id=run_id, chunk_size=50000)
    for index, chunk in enumerate(stream_ctx.get_stream("filtered_stream")):
        print(f"chunk {index}: size={len(chunk.data)} range=({chunk.start}, {chunk.end})")
        if index >= 2:
            break


if __name__ == "__main__":
    run_demo()
