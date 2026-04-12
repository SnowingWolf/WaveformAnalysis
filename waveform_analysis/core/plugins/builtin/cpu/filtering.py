"""
CPU Filtering Plugin - 使用 scipy 进行波形滤波

**加速器**: CPU (scipy)
**功能**: 波形滤波（Butterworth 带通滤波、Savitzky-Golay 滤波）

本模块提供共享的滤波执行层，同时服务：
- `filtered_waveforms`：结构化数组输出，`wave` 字段为 float32
- `wave_pool_filtered`：records-backed float32 波形池
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import numpy as np
from scipy.signal import butter, savgol_filter, sosfiltfilt

from waveform_analysis.core.hardware.channel import (
    group_indices_by_hardware_channel,
    resolve_effective_channel_config,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import ST_WAVEFORM_DTYPE

logger = logging.getLogger(__name__)
BatchSelector = slice | np.ndarray
FILTER_ENGINE_VERSION = "3.0.0"
FILTER_OPTION_NAMES = (
    "filter_type",
    "lowcut",
    "highcut",
    "fs",
    "filter_order",
    "sg_window_size",
    "sg_poly_order",
)


def get_filter_base_values(context: Any, plugin: Plugin) -> dict[str, Any]:
    """Return plugin-level filter config before channel overrides are applied."""
    return {name: context.get_config(plugin, name) for name in FILTER_OPTION_NAMES}


def resolve_filter_config(
    context: Any,
    plugin: Plugin,
    *,
    run_id: str | None = None,
    board: int | None = None,
    channel: int | None = None,
    base_values: Mapping[str, Any] | None = None,
    channel_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve and validate shared filter configuration for waveform filters."""
    resolved_values = dict(base_values or get_filter_base_values(context, plugin))
    if channel_config is None and "channel_config" in getattr(plugin, "options", {}):
        candidate = context.get_config(plugin, "channel_config")
        if isinstance(candidate, Mapping):
            channel_config = candidate

    if run_id is not None and board is not None and channel is not None:
        rule = resolve_effective_channel_config(
            context=context,
            plugin=plugin,
            run_id=run_id,
            board=board,
            channel=channel,
            base_values=resolved_values,
            channel_config=channel_config,
        )
        resolved_values = dict(rule.values)

    filter_type = str(resolved_values["filter_type"])
    if filter_type not in ("BW", "SG"):
        raise ValueError(f"不支持的滤波器类型: {filter_type}. 请使用 'BW' 或 'SG'.")

    bw_sos: np.ndarray | None = None
    sg_window_size: int | None = None
    sg_poly_order: int | None = None

    if filter_type == "BW":
        lowcut = float(resolved_values["lowcut"])
        highcut = float(resolved_values["highcut"])
        fs = float(resolved_values["fs"])
        order = int(resolved_values["filter_order"])

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

        bw_sos = butter(order, [lowcut, highcut], btype="band", output="sos", fs=fs)
        logger.debug(
            "设计 Butterworth 带通滤波器: order=%s lowcut=%s highcut=%s fs=%s",
            order,
            lowcut,
            highcut,
            fs,
        )
    else:
        sg_window_size = int(resolved_values["sg_window_size"])
        sg_poly_order = int(resolved_values["sg_poly_order"])

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

    return {
        "filter_type": filter_type,
        "bw_sos": bw_sos,
        "sg_window_size": sg_window_size,
        "sg_poly_order": sg_poly_order,
    }


def create_filtered_waveform_dtype(source_dtype: np.dtype) -> np.dtype:
    """Return a dtype compatible with source_dtype but with float32 wave samples."""
    names = source_dtype.names or ()
    if "wave" not in names:
        raise ValueError("source dtype missing required 'wave' field")

    fields: list[tuple[Any, ...]] = []
    for name in names:
        field_dtype = source_dtype.fields[name][0]
        if name == "wave":
            subdtype = field_dtype.subdtype
            if subdtype is None:
                fields.append((name, np.float32))
            else:
                _base_dtype, shape = subdtype
                fields.append((name, np.float32, shape))
            continue

        subdtype = field_dtype.subdtype
        if subdtype is None:
            fields.append((name, field_dtype))
            continue
        base_dtype, shape = subdtype
        fields.append((name, base_dtype, shape))

    return np.dtype(fields)


def apply_filter_to_record_wave(
    wave: np.ndarray,
    filter_type: str,
    bw_sos: np.ndarray | None = None,
    sg_window_size: int | None = None,
    sg_poly_order: int | None = None,
) -> np.ndarray:
    """Apply the configured filter to a single record waveform."""
    wave_f32 = np.asarray(wave, dtype=np.float32)
    if wave_f32.ndim != 1:
        raise ValueError("record waveform must be 1D")
    return _apply_filter_core(
        wave_f32,
        filter_type,
        bw_sos=bw_sos,
        sg_window_size=sg_window_size,
        sg_poly_order=sg_poly_order,
    )


def _resolve_sg_window_length(
    n_samples: int,
    sg_window_size: int | None,
    sg_poly_order: int | None,
) -> int | None:
    """Return the effective SG window length, or None when filtering should no-op."""
    if sg_window_size is None or sg_poly_order is None:
        raise ValueError("SG filter requires sg_window_size and sg_poly_order")

    window = min(int(sg_window_size), int(n_samples))
    if window % 2 == 0:
        window -= 1
    if window <= int(sg_poly_order):
        return None
    return window


def _estimate_sosfiltfilt_padlen(bw_sos: np.ndarray) -> int:
    """Match scipy's default sosfiltfilt pad-length heuristic."""
    n_sections = int(bw_sos.shape[0])
    zeros_at_origin = int((bw_sos[:, 2] == 0).sum())
    poles_at_origin = int((bw_sos[:, 5] == 0).sum())
    return 3 * (2 * n_sections + 1 - min(zeros_at_origin, poles_at_origin))


def _apply_filter_core(
    waves_f32: np.ndarray,
    filter_type: str,
    bw_sos: np.ndarray | None = None,
    sg_window_size: int | None = None,
    sg_poly_order: int | None = None,
) -> np.ndarray:
    """Apply the configured filter to float32 waveform batches."""
    waves_f32 = np.asarray(waves_f32, dtype=np.float32)
    if waves_f32.ndim not in (1, 2):
        raise ValueError("waveforms must be 1D or 2D")

    if filter_type == "BW":
        if bw_sos is None:
            raise ValueError("BW filter requires precomputed SOS coefficients")
        if waves_f32.shape[-1] <= _estimate_sosfiltfilt_padlen(bw_sos):
            return np.array(waves_f32, copy=True)
        filtered = sosfiltfilt(bw_sos, waves_f32, axis=-1)
        return np.asarray(filtered, dtype=np.float32)

    window = _resolve_sg_window_length(
        waves_f32.shape[-1],
        sg_window_size,
        sg_poly_order,
    )
    if window is None:
        return np.array(waves_f32, copy=True)

    filtered = savgol_filter(
        waves_f32,
        window_length=window,
        polyorder=int(sg_poly_order),
        axis=-1,
        mode="interp",
    )
    return np.asarray(filtered, dtype=np.float32)


def _filter_channel(args) -> np.ndarray:
    """Apply a single channel-scoped filter config to a waveform batch."""
    waveforms, selector, filter_type, bw_sos, sg_window_size, sg_poly_order = args
    waveforms_f32 = np.asarray(waveforms[selector], dtype=np.float32)
    return _apply_filter_core(
        waveforms_f32,
        filter_type,
        bw_sos=bw_sos,
        sg_window_size=sg_window_size,
        sg_poly_order=sg_poly_order,
    )


def _copy_non_wave_fields(source: np.ndarray, target: np.ndarray) -> None:
    names = source.dtype.names or ()
    for name in names:
        if name == "wave":
            continue
        target[name] = source[name]


def _make_selector(indices: np.ndarray) -> BatchSelector:
    if indices.size == 0:
        raise ValueError("indices must not be empty")
    if indices.size == 1:
        start = int(indices[0])
        return slice(start, start + 1)
    if np.all(np.diff(indices) == 1):
        return slice(int(indices[0]), int(indices[-1]) + 1)
    return np.array(indices, copy=True)


def _split_contiguous_runs(indices: np.ndarray) -> list[np.ndarray]:
    if indices.size == 0:
        return []
    if indices.size == 1:
        return [indices]
    breaks = np.flatnonzero(np.diff(indices) != 1) + 1
    starts = np.r_[0, breaks]
    stops = np.r_[breaks, indices.size]
    return [indices[start:stop] for start, stop in zip(starts, stops, strict=False)]


def _selector_to_indices(selector: BatchSelector) -> np.ndarray:
    if isinstance(selector, slice):
        return np.arange(int(selector.start), int(selector.stop), dtype=np.int64)
    return np.asarray(selector, dtype=np.int64)


def build_channel_selectors(
    channel_indices: np.ndarray,
    batch_size: int,
) -> list[BatchSelector]:
    if channel_indices.size == 0:
        return []
    if batch_size <= 0:
        return [_make_selector(channel_indices)]

    selectors: list[BatchSelector] = []
    for run_indices in _split_contiguous_runs(channel_indices):
        if run_indices.size <= batch_size:
            selectors.append(_make_selector(run_indices))
            continue
        for offset in range(0, run_indices.size, batch_size):
            selectors.append(_make_selector(run_indices[offset : offset + batch_size]))
    return selectors


def build_channel_batches(
    boards: np.ndarray,
    channels: np.ndarray,
    batch_size: int,
) -> list[tuple[tuple[int, int], BatchSelector]]:
    """Group event indices by hardware channel and split them into selectors."""
    if channels.size == 0:
        return []
    groups = group_indices_by_hardware_channel(boards, channels)
    batches: list[tuple[tuple[int, int], BatchSelector]] = []
    for hw_channel, channel_indices in groups.items():
        if channel_indices.size == 0:
            continue
        channel_key = (int(hw_channel.board), int(hw_channel.channel))
        batches.extend(
            (channel_key, selector)
            for selector in build_channel_selectors(channel_indices, batch_size)
        )
    return batches


def selector_length(selector: BatchSelector) -> int:
    if isinstance(selector, slice):
        return int(selector.stop - selector.start)
    return int(selector.size)


def build_filter_batches(
    context: Any,
    plugin: Plugin,
    run_id: str,
    boards: np.ndarray,
    channels: np.ndarray,
    batch_size: int,
) -> list[tuple[tuple[int, int], BatchSelector, dict[str, Any]]]:
    """Return channel-aware filter tasks with resolved per-channel configs."""
    channel_batches = build_channel_batches(boards, channels, batch_size)
    if not channel_batches:
        return []

    base_values = get_filter_base_values(context, plugin)
    channel_config = (
        context.get_config(plugin, "channel_config")
        if "channel_config" in getattr(plugin, "options", {})
        else None
    )
    resolved_by_channel: dict[tuple[int, int], dict[str, Any]] = {}
    planned: list[tuple[tuple[int, int], BatchSelector, dict[str, Any]]] = []
    for channel_key, selector in channel_batches:
        filter_config = resolved_by_channel.get(channel_key)
        if filter_config is None:
            filter_config = resolve_filter_config(
                context,
                plugin,
                run_id=run_id,
                board=channel_key[0],
                channel=channel_key[1],
                base_values=base_values,
                channel_config=channel_config,
            )
            resolved_by_channel[channel_key] = filter_config
        planned.append((channel_key, selector, filter_config))
    return planned


def filter_wave_pool_batch(args) -> list[tuple[int, np.ndarray]]:
    """Apply one channel-scoped filter config to a batch of records-backed waves."""
    records, wave_pool, selector, filter_type, bw_sos, sg_window_size, sg_poly_order = args
    filtered_segments: list[tuple[int, np.ndarray]] = []
    for idx in _selector_to_indices(selector):
        rec = records[int(idx)]
        length = int(rec["event_length"])
        if length <= 0:
            continue
        offset = int(rec["wave_offset"])
        end = offset + length
        if offset < 0 or end > len(wave_pool):
            raise ValueError(
                "wave_pool_filtered found out-of-bounds wave slice "
                f"(offset={offset}, length={length}, wave_pool_size={len(wave_pool)})"
            )
        raw_wave = wave_pool[offset:end]
        filtered_wave = apply_filter_to_record_wave(
            raw_wave,
            filter_type,
            bw_sos=bw_sos,
            sg_window_size=sg_window_size,
            sg_poly_order=sg_poly_order,
        )
        if filtered_wave.shape[0] != length:
            raise ValueError(
                "wave_pool_filtered produced mismatched waveform length "
                f"for offset={offset}: expected {length}, got {filtered_wave.shape[0]}"
            )
        filtered_segments.append((offset, filtered_wave.astype(np.float32, copy=False)))
    return filtered_segments


class FilteredWaveformsPlugin(Plugin):
    provides = "filtered_waveforms"
    depends_on = ["st_waveforms"]
    description = "Apply filtering to waveforms using Butterworth or Savitzky-Golay filters."
    version = FILTER_ENGINE_VERSION
    save_when = "target"

    output_dtype = create_filtered_waveform_dtype(np.dtype(ST_WAVEFORM_DTYPE))

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
            help="每批次事件数（0 表示不分批，整个通道一次处理）",
        ),
        "channel_config": Option(
            default=None,
            type=dict,
            help="按 (board, channel) 的插件通道覆盖配置，可覆盖滤波参数。",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        st_waveforms = context.get_data(run_id, "st_waveforms")
        if not isinstance(st_waveforms, np.ndarray):
            raise ValueError("filtered_waveforms expects st_waveforms as a single structured array")

        resolved_output_dtype = create_filtered_waveform_dtype(st_waveforms.dtype)
        if resolved_output_dtype != self.output_dtype:
            self.output_dtype = resolved_output_dtype

        if len(st_waveforms) == 0:
            return np.zeros(0, dtype=self.output_dtype)

        if "channel" not in st_waveforms.dtype.names:
            raise ValueError("st_waveforms missing required 'channel' field for filtering")
        if "wave" not in st_waveforms.dtype.names:
            raise ValueError("st_waveforms missing required 'wave' field for filtering")

        output = np.empty(len(st_waveforms), dtype=self.output_dtype)
        _copy_non_wave_fields(st_waveforms, output)

        channels = st_waveforms["channel"]
        boards = (
            st_waveforms["board"]
            if "board" in st_waveforms.dtype.names
            else np.zeros(len(st_waveforms), dtype=np.int16)
        )
        waves = st_waveforms["wave"]
        if waves.ndim != 2:
            raise ValueError("st_waveforms['wave'] must be 2D (n_events, n_samples)")

        batch_size = int(context.get_config(self, "batch_size"))
        if batch_size < 0:
            raise ValueError(f"batch_size ({batch_size}) 必须大于等于 0")

        filter_batches = build_filter_batches(context, self, run_id, boards, channels, batch_size)
        if not filter_batches:
            return output

        max_workers = context.get_config(self, "max_workers")
        allow_parallel = max_workers is None or (isinstance(max_workers, int) and max_workers > 1)
        use_parallel = allow_parallel and len(filter_batches) > 1

        if use_parallel:
            from waveform_analysis.core.execution.manager import parallel_map

            tasks = [
                (
                    waves,
                    batch_selector,
                    filter_config["filter_type"],
                    filter_config["bw_sos"],
                    filter_config["sg_window_size"],
                    filter_config["sg_poly_order"],
                )
                for _channel, batch_selector, filter_config in filter_batches
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
            for (_channel, batch_selector, _filter_config), filtered_f32 in zip(
                filter_batches, results, strict=False
            ):
                output["wave"][batch_selector] = filtered_f32
        else:
            for channel_key, batch_selector, filter_config in filter_batches:
                logger.debug(
                    "处理通道批次: channel=%s n_events=%s n_samples=%s",
                    channel_key,
                    selector_length(batch_selector),
                    waves.shape[1],
                )
                output["wave"][batch_selector] = _filter_channel(
                    (
                        waves,
                        batch_selector,
                        filter_config["filter_type"],
                        filter_config["bw_sos"],
                        filter_config["sg_window_size"],
                        filter_config["sg_poly_order"],
                    )
                )

        return output

    def _build_channel_batches(
        self,
        boards: np.ndarray,
        channels: np.ndarray,
        batch_size: int,
    ) -> list[tuple[tuple[int, int], BatchSelector]]:
        return build_channel_batches(boards, channels, batch_size)

    def _build_channel_selectors(
        self,
        channel_indices: np.ndarray,
        batch_size: int,
    ) -> list[BatchSelector]:
        return build_channel_selectors(channel_indices, batch_size)

    @staticmethod
    def _selector_length(selector: BatchSelector) -> int:
        return selector_length(selector)
