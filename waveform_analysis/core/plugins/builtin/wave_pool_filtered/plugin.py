"""WavePoolFilteredPlugin 类实现 - 构建与 records 对齐的滤波波形池。"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.filtering import (
    FILTER_ENGINE_VERSION,
    build_filter_batches,
    filter_wave_pool_batch,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin


class WavePoolFilteredPlugin(Plugin):
    """Build a filtered wave_pool aligned to the existing records layout."""

    provides = "wave_pool_filtered"
    depends_on = ["records", "wave_pool"]
    description = "Build filtered wave_pool from records-backed raw waveforms."
    version = FILTER_ENGINE_VERSION
    save_when = "always"
    output_dtype = np.dtype(np.float32)
    options = {
        "filter_type": Option(default="SG", type=str, help="滤波器类型: 'BW' 或 'SG'"),
        "lowcut": Option(default=0.1, type=float, help="BW 低频截止"),
        "highcut": Option(default=0.5, type=float, help="BW 高频截止"),
        "fs": Option(default=0.5, type=float, help="BW 采样率（GHz）"),
        "filter_order": Option(default=4, type=int, help="BW 阶数"),
        "sg_window_size": Option(default=11, type=int, help="SG 窗口大小（奇数）"),
        "sg_poly_order": Option(default=2, type=int, help="SG 多项式阶数"),
        "max_workers": Option(
            default=None,
            type=int,
            help="并行工作线程数；None 使用 CPU 核心数，1 或 0 禁用并行",
        ),
        "batch_size": Option(
            default=0,
            type=int,
            help="每批次记录数（0 表示不分批，整个通道一次处理）",
        ),
        "channel_config": Option(
            default=None,
            type=dict,
            help="按 (board, channel) 的插件通道覆盖配置，可覆盖滤波参数。",
        ),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        records = context.get_data(run_id, "records")
        wave_pool = context.get_data(run_id, "wave_pool")
        if not isinstance(records, np.ndarray):
            raise ValueError("wave_pool_filtered expects records as a structured array")
        if not isinstance(wave_pool, np.ndarray):
            raise ValueError("wave_pool_filtered expects wave_pool as a numpy array")
        if records.dtype.names is None:
            raise ValueError("wave_pool_filtered expects structured records input")
        required = ("wave_offset", "event_length")
        missing = [name for name in required if name not in records.dtype.names]
        if missing:
            raise ValueError(f"wave_pool_filtered records missing required fields: {missing}")

        filtered_pool = np.zeros(len(wave_pool), dtype=np.float32)
        if len(records) == 0 or len(wave_pool) == 0:
            return filtered_pool

        boards = (
            records["board"]
            if "board" in records.dtype.names
            else np.zeros(len(records), dtype=np.int16)
        )
        channels = (
            records["channel"]
            if "channel" in records.dtype.names
            else np.zeros(len(records), dtype=np.int16)
        )

        batch_size = int(context.get_config(self, "batch_size"))
        if batch_size < 0:
            raise ValueError(f"batch_size ({batch_size}) 必须大于等于 0")

        filter_batches = build_filter_batches(context, self, run_id, boards, channels, batch_size)
        if not filter_batches:
            return filtered_pool

        max_workers = context.get_config(self, "max_workers")
        allow_parallel = max_workers is None or (isinstance(max_workers, int) and max_workers > 1)
        use_parallel = allow_parallel and len(filter_batches) > 1

        tasks = [
            (
                records,
                wave_pool,
                batch_selector,
                filter_config["filter_type"],
                filter_config["bw_sos"],
                filter_config["sg_window_size"],
                filter_config["sg_poly_order"],
            )
            for _channel, batch_selector, filter_config in filter_batches
        ]
        if use_parallel:
            from waveform_analysis.core.execution.manager import parallel_map

            results = parallel_map(
                filter_wave_pool_batch,
                tasks,
                executor_type="thread",
                max_workers=max_workers,
                executor_name="wave_pool_filtered",
            )
        else:
            results = [filter_wave_pool_batch(task) for task in tasks]

        for batch_segments in results:
            for offset, filtered_wave in batch_segments:
                filtered_pool[offset : offset + len(filtered_wave)] = filtered_wave

        return filtered_pool


__all__ = ["WavePoolFilteredPlugin"]
