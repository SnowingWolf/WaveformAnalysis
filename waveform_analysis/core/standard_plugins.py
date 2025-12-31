from typing import Any, List, Optional

import numpy as np

from waveform_analysis.utils.data_processing.wavestruct import PEAK_DTYPE, RECORD_DTYPE

from .plugins import Option, Plugin


class RawFilesPlugin(Plugin):
    """Plugin to find raw CSV files."""

    provides = "raw_files"
    description = "Scan the data directory and group raw CSV files by channel number."
    options = {
        "n_channels": Option(default=2, type=int, help="Number of channels to load"),
        "start_channel_slice": Option(default=6, type=int, help="Starting channel index"),
        "data_root": Option(default="DAQ", type=str, help="Root directory for data"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> List[List[str]]:
        from waveform_analysis.utils.data_processing.loader import get_raw_files

        n_channels = context.get_config(self, "n_channels")
        start_channel_slice = context.get_config(self, "start_channel_slice")
        data_root = context.get_config(self, "data_root")

        # Support DAQ integration if daq_run is present in context
        daq_run = getattr(context, "daq_run", None)

        return get_raw_files(
            n_channels=n_channels + start_channel_slice,
            char=run_id,
            data_root=data_root,
            daq_run=daq_run,
        )


class WaveformsPlugin(Plugin):
    """Plugin to extract waveforms from raw files."""

    provides = "waveforms"
    depends_on = ["raw_files"]
    description = "Read and parse waveform data from raw CSV files."
    options = {
        "start_channel_slice": Option(default=6, type=int),
        "n_channels": Option(default=2, type=int),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        from waveform_analysis.utils.data_processing.loader import get_waveforms

        start = context.get_config(self, "start_channel_slice")
        n_channels = context.get_config(self, "n_channels")
        end = start + context.config.get("n_channels", 2)
        raw_files = context.get_data(run_id, "raw_files")
        return get_waveforms(raw_files[start:end], show_progress=context.config.get("show_progress", True))


class StWaveformsPlugin(Plugin):
    """Plugin to structure waveforms into NumPy arrays."""

    provides = "st_waveforms"
    depends_on = ["waveforms"]
    output_dtype = np.dtype(RECORD_DTYPE)

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        from waveform_analysis.utils.data_processing.processor import WaveformStruct

        waveforms = context.get_data(run_id, "waveforms")
        waveform_struct = WaveformStruct(waveforms)
        st_waveforms = waveform_struct.structrue_waveforms(show_progress=context.config.get("show_progress", True))
        # Also provide event_len as a side effect
        context._set_data(run_id, "event_len", waveform_struct.get_event_length())
        return st_waveforms


class HitFinderPlugin(Plugin):
    """Example implementation of the HitFinder as a plugin."""

    provides = "hits"
    depends_on = ["st_waveforms", "event_len"]
    input_dtype = {"st_waveforms": np.dtype(RECORD_DTYPE)}
    output_dtype = np.dtype(PEAK_DTYPE)

    def compute(self, context: Any, run_id: str, threshold: float = 10.0, **kwargs) -> List[np.ndarray]:
        from waveform_analysis.utils.data_processing.processor import find_hits

        st_waveforms = context.get_data(run_id, "st_waveforms")
        event_len = context.get_data(run_id, "event_len")

        hits_list = []
        for i in range(len(st_waveforms)):
            st_ch = st_waveforms[i]
            n = event_len[i]
            if len(st_ch) == 0:
                hits_list.append(np.zeros(0, dtype=kwargs.get("dtype", object)))
                continue

            waves_2d = np.stack(st_ch["wave"][:n])
            baselines = st_ch["baseline"][:n]
            hits = find_hits(waves_2d, baselines, threshold=threshold, **kwargs)
            hits["channel"] = i
            hits_list.append(hits)
        return hits_list
