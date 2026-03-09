"""
CPU Filtering Plugin - 使用 scipy 进行波形滤波

**加速器**: CPU (scipy)
**功能**: 波形滤波（Butterworth 带通滤波、Savitzky-Golay 滤波）

本插件提供两种滤波方法：
- Butterworth 带通滤波器 (BW)
- Savitzky-Golay 滤波器 (SG)

输出格式与 st_waveforms 保持一致（结构化数组），只是 wave 字段为滤波后的数据。
"""

import logging
from typing import Any, List, Optional, Tuple

import numpy as np
from scipy.signal import butter, savgol_filter, sosfiltfilt

from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import ST_WAVEFORM_DTYPE

logger = logging.getLogger(__name__)


def _filter_channel(args):
    """滤波单个通道的波形数据（线程安全）。

    Parameters
    ----------
    args : tuple
        (waveforms_i16, indices, filter_type, bw_sos, sg_window_size, sg_poly_order)
        waveforms_i16: shape (n_events, n_samples), int16
    """
    waveforms_i16, indices, filter_type, bw_sos, sg_window_size, sg_poly_order = args
    waveforms_f64 = waveforms_i16[indices].astype(np.float64, copy=False)
    if filter_type == "BW":
        filtered = sosfiltfilt(bw_sos, waveforms_f64, axis=-1)
    else:  # SG
        if sg_window_size <= sg_poly_order:
            filtered = waveforms_f64
        else:
            filtered = savgol_filter(
                waveforms_f64,
                window_length=sg_window_size,
                polyorder=sg_poly_order,
                axis=-1,
                mode="interp",
            )

    np.clip(filtered, -32768, 32767, out=filtered)
    return filtered.astype(np.int16, copy=False)


class FilteredWaveformsPlugin(Plugin):
    provides = "filtered_waveforms"
    depends_on = ["st_waveforms"]
    description = "Apply filtering to waveforms using Butterworth or Savitzky-Golay filters."
    version = "2.4.0"
    save_when = "target"

    output_dtype = np.dtype(ST_WAVEFORM_DTYPE)  # 默认值；compute() 中会动态更新

    options = {
        "filter_type": Option(default="SG", type=str, help="滤波器类型: 'BW' 或 'SG'"),
        "lowcut": Option(default=0.1, type=float, help="BW 低频截止"),
        "highcut": Option(default=0.5, type=float, help="BW 高频截止"),
        "fs": Option(default=0.5, type=float, help="BW 采样率（GHz）"),
        "filter_order": Option(default=4, type=int, help="BW 阶数"),
        "sg_window_size": Option(default=11, type=int, help="SG 窗口大小（奇数）"),
        "sg_poly_order": Option(default=2, type=int, help="SG 多项式阶数"),
        "daq_adapter": Option(
            default=None,
            type=str,
            help="DAQ 适配器名称（用于自动推断采样率）",
        ),
        # 你也可以加：sg_mode / sg_cval 等（这里先不扩展 options）
        "max_workers": Option(
            default=None,
            type=int,
            help="并行工作线程数；None 使用 CPU 核心数，1 或 0 禁用并行",
        ),
        "batch_size": Option(
            default=0,
            type=int,
            help="每批次事件数（0 表示不分批，整个通道一次处理）",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        filter_type: str = context.get_config(self, "filter_type")
        if filter_type not in ("BW", "SG"):
            raise ValueError(f"不支持的滤波器类型: {filter_type}. 请使用 'BW' 或 'SG'.")

        bw_sos: Optional[np.ndarray] = None
        sg_window_size: Optional[int] = None
        sg_poly_order: Optional[int] = None

        if filter_type == "BW":
            lowcut = float(context.get_config(self, "lowcut"))
            highcut = float(context.get_config(self, "highcut"))
            fs = float(context.get_config(self, "fs"))
            daq_adapter = context.get_config(self, "daq_adapter")
            if not self._has_config(context, "fs"):
                fs = self._get_fs_from_adapter(daq_adapter, fs)
            order = int(context.get_config(self, "filter_order"))

            if fs <= 0:
                raise ValueError(f"fs ({fs}) 必须大于 0")
            if order <= 0:
                raise ValueError(f"滤波器阶数 ({order}) 必须大于 0")
            if lowcut <= 0 or highcut <= 0:
                raise ValueError("截止频率必须大于 0")
            if lowcut >= highcut:
                raise ValueError(f"lowcut ({lowcut}) 必须小于 highcut ({highcut})")
            if highcut >= fs / 2:
                raise ValueError(f"highcut ({highcut}) 必须小于奈奎斯特频率 ({fs / 2})")

            # SciPy: 直接用 fs 参数，避免手动归一化
            bw_sos = butter(order, [lowcut, highcut], btype="band", output="sos", fs=fs)
            logger.debug(
                "设计 Butterworth 带通滤波器: order=%s lowcut=%s highcut=%s fs=%s",
                order,
                lowcut,
                highcut,
                fs,
            )

        else:  # SG
            sg_window_size = int(context.get_config(self, "sg_window_size"))
            sg_poly_order = int(context.get_config(self, "sg_poly_order"))

            if sg_window_size <= 0:
                raise ValueError(f"SG 窗口大小 ({sg_window_size}) 必须大于 0")
            if sg_poly_order < 0:
                raise ValueError(f"SG 多项式阶数 ({sg_poly_order}) 必须大于等于 0")
            if sg_window_size % 2 == 0:
                sg_window_size += 1
                logger.warning("SG 窗口大小已调整为奇数: %s", sg_window_size)
            if sg_poly_order >= sg_window_size:
                raise ValueError(f"SG 多项式阶数 ({sg_poly_order}) 必须小于窗口大小 ({sg_window_size})")

            logger.debug("SG 滤波器参数: window_size=%s poly_order=%s", sg_window_size, sg_poly_order)

        st_waveforms = context.get_data(run_id, "st_waveforms")
        if not isinstance(st_waveforms, np.ndarray):
            raise ValueError("filtered_waveforms expects st_waveforms as a single structured array")

        # 动态匹配 st_waveforms 的实际 dtype（wave 长度可能不是默认的 1500）
        if st_waveforms.dtype != self.output_dtype:
            self.output_dtype = st_waveforms.dtype

        if len(st_waveforms) == 0:
            return np.zeros(0, dtype=st_waveforms.dtype)

        output = np.copy(st_waveforms)

        if "channel" not in st_waveforms.dtype.names:
            raise ValueError("st_waveforms missing required 'channel' field for filtering")
        if "wave" not in st_waveforms.dtype.names:
            raise ValueError("st_waveforms missing required 'wave' field for filtering")

        channels = st_waveforms["channel"]
        waveforms_i16 = st_waveforms["wave"]
        if waveforms_i16.ndim != 2:
            raise ValueError("st_waveforms['wave'] must be 2D (n_events, n_samples)")
        n_samples = waveforms_i16.shape[1]

        batch_size = int(context.get_config(self, "batch_size"))
        if batch_size < 0:
            raise ValueError(f"batch_size ({batch_size}) 必须大于等于 0")

        if filter_type == "SG":
            # 对全部事件共享同一个窗口长度，避免每个任务重复推导。
            sg_window_size = min(sg_window_size, n_samples)
            if sg_window_size % 2 == 0:
                sg_window_size -= 1
            if sg_window_size <= sg_poly_order:
                logger.warning(
                    "SG 窗口长度(%s)不大于多项式阶数(%s)，返回原始波形",
                    sg_window_size,
                    sg_poly_order,
                )
                return output

        channel_batches = self._build_channel_batches(channels, batch_size)
        if not channel_batches:
            return output

        max_workers = context.get_config(self, "max_workers")
        allow_parallel = max_workers is None or (isinstance(max_workers, int) and max_workers > 1)
        use_parallel = allow_parallel and len(channel_batches) > 1

        if use_parallel:
            from waveform_analysis.core.execution.manager import parallel_map

            tasks = [
                (waveforms_i16, batch_indices, filter_type, bw_sos, sg_window_size, sg_poly_order)
                for _channel, batch_indices in channel_batches
            ]
            logger.debug(
                "并行滤波: tasks=%s max_workers=%s batch_size=%s",
                len(tasks),
                max_workers,
                batch_size,
            )
            results = parallel_map(
                _filter_channel,
                tasks,
                executor_type="thread",
                max_workers=max_workers,
                executor_name="filtered_waveforms",
            )
            for (_channel, batch_indices), filtered_i16 in zip(channel_batches, results):
                output["wave"][batch_indices] = filtered_i16
        else:
            # 串行路径：单任务或显式禁用并行
            for ch, batch_indices in channel_batches:
                logger.debug(
                    "处理通道批次: channel=%s n_events=%s n_samples=%s",
                    ch,
                    len(batch_indices),
                    n_samples,
                )
                filtered_i16 = _filter_channel(
                    (waveforms_i16, batch_indices, filter_type, bw_sos, sg_window_size, sg_poly_order)
                )
                output["wave"][batch_indices] = filtered_i16

        return output

    def _build_channel_batches(self, channels: np.ndarray, batch_size: int) -> List[Tuple[int, np.ndarray]]:
        """将事件按 channel 分组，并按 batch_size 切分为批次索引。"""
        if channels.size == 0:
            return []

        ordered_indices = np.argsort(channels, kind="stable")
        sorted_channels = channels[ordered_indices]
        group_starts = np.flatnonzero(np.r_[True, sorted_channels[1:] != sorted_channels[:-1]])
        group_ends = np.r_[group_starts[1:], len(ordered_indices)]

        batches: List[Tuple[int, np.ndarray]] = []
        for start, end in zip(group_starts, group_ends):
            channel_indices = ordered_indices[start:end]
            if channel_indices.size == 0:
                continue
            channel = int(sorted_channels[start])
            if batch_size <= 0 or channel_indices.size <= batch_size:
                batches.append((channel, channel_indices))
                continue
            for offset in range(0, channel_indices.size, batch_size):
                batches.append((channel, channel_indices[offset : offset + batch_size]))
        return batches

    def _has_config(self, context: Any, name: str) -> bool:
        if hasattr(context, "has_explicit_config"):
            try:
                return context.has_explicit_config(self, name)
            except Exception:
                pass
        config = getattr(context, "config", {})
        provides = self.provides
        if provides in config and isinstance(config[provides], dict):
            if name in config[provides]:
                return True
        if f"{provides}.{name}" in config:
            return True
        return name in config

    def _get_fs_from_adapter(self, daq_adapter: Optional[str], default_value: float) -> float:
        if not daq_adapter:
            return default_value
        try:
            from waveform_analysis.utils.formats import get_adapter
        except Exception:
            return default_value
        try:
            adapter = get_adapter(daq_adapter)
        except ValueError:
            return default_value
        sampling_rate_hz = adapter.sampling_rate_hz
        if not sampling_rate_hz:
            return default_value
        return float(sampling_rate_hz) / 1e9
