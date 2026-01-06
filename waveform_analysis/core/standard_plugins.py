"""
Standard Plugins 模块 - 包含波形分析流程的标准插件实现。

定义了从原始文件扫描、波形提取、结构化到特征计算和事件配对的完整插件链。
这些插件是 WaveformDataset 内部调用的核心逻辑单元。
"""

from typing import Any, Dict, List

import numpy as np

from .plugins import Option, Plugin
from .processor import PEAK_DTYPE, RECORD_DTYPE, WaveformStruct, find_hits


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
        from waveform_analysis.utils.loader import get_raw_files

        n_channels = context.get_config(self, "n_channels")
        start_channel_slice = context.get_config(self, "start_channel_slice")
        data_root = context.get_config(self, "data_root")

        # Support DAQ integration if daq_run is present in context
        daq_run = getattr(context, "daq_run", None)

        return get_raw_files(
            n_channels=n_channels + start_channel_slice,
            run_name=run_id,
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
        "channel_workers": Option(default=None, help="Number of parallel workers for channel-level processing (None=auto, uses min(n_channels, cpu_count))"),
        "channel_executor": Option(default="thread", type=str, help="Executor type for channel-level parallelism: 'thread' or 'process'"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        import multiprocessing
        from waveform_analysis.utils.loader import get_waveforms

        start = context.get_config(self, "start_channel_slice")
        n_channels = context.config.get("n_channels", 2)
        end = start + n_channels
        raw_files = context.get_data(run_id, "raw_files")
        
        # Get parallel processing configuration
        channel_workers = context.get_config(self, "channel_workers")
        channel_executor = context.get_config(self, "channel_executor")
        
        # Enable multithreading acceleration by default: use number of channels or CPU count, whichever is smaller
        if channel_workers is None:
            channel_workers = min(n_channels, multiprocessing.cpu_count())
        
        show_progress = context.config.get("show_progress", True)
        
        return get_waveforms(
            raw_filess=raw_files[start:end],
            show_progress=show_progress,
            channel_workers=channel_workers,
            channel_executor=channel_executor,
        )


class StWaveformsPlugin(Plugin):
    """Plugin to structure waveforms into NumPy arrays."""

    provides = "st_waveforms"
    depends_on = ["waveforms"]
    save_when = "always"
    output_dtype = np.dtype(RECORD_DTYPE)

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        waveforms = context.get_data(run_id, "waveforms")
        waveform_struct = WaveformStruct(waveforms)
        st_waveforms = waveform_struct.structure_waveforms(show_progress=context.config.get("show_progress", True))
        return st_waveforms


class HitFinderPlugin(Plugin):
    """Example implementation of the HitFinder as a plugin."""

    provides = "hits"
    depends_on = ["st_waveforms"]
    input_dtype = {"st_waveforms": np.dtype(RECORD_DTYPE)}
    output_dtype = np.dtype(PEAK_DTYPE)

    def compute(self, context: Any, run_id: str, threshold: float = 10.0, **kwargs) -> List[np.ndarray]:
        st_waveforms = context.get_data(run_id, "st_waveforms")

        hits_list = []
        for i in range(len(st_waveforms)):
            st_ch = st_waveforms[i]
            if len(st_ch) == 0:
                hits_list.append(np.zeros(0, dtype=kwargs.get("dtype", object)))
                continue

            # 使用每个通道的全部事件数
            waves_2d = np.stack(st_ch["wave"])
            hits = find_hits(waves_2d, st_ch["baseline"], threshold=threshold)
            hits_list.append(hits)
        return hits_list


class BasicFeaturesPlugin(Plugin):
    """Plugin to compute basic features (peaks and charges)."""

    provides = "basic_features"
    depends_on = ["st_waveforms"]
    save_when = "never"
    options = {
        "peaks_range": Option(default=None, type=tuple),
        "charge_range": Option(default=None, type=tuple),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> Dict[str, List[np.ndarray]]:
        from waveform_analysis.core.processor import WaveformProcessor

        st_waveforms = context.get_data(run_id, "st_waveforms")

        peaks_range = context.get_config(self, "peaks_range")
        charge_range = context.get_config(self, "charge_range")

        processor = WaveformProcessor(n_channels=len(st_waveforms))
        peaks, charges = processor.compute_basic_features(st_waveforms, peaks_range, charge_range)

        return {"peaks": peaks, "charges": charges}


class PeaksPlugin(Plugin):
    """Plugin to provide peaks from basic_features."""

    provides = "peaks"
    depends_on = ["basic_features"]
    save_when = "always"

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        return context.get_data(run_id, "basic_features")["peaks"]


class ChargesPlugin(Plugin):
    """Plugin to provide charges from basic_features."""

    provides = "charges"
    depends_on = ["basic_features"]
    save_when = "always"

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        return context.get_data(run_id, "basic_features")["charges"]


class DataFramePlugin(Plugin):
    """Plugin to build the initial single-channel events DataFrame."""

    provides = "df"
    depends_on = ["st_waveforms", "peaks", "charges"]
    save_when = "always"

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        from waveform_analysis.core.processor import WaveformProcessor

        st_waveforms = context.get_data(run_id, "st_waveforms")
        peaks = context.get_data(run_id, "peaks")
        charges = context.get_data(run_id, "charges")

        processor = WaveformProcessor(n_channels=len(st_waveforms))
        df = processor.build_dataframe(
            st_waveforms,
            peaks,
            charges,
        )
        return df


class GroupedEventsPlugin(Plugin):
    """Plugin to group events by time window."""

    provides = "df_events"
    depends_on = ["df"]
    save_when = "always"
    options = {
        "time_window_ns": Option(default=100.0, type=float),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        from waveform_analysis.core.analyzer import EventAnalyzer

        df = context.get_data(run_id, "df")
        tw = context.get_config(self, "time_window_ns")

        # We need n_channels and start_channel_slice from context config
        n_channels = context.config.get("n_channels", 2)
        start_channel_slice = context.config.get("start_channel_slice", 6)

        analyzer = EventAnalyzer(n_channels=n_channels, start_channel_slice=start_channel_slice)
        # 从context配置中获取优化参数（如果存在）
        use_numba = context.config.get("use_numba", True)
        n_processes = context.config.get("n_processes", None)
        return analyzer.group_events(df, tw, use_numba=use_numba, n_processes=n_processes)


class PairedEventsPlugin(Plugin):
    """Plugin to pair events across channels."""

    provides = "df_paired"
    depends_on = ["df_events"]
    save_when = "always"

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        from waveform_analysis.core.analyzer import EventAnalyzer

        df_events = context.get_data(run_id, "df_events")

        n_channels = context.config.get("n_channels", 2)
        start_channel_slice = context.config.get("start_channel_slice", 6)
        time_window_ns = context.config.get("time_window_ns", 100.0)  # 从配置获取时间窗口

        analyzer = EventAnalyzer(n_channels=n_channels, start_channel_slice=start_channel_slice)
        return analyzer.pair_events(df_events, time_window_ns=time_window_ns)
