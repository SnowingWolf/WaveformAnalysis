"""peaklet_waveforms bundle - provides 'peaklet_waveforms'。"""

from multiprocessing import Pool, cpu_count
import time
from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._record_utils import RecordLookup
from waveform_analysis.core.plugins.builtin.shared.waveform_merge import (
    WaveformOverlapConflictError,
    merge_waveform_segments,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin

try:
    from numba import njit

    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

    def njit(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return lambda f: f


import logging

logger = logging.getLogger(__name__)
HAS_MULTIPROCESSING = True
from waveform_analysis.core.plugins.builtin.peaklets._compute import (
    PEAKLET_WAVEFORMS_DTYPE,
    _build_hit_merged_components_index,
    _build_hmc_csr,
    _build_peaklet_component_csr,
    _build_waveforms_numba,
    _components_by_peaklet,
    _empty_waveform_pool,
    _empty_waveforms,
    _extract_polarity_signs,
    _fill_cross_record_pool_numba,
    _first_pass_cross_record_numba,
    _get_context_memory,
    _merged_wave_piece,
    _merged_wave_pieces_multirecord,
    _record_array,
    _store_context_memory,
    _validate_peaklet_components,
    _wave_pool_array,
)

_ROUTE_EMPTY = np.int8(0)
_ROUTE_FAST = np.int8(1)
_ROUTE_CANONICAL = np.int8(2)

_STATUS_OK = 0
_STATUS_MIXED_DT = 1
_STATUS_OFF_GRID = 2
_STATUS_NONFINITE = 3
_STATUS_INVALID_RECORD = 4
_STATUS_INVALID_POOL = 5
_STATUS_INVALID_DT = 6


@njit(cache=True, nogil=True)
def _classify_and_size_peaklets_numba(
    piece_starts,
    piece_ends,
    piece_record_indices,
    piece_is_cross,
    piece_boards,
    piece_channels,
    peaklet_piece_starts,
    peaklet_piece_ends,
    record_dt,
    record_event_length,
    record_timestamp,
    record_wave_offset,
    record_baseline,
    wave_pool,
):
    """Classify peaklets and build their public index rows in one pass."""
    n_peaklets = len(peaklet_piece_starts)
    rows = np.zeros((n_peaklets, 6), dtype=np.int64)
    routes = np.zeros(n_peaklets, dtype=np.int8)
    total_wave_length = 0
    input_samples = 0
    max_wave_length = 0

    for peaklet_id in range(n_peaklets):
        rows[peaklet_id, 0] = peaklet_id
        rows[peaklet_id, 4] = total_wave_length
        piece_begin = peaklet_piece_starts[peaklet_id]
        piece_end = peaklet_piece_ends[peaklet_id]
        if piece_begin < 0 or piece_end <= piece_begin:
            continue

        dt_ns = -1
        grid_origin = 0
        time_start = 0
        time_end = 0
        has_piece = False
        route = _ROUTE_FAST
        previous_board = -32769
        previous_channel = -32769
        previous_end = 0

        for piece_i in range(piece_begin, piece_end):
            rec_idx = piece_record_indices[piece_i]
            if rec_idx < 0 or rec_idx >= len(record_dt):
                return (
                    rows,
                    routes,
                    total_wave_length,
                    max_wave_length,
                    input_samples,
                    _STATUS_INVALID_RECORD,
                    peaklet_id,
                )
            piece_dt = record_dt[rec_idx]
            if piece_dt <= 0:
                return (
                    rows,
                    routes,
                    total_wave_length,
                    max_wave_length,
                    input_samples,
                    _STATUS_INVALID_DT,
                    peaklet_id,
                )

            start = piece_starts[piece_i]
            end = piece_ends[piece_i]
            if start < 0:
                start = 0
            rec_length = record_event_length[rec_idx]
            if end > rec_length:
                end = rec_length
            if end <= start:
                continue

            pool_start = record_wave_offset[rec_idx] + start
            pool_end = record_wave_offset[rec_idx] + end
            if pool_start < 0 or pool_end > len(wave_pool):
                return (
                    rows,
                    routes,
                    total_wave_length,
                    max_wave_length,
                    input_samples,
                    _STATUS_INVALID_POOL,
                    peaklet_id,
                )
            if not np.isfinite(record_baseline[rec_idx]):
                return (
                    rows,
                    routes,
                    total_wave_length,
                    max_wave_length,
                    input_samples,
                    _STATUS_NONFINITE,
                    peaklet_id,
                )
            for pool_i in range(pool_start, pool_end):
                if not np.isfinite(wave_pool[pool_i]):
                    return (
                        rows,
                        routes,
                        total_wave_length,
                        max_wave_length,
                        input_samples,
                        _STATUS_NONFINITE,
                        peaklet_id,
                    )

            dt_ps = piece_dt * 1000
            abs_start = record_timestamp[rec_idx] + start * dt_ps
            abs_end = record_timestamp[rec_idx] + end * dt_ps
            if not has_piece:
                dt_ns = piece_dt
                grid_origin = abs_start
                time_start = abs_start
                time_end = abs_end
                has_piece = True
            else:
                if piece_dt != dt_ns:
                    return (
                        rows,
                        routes,
                        total_wave_length,
                        max_wave_length,
                        input_samples,
                        _STATUS_MIXED_DT,
                        peaklet_id,
                    )
                if (abs_start - grid_origin) % dt_ps != 0:
                    return (
                        rows,
                        routes,
                        total_wave_length,
                        max_wave_length,
                        input_samples,
                        _STATUS_OFF_GRID,
                        peaklet_id,
                    )
                if abs_start < time_start:
                    time_start = abs_start
                if abs_end > time_end:
                    time_end = abs_end

            board = piece_boards[piece_i]
            channel = piece_channels[piece_i]
            if piece_is_cross[piece_i]:
                route = _ROUTE_CANONICAL
            if board == previous_board and channel == previous_channel and abs_start < previous_end:
                route = _ROUTE_CANONICAL
                if abs_end > previous_end:
                    previous_end = abs_end
            else:
                previous_board = board
                previous_channel = channel
                previous_end = abs_end
            input_samples += end - start

        if not has_piece:
            continue
        dt_ps = dt_ns * 1000
        wave_length = (time_end - time_start) // dt_ps
        rows[peaklet_id, 1] = time_start
        rows[peaklet_id, 2] = time_start + wave_length * dt_ps
        rows[peaklet_id, 3] = dt_ns
        rows[peaklet_id, 5] = wave_length
        routes[peaklet_id] = route
        total_wave_length += wave_length
        if wave_length > max_wave_length:
            max_wave_length = wave_length

    return (
        rows,
        routes,
        total_wave_length,
        max_wave_length,
        input_samples,
        _STATUS_OK,
        -1,
    )


@njit(cache=True, nogil=True)
def _fill_routed_peaklet_pool_numba(
    pool64,
    rows,
    routes,
    piece_starts,
    piece_ends,
    piece_record_indices,
    piece_boards,
    piece_channels,
    piece_record_ids,
    piece_merged_indices,
    peaklet_piece_starts,
    peaklet_piece_ends,
    record_dt,
    record_event_length,
    record_timestamp,
    record_wave_offset,
    record_baseline,
    record_sign,
    wave_pool,
    clip_negative_signal,
    max_wave_length,
):
    """Fill fast and canonical peaklets while preserving deterministic sums."""
    occupancy_values = np.empty(max_wave_length, dtype=np.float32)
    occupancy_bits = np.empty(max_wave_length, dtype=np.uint32)
    occupancy_source = np.empty(max_wave_length, dtype=np.int64)
    occupancy_stamp = np.zeros(max_wave_length, dtype=np.int64)
    bit_value = np.empty(1, dtype=np.float32)
    bit_view = bit_value.view(np.uint32)
    stamp = 0
    unique_samples = 0

    for peaklet_id in range(len(rows)):
        wave_length = rows[peaklet_id, 5]
        if wave_length <= 0:
            continue
        piece_begin = peaklet_piece_starts[peaklet_id]
        piece_end = peaklet_piece_ends[peaklet_id]
        peaklet_time_start = rows[peaklet_id, 1]
        dt_ps = rows[peaklet_id, 3] * 1000
        pool_offset = rows[peaklet_id, 4]

        if routes[peaklet_id] == _ROUTE_FAST:
            for piece_i in range(piece_begin, piece_end):
                rec_idx = piece_record_indices[piece_i]
                start = piece_starts[piece_i]
                end = piece_ends[piece_i]
                if start < 0:
                    start = 0
                if end > record_event_length[rec_idx]:
                    end = record_event_length[rec_idx]
                if end <= start:
                    continue
                abs_start = record_timestamp[rec_idx] + start * dt_ps
                dst = pool_offset + (abs_start - peaklet_time_start) // dt_ps
                src = record_wave_offset[rec_idx] + start
                baseline = record_baseline[rec_idx]
                sign = record_sign[rec_idx]
                for sample_i in range(end - start):
                    signal = sign * (np.float32(wave_pool[src + sample_i]) - baseline)
                    if clip_negative_signal and signal < 0.0:
                        signal = np.float32(0.0)
                    pool64[dst + sample_i] += np.float64(signal)
                    unique_samples += 1
            continue

        piece_i = piece_begin
        while piece_i < piece_end:
            board = piece_boards[piece_i]
            channel = piece_channels[piece_i]
            channel_end = piece_i + 1
            while (
                channel_end < piece_end
                and piece_boards[channel_end] == board
                and piece_channels[channel_end] == channel
            ):
                channel_end += 1

            stamp += 1
            for channel_piece_i in range(piece_i, channel_end):
                rec_idx = piece_record_indices[channel_piece_i]
                start = piece_starts[channel_piece_i]
                end = piece_ends[channel_piece_i]
                if start < 0:
                    start = 0
                if end > record_event_length[rec_idx]:
                    end = record_event_length[rec_idx]
                if end <= start:
                    continue
                abs_start = record_timestamp[rec_idx] + start * dt_ps
                local_start = (abs_start - peaklet_time_start) // dt_ps
                src = record_wave_offset[rec_idx] + start
                baseline = record_baseline[rec_idx]
                sign = record_sign[rec_idx]
                for sample_i in range(end - start):
                    local_i = local_start + sample_i
                    signal = sign * (np.float32(wave_pool[src + sample_i]) - baseline)
                    if clip_negative_signal and signal < 0.0:
                        signal = np.float32(0.0)
                    bit_value[0] = signal
                    signal_bits = bit_view[0]
                    if occupancy_stamp[local_i] != stamp:
                        occupancy_stamp[local_i] = stamp
                        occupancy_values[local_i] = signal
                        occupancy_bits[local_i] = signal_bits
                        occupancy_source[local_i] = channel_piece_i
                        unique_samples += 1
                    elif occupancy_bits[local_i] != signal_bits:
                        return (
                            peaklet_id,
                            local_i,
                            occupancy_source[local_i],
                            channel_piece_i,
                            occupancy_values[local_i],
                            signal,
                            unique_samples,
                        )

            for local_i in range(wave_length):
                if occupancy_stamp[local_i] == stamp:
                    pool64[pool_offset + local_i] += np.float64(occupancy_values[local_i])
            piece_i = channel_end

    return -1, -1, -1, -1, np.float32(0.0), np.float32(0.0), unique_samples


def _process_peaklet_batch(batch_data: dict) -> tuple[np.ndarray, np.ndarray]:
    """
    Process a batch of peaklets in a separate process.

    This function is called by multiprocessing Pool.map() and must be
    at module level (not a method).

    Parameters
    ----------
    batch_data : dict
        Contains: peaklets, components, merged, records, wave_pool,
                  hit_merged_components, hit_threshold

    Returns
    -------
    waveforms : np.ndarray
        Waveform index rows for this batch
    pool : np.ndarray
        Concatenated waveform pool for this batch
    """
    peaklets = batch_data["peaklets"]
    components = batch_data["components"]
    merged = batch_data["merged"]
    records = batch_data["records"]
    wave_pool = batch_data["wave_pool"]
    hit_merged_components = batch_data["hit_merged_components"]
    hit_threshold = batch_data["hit_threshold"]
    clip_negative_signal = bool(batch_data.get("clip_negative_signal", False))

    # Build hit_merged_components index if available
    if hit_merged_components is not None and len(hit_merged_components) > 0:
        hit_merged_components_index = _build_hit_merged_components_index(hit_merged_components)
    else:
        hit_merged_components_index = {}

    # Store in batch_data for access in nested function
    batch_data["hit_merged_components_index"] = hit_merged_components_index

    # Process using the same logic as _build_python
    record_lookup = RecordLookup(records)
    component_groups = _components_by_peaklet(components, len(peaklets))
    rows: list[tuple[int, int, int, int, int, int]] = []
    pools: list[np.ndarray] = []
    wave_offset = 0

    for peaklet_id, merged_indices in enumerate(component_groups):
        if len(merged_indices) == 0:
            rows.append((peaklet_id, 0, 0, 0, wave_offset, 0))
            continue

        segments: list[dict[str, Any]] = []

        for merged_index in merged_indices:
            hit = merged[int(merged_index)]

            # Detect cross-record hit
            is_single_record = (
                bool(hit["is_single_record"])
                if "is_single_record" in hit.dtype.names
                else (int(hit["sample_start"]) >= 0 and int(hit["sample_end"]) >= 0)
            )

            if (
                not is_single_record
                and hit_merged_components is not None
                and hit_threshold is not None
            ):
                # Cross-record path
                multi_pieces = _merged_wave_pieces_multirecord(
                    hit=hit,
                    hit_merged_components_index=batch_data["hit_merged_components_index"],
                    hit_threshold=hit_threshold,
                    records=records,
                    record_lookup=record_lookup,
                    wave_pool=wave_pool,
                    merged_index=int(merged_index),
                    clip_negative_signal=clip_negative_signal,
                )

                for start_ps, _end_ps, piece_dt_ns, signal, record_id in multi_pieces:
                    if len(signal) == 0:
                        continue
                    segments.append(
                        {
                            "waveform": signal,
                            "abs_time_ps": start_ps
                            + np.arange(len(signal), dtype=np.int64) * piece_dt_ns * 1000,
                            "dt": piece_dt_ns,
                            "board": int(hit["board"]),
                            "channel": int(hit["channel"]),
                            "record_id": record_id,
                            "merged_index": int(merged_index),
                        }
                    )
            else:
                # Single-record path
                start_ps, _end_ps, piece_dt_ns, signal, record_id = _merged_wave_piece(
                    hit=hit,
                    records=records,
                    record_lookup=record_lookup,
                    wave_pool=wave_pool,
                    clip_negative_signal=clip_negative_signal,
                )
                if len(signal) == 0:
                    continue
                segments.append(
                    {
                        "waveform": signal,
                        "abs_time_ps": start_ps
                        + np.arange(len(signal), dtype=np.int64) * piece_dt_ns * 1000,
                        "dt": piece_dt_ns,
                        "board": int(hit["board"]),
                        "channel": int(hit["channel"]),
                        "record_id": record_id,
                        "merged_index": int(merged_index),
                    }
                )

        if not segments:
            rows.append((peaklet_id, 0, 0, 0, wave_offset, 0))
            continue

        merged_waveform = merge_waveform_segments(
            segments,
            sum_channels=True,
            dense=True,
            context=f"peaklet_id={peaklet_id}",
        )
        summed = merged_waveform["waveform"]
        dt_ns = int(merged_waveform["dt"])
        time_start = int(merged_waveform["abs_time_ps"][0])
        wave_length = len(summed)
        time_end = time_start + wave_length * dt_ns * 1000

        rows.append((peaklet_id, time_start, time_end, dt_ns, wave_offset, wave_length))
        pools.append(summed)
        wave_offset += wave_length

    pool = np.concatenate(pools).astype(np.float32, copy=False) if pools else _empty_waveform_pool()
    waveforms = np.array(rows, dtype=PEAKLET_WAVEFORMS_DTYPE) if rows else _empty_waveforms()

    return waveforms, pool


class PeakletWaveformPlugin(Plugin):
    """Build ragged waveform index rows for peaklets and cache the signal pool."""

    provides = "peaklet_waveforms"
    depends_on = []  # 使用 resolve_depends_on() 动态解析
    description = "Build peaklet waveform index rows from records-backed hit_merged samples. Supports cross-record hits via component expansion."
    version = "2.1.0"
    output_dtype = PEAKLET_WAVEFORMS_DTYPE
    save_when = "always"

    options = {
        "use_filtered": Option(
            default=False, type=bool, help="是否使用 wave_pool_filtered 构建 peaklet 波形"
        ),
        "clip_negative_signal": Option(
            default=False,
            type=bool,
            help="是否将 baseline/polarity 转换后的负信号裁剪为 0。默认保留负值。",
        ),
        "debug_numba": Option(
            default=False,
            type=bool,
            help="调试 peaklet waveform Numba 路径；启用后 Numba 异常直接抛出。",
        ),
        "log_waveform_diagnostics": Option(
            default=False,
            type=bool,
            help="记录 peaklet waveform 构建统计和耗时诊断信息。",
        ),
        "n_workers": Option(
            default=1,
            type=int,
            help="并行处理的进程数。1=单进程，0=自动（使用 CPU 核心数-1），>1=指定进程数",
        ),
        "parallel_threshold": Option(
            default=5000,
            type=int,
            help="启用并行化的最小 peaklet 数量。少于此数量时使用单进程",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        deps = [
            "peaklets",
            "peaklet_components",
            "hit_merged",
            "hit_merged_components",
            "hit_threshold",
            "records",
        ]
        deps.append(
            "wave_pool_filtered" if bool(context.get_config(self, "use_filtered")) else "wave_pool"
        )
        return deps

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        cached_waveforms = _get_context_memory(context, run_id, "peaklet_waveforms")
        if isinstance(cached_waveforms, np.ndarray):
            return cached_waveforms

        waveforms, pool = self.build_pair(context, run_id)
        self._store_waveform_pair(context, run_id, waveforms, pool)
        return waveforms

    def _configure_build(self, context: Any) -> None:
        """Resolve the canonical configuration used by both waveform outputs."""
        n_workers = int(context.get_config(self, "n_workers"))
        if n_workers == 0 and HAS_MULTIPROCESSING:
            n_workers = max(1, cpu_count() - 1)

        self._n_workers = n_workers
        self._parallel_threshold = int(context.get_config(self, "parallel_threshold"))
        self._debug_numba = bool(context.get_config(self, "debug_numba"))
        self._log_waveform_diagnostics = bool(context.get_config(self, "log_waveform_diagnostics"))
        self._clip_negative_signal = bool(context.get_config(self, "clip_negative_signal"))

    def build_pair(self, context: Any, run_id: str) -> tuple[np.ndarray, np.ndarray]:
        """Build index rows and the flattened pool from one canonical configuration."""
        self._configure_build(context)
        return self._compute_waveforms_and_pool(context, run_id)

    def _store_waveform_pair(
        self, context: Any, run_id: str, waveforms: np.ndarray, pool: np.ndarray
    ) -> None:
        _store_context_memory(context, run_id, "peaklet_waveforms", waveforms)
        _store_context_memory(context, run_id, "peaklet_waveform_pool", pool)

    def _compute_waveforms_and_pool(
        self, context: Any, run_id: str
    ) -> tuple[np.ndarray, np.ndarray]:
        peaklets = context.get_data(run_id, "peaklets")
        if not isinstance(peaklets, np.ndarray):
            raise ValueError("peaklet_waveforms expects peaklets as a structured array")
        if len(peaklets) == 0:
            return _empty_waveforms(), _empty_waveform_pool()

        components = context.get_data(run_id, "peaklet_components")
        if not isinstance(components, np.ndarray):
            raise ValueError("peaklet_waveforms expects peaklet_components as a structured array")
        _validate_peaklet_components(
            peaklets=peaklets,
            components=components,
            consumer="peaklet_waveforms",
        )
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("peaklet_waveforms expects hit_merged as a structured array")

        # Get cross-record dependencies
        hit_merged_components = context.get_data(run_id, "hit_merged_components")
        hit_threshold = context.get_data(run_id, "hit_threshold")

        records = _record_array(context.get_data(run_id, "records"))
        if "dt" not in (records.dtype.names or ()):
            raise KeyError("records dt field is required")
        wave_pool_name = (
            "wave_pool_filtered" if bool(context.get_config(self, "use_filtered")) else "wave_pool"
        )
        wave_pool = _wave_pool_array(context.get_data(run_id, wave_pool_name))

        # Store context and run_id for Python fallback path
        self._context = context
        self._run_id = run_id
        self._hit_merged_components = hit_merged_components
        self._hit_threshold = hit_threshold
        self._hit_merged_components_index = None

        return self._build(
            peaklets=peaklets,
            components=components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )

    def _build(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        if len(peaklets) == 0:
            return _empty_waveforms(), _empty_waveform_pool()

        if HAS_NUMBA:
            try:
                return self._build_routed_numba(
                    peaklets=peaklets,
                    components=components,
                    merged=merged,
                    records=records,
                    wave_pool=wave_pool,
                )
            except (WaveformOverlapConflictError, ValueError, KeyError, IndexError):
                raise
            except Exception as e:
                if getattr(self, "_debug_numba", False):
                    raise
                logger.warning(
                    "Numba routed path failed for peaklet_waveforms; " "falling back to Python: %s",
                    e,
                )
                self._log_route_diagnostics(
                    n_peaklets=len(peaklets),
                    n_fast=0,
                    n_canonical=0,
                    n_fallback=len(peaklets),
                    input_samples=0,
                    unique_samples=0,
                    classify_sec=0.0,
                    kernel_sec=0.0,
                    jit_before=False,
                    jit_after=False,
                )

        return self._build_canonical(
            peaklets=peaklets,
            components=components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )

    def _prepare_numba_pieces(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
    ) -> tuple[np.ndarray, ...]:
        """Flatten component provenance and sort it into peak/channel CSR order."""
        merged_names = merged.dtype.names or ()
        if {"sample_start", "sample_end"}.issubset(merged_names):
            merged_starts = merged["sample_start"]
            merged_ends = merged["sample_end"]
        elif {"edge_start", "edge_end"}.issubset(merged_names):
            merged_starts = merged["edge_start"]
            merged_ends = merged["edge_end"]
        else:
            raise KeyError(
                "peaklet_waveforms requires hit_merged sample_start/sample_end "
                "or edge_start/edge_end"
            )
        if "record_id" not in merged_names:
            raise KeyError("peaklet_waveforms requires hit_merged record_id")

        hit_threshold = getattr(self, "_hit_threshold", None)
        hit_merged_components = getattr(self, "_hit_merged_components", None)
        if not isinstance(hit_threshold, np.ndarray) or not isinstance(
            hit_merged_components, np.ndarray
        ):
            raise ValueError(
                "peaklet_waveforms routed Numba path requires hit_merged_components "
                "and hit_threshold arrays"
            )
        hit_names = hit_threshold.dtype.names or ()
        if {"sample_start", "sample_end"}.issubset(hit_names):
            hit_starts = hit_threshold["sample_start"]
            hit_ends = hit_threshold["sample_end"]
        elif {"edge_start", "edge_end"}.issubset(hit_names):
            hit_starts = hit_threshold["edge_start"]
            hit_ends = hit_threshold["edge_end"]
        else:
            raise KeyError(
                "peaklet_waveforms requires hit_threshold sample_start/sample_end "
                "or edge_start/edge_end"
            )

        is_single_record = (
            merged["is_single_record"].astype(bool, copy=False)
            if "is_single_record" in merged_names
            else (np.asarray(merged_starts) >= 0) & (np.asarray(merged_ends) >= 0)
        )
        merged_to_hits = _build_hit_merged_components_index(hit_merged_components)
        record_lookup = RecordLookup(records)

        peak_ids: list[int] = []
        boards: list[int] = []
        channels: list[int] = []
        record_ids: list[int] = []
        record_indices: list[int] = []
        starts: list[int] = []
        ends: list[int] = []
        merged_indices: list[int] = []
        source_indices: list[int] = []
        cross_flags: list[bool] = []

        for component in components:
            peaklet_id = int(component["peak_id"])
            merged_index = int(component["merged_index"])
            if not 0 <= merged_index < len(merged):
                raise IndexError(f"peaklet_waveforms found invalid merged_index={merged_index}")
            hit = merged[merged_index]
            board = int(hit["board"])
            channel = int(hit["channel"])
            if bool(is_single_record[merged_index]):
                record_id = int(hit["record_id"])
                peak_ids.append(peaklet_id)
                boards.append(board)
                channels.append(channel)
                record_ids.append(record_id)
                record_indices.append(record_id)
                starts.append(int(merged_starts[merged_index]))
                ends.append(int(merged_ends[merged_index]))
                merged_indices.append(merged_index)
                source_indices.append(merged_index)
                cross_flags.append(False)
                continue

            for hit_index_value in merged_to_hits.get(merged_index, ()):
                hit_index = int(hit_index_value)
                if not 0 <= hit_index < len(hit_threshold):
                    raise IndexError(f"peaklet_waveforms found invalid hit_index={hit_index}")
                component_hit = hit_threshold[hit_index]
                record_id = int(component_hit["record_id"])
                peak_ids.append(peaklet_id)
                boards.append(board)
                channels.append(channel)
                record_ids.append(record_id)
                record_indices.append(record_id)
                starts.append(int(hit_starts[hit_index]))
                ends.append(int(hit_ends[hit_index]))
                merged_indices.append(merged_index)
                source_indices.append(hit_index)
                cross_flags.append(True)

        peak_ids_arr = np.asarray(peak_ids, dtype=np.int64)
        boards_arr = np.asarray(boards, dtype=np.int16)
        channels_arr = np.asarray(channels, dtype=np.int16)
        record_ids_arr = np.asarray(record_ids, dtype=np.int64)
        record_ids_arr = np.asarray(record_ids, dtype=np.int64)
        record_indices_arr = record_lookup.get_indices(record_ids_arr)
        starts_arr = np.asarray(starts, dtype=np.int64)
        ends_arr = np.asarray(ends, dtype=np.int64)
        merged_indices_arr = np.asarray(merged_indices, dtype=np.int64)
        source_indices_arr = np.asarray(source_indices, dtype=np.int64)
        cross_flags_arr = np.asarray(cross_flags, dtype=np.bool_)

        if len(peak_ids_arr):
            safe_record_indices = np.maximum(record_indices_arr, 0)
            timestamps = (
                records["timestamp"].astype(np.int64, copy=False)[safe_record_indices]
                if "timestamp" in (records.dtype.names or ())
                else np.zeros(len(safe_record_indices), dtype=np.int64)
            )
            record_dt = records["dt"].astype(np.int64, copy=False)[safe_record_indices]
            abs_starts = timestamps + np.maximum(starts_arr, 0) * record_dt * 1000
            order = np.lexsort(
                (
                    source_indices_arr,
                    abs_starts,
                    channels_arr,
                    boards_arr,
                    peak_ids_arr,
                )
            )
            peak_ids_arr = peak_ids_arr[order]
            boards_arr = boards_arr[order]
            channels_arr = channels_arr[order]
            record_ids_arr = record_ids_arr[order]
            record_indices_arr = record_indices_arr[order]
            starts_arr = starts_arr[order]
            ends_arr = ends_arr[order]
            merged_indices_arr = merged_indices_arr[order]
            cross_flags_arr = cross_flags_arr[order]

        counts = np.bincount(peak_ids_arr, minlength=len(peaklets))
        piece_ends = np.cumsum(counts, dtype=np.int64)
        piece_starts = piece_ends - counts
        empty = counts == 0
        piece_starts[empty] = -1
        piece_ends[empty] = -1
        return (
            starts_arr,
            ends_arr,
            record_indices_arr,
            cross_flags_arr,
            boards_arr,
            channels_arr,
            record_ids_arr,
            merged_indices_arr,
            piece_starts,
            piece_ends,
        )

    def _raise_numba_status(self, status: int, peaklet_id: int) -> None:
        if status == _STATUS_MIXED_DT:
            raise ValueError(
                f"peaklet_waveforms does not support mixed dt in peaklet_id={peaklet_id}"
            )
        if status == _STATUS_OFF_GRID:
            raise ValueError(f"peaklet_id={peaklet_id} samples are not aligned to a common dt grid")
        if status == _STATUS_NONFINITE:
            raise ValueError(f"peaklet_id={peaklet_id} contains non-finite waveform samples")
        if status == _STATUS_INVALID_RECORD:
            raise ValueError(f"peaklet_id={peaklet_id} references an unknown record_id")
        if status == _STATUS_INVALID_POOL:
            raise ValueError(f"peaklet_id={peaklet_id} references samples outside wave_pool")
        if status == _STATUS_INVALID_DT:
            raise ValueError(f"peaklet_id={peaklet_id} requires positive dt")
        raise RuntimeError(f"unknown peaklet waveform kernel status={status}")

    def _build_routed_numba(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        started = time.perf_counter()
        pieces = self._prepare_numba_pieces(
            peaklets=peaklets,
            components=components,
            merged=merged,
            records=records,
        )
        (
            piece_starts,
            piece_ends,
            piece_record_indices,
            piece_is_cross,
            piece_boards,
            piece_channels,
            piece_record_ids,
            piece_merged_indices,
            peaklet_piece_starts,
            peaklet_piece_ends,
        ) = pieces

        record_names = records.dtype.names or ()
        record_dt = records["dt"].astype(np.int64, copy=False)
        record_event_length = records["event_length"].astype(np.int64, copy=False)
        record_timestamp = (
            records["timestamp"].astype(np.int64, copy=False)
            if "timestamp" in record_names
            else np.zeros(len(records), dtype=np.int64)
        )
        record_wave_offset = records["wave_offset"].astype(np.int64, copy=False)
        record_baseline = (
            records["baseline"].astype(np.float32, copy=False)
            if "baseline" in record_names
            else np.zeros(len(records), dtype=np.float32)
        )
        record_sign = _extract_polarity_signs(records)
        jit_before = bool(getattr(_classify_and_size_peaklets_numba, "signatures", ()))
        classify_started = time.perf_counter()
        (
            waveform_rows,
            routes,
            total_wave_length,
            max_wave_length,
            input_samples,
            status,
            status_peaklet,
        ) = _classify_and_size_peaklets_numba(
            piece_starts,
            piece_ends,
            piece_record_indices,
            piece_is_cross,
            piece_boards,
            piece_channels,
            peaklet_piece_starts,
            peaklet_piece_ends,
            record_dt,
            record_event_length,
            record_timestamp,
            record_wave_offset,
            record_baseline,
            wave_pool,
        )
        classify_sec = time.perf_counter() - classify_started
        if status != _STATUS_OK:
            self._raise_numba_status(int(status), int(status_peaklet))

        pool64 = np.zeros(int(total_wave_length), dtype=np.float64)
        kernel_started = time.perf_counter()
        (
            conflict_peaklet,
            conflict_local_i,
            first_piece_i,
            other_piece_i,
            first_value,
            other_value,
            unique_samples,
        ) = _fill_routed_peaklet_pool_numba(
            pool64,
            waveform_rows,
            routes,
            piece_starts,
            piece_ends,
            piece_record_indices,
            piece_boards,
            piece_channels,
            piece_record_ids,
            piece_merged_indices,
            peaklet_piece_starts,
            peaklet_piece_ends,
            record_dt,
            record_event_length,
            record_timestamp,
            record_wave_offset,
            record_baseline,
            record_sign,
            wave_pool,
            bool(getattr(self, "_clip_negative_signal", False)),
            int(max_wave_length),
        )
        kernel_sec = time.perf_counter() - kernel_started
        if conflict_peaklet >= 0:
            abs_time_ps = (
                int(waveform_rows[conflict_peaklet, 1])
                + int(conflict_local_i) * int(waveform_rows[conflict_peaklet, 3]) * 1000
            )
            raise WaveformOverlapConflictError(
                f"peaklet_id={int(conflict_peaklet)} has conflicting overlap at "
                f"board={int(piece_boards[first_piece_i])}, "
                f"channel={int(piece_channels[first_piece_i])}, "
                f"abs_time_ps={abs_time_ps}: value={float(first_value)} "
                f"(record_id={int(piece_record_ids[first_piece_i])}, "
                f"merged_index={int(piece_merged_indices[first_piece_i])}) != "
                f"value={float(other_value)} "
                f"(record_id={int(piece_record_ids[other_piece_i])}, "
                f"merged_index={int(piece_merged_indices[other_piece_i])})"
            )

        waveforms = np.zeros(len(waveform_rows), dtype=PEAKLET_WAVEFORMS_DTYPE)
        for field_i, field in enumerate(PEAKLET_WAVEFORMS_DTYPE.names):
            waveforms[field] = waveform_rows[:, field_i]
        pool = pool64.astype(np.float32)
        self._log_route_diagnostics(
            n_peaklets=len(peaklets),
            n_fast=int(np.sum(routes == _ROUTE_FAST)),
            n_canonical=int(np.sum(routes == _ROUTE_CANONICAL)),
            n_fallback=0,
            input_samples=int(input_samples),
            unique_samples=int(unique_samples),
            classify_sec=classify_sec,
            kernel_sec=kernel_sec,
            jit_before=jit_before,
            jit_after=bool(getattr(_classify_and_size_peaklets_numba, "signatures", ())),
            total_sec=time.perf_counter() - started,
        )
        return waveforms, pool

    def _log_route_diagnostics(
        self,
        *,
        n_peaklets: int,
        n_fast: int,
        n_canonical: int,
        n_fallback: int,
        input_samples: int,
        unique_samples: int,
        classify_sec: float,
        kernel_sec: float,
        jit_before: bool,
        jit_after: bool,
        total_sec: float | None = None,
    ) -> None:
        if not getattr(self, "_log_waveform_diagnostics", False):
            return
        logger.info(
            "peaklet_waveforms diagnostics: n_peaklets=%s fast_peaklets=%s "
            "canonical_peaklets=%s fallback_peaklets=%s input_samples=%s "
            "unique_samples=%s classify_sec=%.6f kernel_sec=%.6f total_sec=%.6f "
            "jit_signature_before=%s jit_signature_after=%s",
            n_peaklets,
            n_fast,
            n_canonical,
            n_fallback,
            input_samples,
            unique_samples,
            classify_sec,
            kernel_sec,
            classify_sec + kernel_sec if total_sec is None else total_sec,
            jit_before,
            jit_after,
        )

    def _has_overlapping_channel_windows(
        self,
        *,
        components: np.ndarray,
        merged: np.ndarray,
        is_single_record: np.ndarray,
        records: np.ndarray,
    ) -> bool:
        """Return whether one peak/channel has overlapping sample windows."""
        if "dt" not in (records.dtype.names or ()):
            raise KeyError("records dt field is required")
        record_lookup = RecordLookup(records)
        hit_threshold = getattr(self, "_hit_threshold", None)
        component_rows = getattr(self, "_hit_merged_components", None)
        merged_to_hits = (
            _build_hit_merged_components_index(component_rows)
            if isinstance(component_rows, np.ndarray) and len(component_rows)
            else {}
        )
        windows: list[tuple[int, int, int, int, int]] = []

        for component in components:
            peaklet_id = int(component["peak_id"])
            merged_index = int(component["merged_index"])
            hit = merged[merged_index]
            board = int(hit["board"])
            channel = int(hit["channel"])

            if bool(is_single_record[merged_index]):
                record = record_lookup.get(int(hit["record_id"]))
                if record is None:
                    continue
                start = int(hit["sample_start"])
                end = int(hit["sample_end"])
                dt_ps = int(record["dt"]) * 1000
                timestamp = int(record["timestamp"])
                windows.append(
                    (peaklet_id, board, channel, timestamp + start * dt_ps, timestamp + end * dt_ps)
                )
                continue

            if not isinstance(hit_threshold, np.ndarray):
                continue
            for hit_index in merged_to_hits.get(merged_index, ()):  # cross-record members
                component_hit = hit_threshold[int(hit_index)]
                record = record_lookup.get(int(component_hit["record_id"]))
                if record is None:
                    continue
                start = int(component_hit["edge_start"])
                end = int(component_hit["edge_end"])
                dt_ps = int(record["dt"]) * 1000
                timestamp = int(record["timestamp"])
                windows.append(
                    (peaklet_id, board, channel, timestamp + start * dt_ps, timestamp + end * dt_ps)
                )

        windows.sort(key=lambda row: (row[0], row[1], row[2], row[3], row[4]))
        previous_key: tuple[int, int, int] | None = None
        previous_end = 0
        for peaklet_id, board, channel, start, end in windows:
            key = (peaklet_id, board, channel)
            if key == previous_key and start < previous_end:
                return True
            if key != previous_key:
                previous_key = key
                previous_end = end
            else:
                previous_end = max(previous_end, end)
        return False

    def _numba_inputs_are_canonical_safe(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> bool:
        """Return whether the all-single Numba path satisfies merger invariants."""
        record_lookup = RecordLookup(records)
        for merged_indices in _components_by_peaklet(components, len(peaklets)):
            common_dt_ps: int | None = None
            grid_origin: int | None = None
            for merged_index in merged_indices:
                hit = merged[int(merged_index)]
                record = record_lookup.get(int(hit["record_id"]))
                if record is None:
                    return False
                start = max(0, int(hit["sample_start"]))
                end = min(int(record["event_length"]), int(hit["sample_end"]))
                if end <= start:
                    continue
                dt_ns = int(record["dt"])
                if dt_ns <= 0:
                    return False
                dt_ps = dt_ns * 1000
                abs_start = int(record["timestamp"]) + start * dt_ps
                if common_dt_ps is None:
                    common_dt_ps = dt_ps
                    grid_origin = abs_start
                elif dt_ps != common_dt_ps or (abs_start - int(grid_origin)) % dt_ps != 0:
                    return False
                baseline = float(record["baseline"])
                offset = int(record["wave_offset"])
                raw = wave_pool[offset + start : offset + end]
                if not np.isfinite(baseline) or not np.all(np.isfinite(raw)):
                    return False
        return True

    def _build_canonical(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build with the provenance-aware merger, optionally across processes."""
        n_workers = int(getattr(self, "_n_workers", 1))
        parallel_threshold = int(getattr(self, "_parallel_threshold", 5000))
        if (
            HAS_MULTIPROCESSING
            and n_workers != 1
            and len(peaklets) >= parallel_threshold
            and isinstance(getattr(self, "_hit_merged_components", None), np.ndarray)
            and isinstance(getattr(self, "_hit_threshold", None), np.ndarray)
        ):
            return self._build_python_parallel(
                peaklets=peaklets,
                components=components,
                merged=merged,
                records=records,
                wave_pool=wave_pool,
                n_workers=n_workers,
            )
        return self._build_python(
            peaklets=peaklets,
            components=components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )

    def _build_cross_record_numba(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        is_single_record: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compatibility entry point for callers that explicitly request cross-record JIT."""
        return self._build_routed_numba(
            peaklets=peaklets,
            components=components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )

        # Legacy two-pass implementation retained below while cached callers
        # migrate to the canonical path.
        if self._has_overlapping_channel_windows(
            components=components,
            merged=merged,
            is_single_record=is_single_record,
            records=records,
        ):
            return self._build_python(
                peaklets=peaklets,
                components=components,
                merged=merged,
                records=records,
                wave_pool=wave_pool,
            )
        hit_merged_components = getattr(self, "_hit_merged_components", None)
        hit_threshold = getattr(self, "_hit_threshold", None)
        if not isinstance(hit_merged_components, np.ndarray) or not isinstance(
            hit_threshold, np.ndarray
        ):
            raise ValueError(
                "peaklet_waveforms cross-record path requires hit_merged_components "
                "and hit_threshold arrays"
            )

        t0 = time.perf_counter()
        grouped_merged_indices, peaklet_comp_starts, peaklet_comp_ends = (
            _build_peaklet_component_csr(components, len(peaklets))
        )
        merged_names = merged.dtype.names or ()
        if {"component_offset", "component_count"}.issubset(merged_names):
            grouped_hit_indices = hit_merged_components["hit_index"].astype(np.int64, copy=False)
            merged_hit_starts = merged["component_offset"].astype(np.int64, copy=False)
            merged_hit_ends = merged_hit_starts + merged["component_count"].astype(
                np.int64, copy=False
            )
            if (
                np.any(merged_hit_starts < 0)
                or np.any(merged_hit_ends < merged_hit_starts)
                or np.any(merged_hit_ends > len(grouped_hit_indices))
            ):
                raise ValueError("peaklet_waveforms found invalid hit_merged component offsets")
        else:
            grouped_hit_indices, merged_hit_starts, merged_hit_ends = _build_hmc_csr(
                hit_merged_components, len(merged)
            )

        if {"sample_start", "sample_end"}.issubset(merged_names):
            merged_sample_starts = merged["sample_start"]
            merged_sample_ends = merged["sample_end"]
        elif {"edge_start", "edge_end"}.issubset(merged_names):
            merged_sample_starts = merged["edge_start"]
            merged_sample_ends = merged["edge_end"]
        else:
            raise KeyError(
                "peaklet_waveforms requires hit_merged sample_start/sample_end "
                "or edge_start/edge_end"
            )
        if "record_id" not in merged_names:
            raise KeyError("peaklet_waveforms requires hit_merged record_id")

        merged_component_counts = (
            merged["component_count"].astype(np.int64, copy=False)
            if "component_count" in merged_names
            else np.zeros(len(merged), dtype=np.int64)
        )
        direct_merged = np.asarray(is_single_record, dtype=bool) & (merged_component_counts == 1)

        hit_names = hit_threshold.dtype.names or ()
        if {"sample_start", "sample_end"}.issubset(hit_names):
            hit_sample_starts = hit_threshold["sample_start"].astype(np.int64, copy=False)
            hit_sample_ends = hit_threshold["sample_end"].astype(np.int64, copy=False)
        elif {"edge_start", "edge_end"}.issubset(hit_names):
            hit_sample_starts = hit_threshold["edge_start"].astype(np.int64, copy=False)
            hit_sample_ends = hit_threshold["edge_end"].astype(np.int64, copy=False)
        else:
            raise KeyError(
                "peaklet_waveforms requires hit_threshold sample_start/sample_end "
                "or edge_start/edge_end"
            )

        if "record_id" not in hit_names:
            raise KeyError("peaklet_waveforms requires hit_threshold record_id")
        record_lookup = RecordLookup(records)
        hit_record_ids = hit_threshold["record_id"].astype(np.int64, copy=False)
        hit_record_indices = record_lookup.get_indices(hit_record_ids).astype(np.int64, copy=False)
        merged_record_indices = record_lookup.get_indices(
            merged["record_id"].astype(np.int64, copy=False)
        ).astype(np.int64, copy=False)

        record_names = records.dtype.names or ()
        if "dt" not in record_names:
            raise KeyError("peaklet_waveforms cross-record path requires records dt")
        for required in ("event_length", "wave_offset"):
            if required not in record_names:
                raise KeyError(f"peaklet_waveforms cross-record path requires records {required}")

        record_dt = records["dt"].astype(np.int64, copy=False)
        record_event_length = records["event_length"].astype(np.int64, copy=False)
        record_timestamp = (
            records["timestamp"].astype(np.int64, copy=False)
            if "timestamp" in record_names
            else np.zeros(len(records), dtype=np.int64)
        )
        record_wave_offset = records["wave_offset"].astype(np.int64, copy=False)
        record_baseline = (
            records["baseline"].astype(np.float32, copy=False)
            if "baseline" in record_names
            else np.zeros(len(records), dtype=np.float32)
        )
        record_sign = _extract_polarity_signs(records)
        time_prepare_csr = time.perf_counter() - t0

        t_first = time.perf_counter()
        waveform_rows, total_wave_length = _first_pass_cross_record_numba(
            grouped_merged_indices,
            peaklet_comp_starts,
            peaklet_comp_ends,
            direct_merged,
            merged_record_indices,
            merged_sample_starts,
            merged_sample_ends,
            grouped_hit_indices,
            merged_hit_starts,
            merged_hit_ends,
            hit_record_indices,
            hit_sample_starts,
            hit_sample_ends,
            record_dt,
            record_event_length,
            record_timestamp,
        )
        time_first_pass = time.perf_counter() - t_first

        for peaklet_id in range(len(waveform_rows)):
            if waveform_rows[peaklet_id, 1] == -1:
                raise ValueError(
                    f"peaklet_waveforms does not support mixed dt in peaklet_id={peaklet_id}"
                )

        t_second = time.perf_counter()
        pool = np.zeros(int(total_wave_length), dtype=np.float32)
        _fill_cross_record_pool_numba(
            pool,
            waveform_rows,
            grouped_merged_indices,
            peaklet_comp_starts,
            peaklet_comp_ends,
            direct_merged,
            merged_record_indices,
            merged_sample_starts,
            merged_sample_ends,
            grouped_hit_indices,
            merged_hit_starts,
            merged_hit_ends,
            hit_record_indices,
            hit_sample_starts,
            hit_sample_ends,
            record_dt,
            record_event_length,
            record_timestamp,
            record_wave_offset,
            record_baseline,
            record_sign,
            wave_pool,
            bool(getattr(self, "_clip_negative_signal", False)),
        )
        time_second_pass = time.perf_counter() - t_second

        waveforms = np.zeros(len(waveform_rows), dtype=PEAKLET_WAVEFORMS_DTYPE)
        waveforms["peak_id"] = waveform_rows[:, 0]
        waveforms["time_start"] = waveform_rows[:, 1]
        waveforms["time_end"] = waveform_rows[:, 2]
        waveforms["dt"] = waveform_rows[:, 3]
        waveforms["wave_offset"] = waveform_rows[:, 4]
        waveforms["wave_length"] = waveform_rows[:, 5]

        if getattr(self, "_log_waveform_diagnostics", False):
            component_peak_ids = components["peak_id"].astype(np.int64, copy=False)
            component_merged_indices = components["merged_index"].astype(np.int64, copy=False)
            component_is_cross = ~is_single_record[component_merged_indices]
            if len(component_peak_ids) > 0:
                cross_counts = np.bincount(
                    component_peak_ids[component_is_cross], minlength=len(peaklets)
                )
                fraction_peaklet_with_cross_record = float(np.mean(cross_counts > 0))
            else:
                fraction_peaklet_with_cross_record = 0.0
            logger.info(
                "peaklet_waveforms diagnostics: "
                "n_peaklets=%s n_merged=%s n_hit_threshold=%s "
                "fraction_cross_record_merged=%.6f "
                "fraction_direct_merged=%.6f "
                "fraction_peaklet_with_cross_record=%.6f "
                "total_waveform_pool_length=%s "
                "time_prepare_csr=%.6fs time_first_pass=%.6fs "
                "time_second_pass=%.6fs time_total=%.6fs",
                len(peaklets),
                len(merged),
                len(hit_threshold),
                float(np.mean(~is_single_record)) if len(is_single_record) else 0.0,
                float(np.mean(direct_merged)) if len(direct_merged) else 0.0,
                fraction_peaklet_with_cross_record,
                int(total_wave_length),
                time_prepare_csr,
                time_first_pass,
                time_second_pass,
                time.perf_counter() - t0,
            )

        return waveforms, pool

    def _build_hybrid(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        is_single_record: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Hybrid strategy: use Numba for single-record peaklets, Python for cross-record.

        This significantly improves performance when only a small fraction of peaklets
        contain cross-record hits.
        """
        # Build mapping: which merged indices belong to which peaklet
        component_peak_ids = components["peak_id"]
        component_merged_indices = components["merged_index"]

        # Vectorized check: for each peaklet, does it contain any cross-record hit?
        # This is faster than looping through each peaklet
        peaklet_has_cross_record = np.zeros(len(peaklets), dtype=bool)

        # Create mapping: component index -> is_cross_record
        component_is_cross = ~is_single_record[component_merged_indices]

        # Use bincount to check if any component in each peaklet is cross-record
        # bincount counts True (1) values per peaklet_id
        cross_counts = np.bincount(component_peak_ids[component_is_cross], minlength=len(peaklets))
        peaklet_has_cross_record = cross_counts > 0

        # Split into two groups
        single_record_mask = ~peaklet_has_cross_record
        cross_record_mask = peaklet_has_cross_record

        n_single = np.sum(single_record_mask)
        n_cross = np.sum(cross_record_mask)

        # Process single-record peaklets with Numba
        if n_single > 0:
            single_peaklet_ids = np.flatnonzero(single_record_mask)
            single_component_mask = np.isin(component_peak_ids, single_peaklet_ids)
            single_components = components[single_component_mask]

            # Remap peak_id to 0-based for the subset
            peak_id_map = np.full(len(peaklets), -1, dtype=np.int64)
            peak_id_map[single_peaklet_ids] = np.arange(n_single)
            single_components_remapped = single_components.copy()
            single_components_remapped["peak_id"] = peak_id_map[single_components["peak_id"]]

            # Create subset peaklets array
            single_peaklets = peaklets[single_peaklet_ids]

            # Use Numba for this subset
            single_waveforms, single_pool = self._build_numba(
                peaklets=single_peaklets,
                components=single_components_remapped,
                merged=merged,
                records=records,
                wave_pool=wave_pool,
            )
        else:
            single_waveforms = _empty_waveforms()
            single_pool = _empty_waveform_pool()

        # Process cross-record peaklets with Python
        if n_cross > 0:
            cross_peaklet_ids = np.flatnonzero(cross_record_mask)
            cross_component_mask = np.isin(component_peak_ids, cross_peaklet_ids)
            cross_components = components[cross_component_mask]

            # Remap peak_id
            peak_id_map = np.full(len(peaklets), -1, dtype=np.int64)
            peak_id_map[cross_peaklet_ids] = np.arange(n_cross)
            cross_components_remapped = cross_components.copy()
            cross_components_remapped["peak_id"] = peak_id_map[cross_components["peak_id"]]

            cross_peaklets = peaklets[cross_peaklet_ids]

            # Determine if we should use parallel processing
            n_workers = getattr(self, "_n_workers", 1)
            parallel_threshold = getattr(self, "_parallel_threshold", 5000)

            use_parallel = HAS_MULTIPROCESSING and n_workers != 1 and n_cross >= parallel_threshold

            if use_parallel:
                # Parallel processing for cross-record peaklets
                cross_waveforms, cross_pool = self._build_python_parallel(
                    peaklets=cross_peaklets,
                    components=cross_components_remapped,
                    merged=merged,
                    records=records,
                    wave_pool=wave_pool,
                    n_workers=n_workers,
                )
            else:
                # Use Python for this subset
                cross_waveforms, cross_pool = self._build_python(
                    peaklets=cross_peaklets,
                    components=cross_components_remapped,
                    merged=merged,
                    records=records,
                    wave_pool=wave_pool,
                )
        else:
            cross_waveforms = _empty_waveforms()
            cross_pool = _empty_waveform_pool()

        # Merge results
        # Concatenate pools
        merged_pool = np.concatenate([single_pool, cross_pool]).astype(np.float32, copy=False)

        # Merge waveform rows and adjust offsets
        merged_waveforms = np.zeros(len(peaklets), dtype=PEAKLET_WAVEFORMS_DTYPE)

        # Copy single-record results
        if n_single > 0:
            single_peaklet_ids = np.flatnonzero(single_record_mask)
            for i, peaklet_id in enumerate(single_peaklet_ids):
                merged_waveforms[peaklet_id] = single_waveforms[i]

        # Copy cross-record results and adjust wave_offset
        if n_cross > 0:
            cross_peaklet_ids = np.flatnonzero(cross_record_mask)
            single_pool_size = len(single_pool)
            for i, peaklet_id in enumerate(cross_peaklet_ids):
                merged_waveforms[peaklet_id] = cross_waveforms[i]
                merged_waveforms[peaklet_id]["wave_offset"] += single_pool_size

        return merged_waveforms, merged_pool

    def _build_numba(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Numba 加速路径 - 仅处理单 record 的 hit_merged"""
        if self._has_overlapping_channel_windows(
            components=components,
            merged=merged,
            is_single_record=np.ones(len(merged), dtype=bool),
            records=records,
        ) or not self._numba_inputs_are_canonical_safe(
            peaklets=peaklets,
            components=components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        ):
            return self._build_canonical(
                peaklets=peaklets,
                components=components,
                merged=merged,
                records=records,
                wave_pool=wave_pool,
            )
        # Note: Caller (_build_hybrid) ensures all merged hits are single-record
        # No need to check for cross-record here

        # 批量解析 record_id
        record_lookup = RecordLookup(records)
        record_ids = merged["record_id"]
        record_indices = record_lookup.get_indices(record_ids)

        # 提取 merged 字段
        merged_names = merged.dtype.names or ()
        if {"sample_start", "sample_end"}.issubset(merged_names):
            merged_sample_starts = merged["sample_start"].astype(np.int64)
            merged_sample_ends = merged["sample_end"].astype(np.int64)
        elif {"edge_start", "edge_end"}.issubset(merged_names):
            merged_sample_starts = merged["edge_start"].astype(np.int64)
            merged_sample_ends = merged["edge_end"].astype(np.int64)
        else:
            raise KeyError(
                "peaklet_waveforms requires sample_start/sample_end or edge_start/edge_end"
            )

        merged_dt = merged["dt"].astype(np.int64)

        # 提取 record 字段
        record_names = records.dtype.names or ()
        record_dt = records["dt"].astype(np.int64) if "dt" in record_names else merged_dt
        record_baseline = (
            records["baseline"].astype(np.float32)
            if "baseline" in record_names
            else np.zeros(len(records), dtype=np.float32)
        )
        record_wave_offset = records["wave_offset"].astype(np.int64)
        record_event_length = records["event_length"].astype(np.int64)
        record_timestamp = (
            records["timestamp"].astype(np.int64)
            if "timestamp" in record_names
            else np.zeros(len(records), dtype=np.int64)
        )
        record_sign = _extract_polarity_signs(records)

        # 调用 Numba 核心
        waveform_rows, pool = _build_waveforms_numba(
            components["peak_id"].astype(np.int64),
            components["merged_index"].astype(np.int64),
            record_ids.astype(np.int64),
            merged_sample_starts,
            merged_sample_ends,
            merged_dt,
            record_indices,
            record_dt,
            record_baseline,
            record_wave_offset,
            record_event_length,
            record_timestamp,
            record_sign,
            wave_pool,
            bool(getattr(self, "_clip_negative_signal", False)),
        )

        # 检查混合 dt 错误
        for i in range(len(waveform_rows)):
            if waveform_rows[i, 1] == -1:
                raise ValueError(f"peaklet_waveforms does not support mixed dt in peaklet_id={i}")

        # 转换为结构化数组
        waveforms = np.zeros(len(waveform_rows), dtype=PEAKLET_WAVEFORMS_DTYPE)
        waveforms["peak_id"] = waveform_rows[:, 0]
        waveforms["time_start"] = waveform_rows[:, 1]
        waveforms["time_end"] = waveform_rows[:, 2]
        waveforms["dt"] = waveform_rows[:, 3]
        waveforms["wave_offset"] = waveform_rows[:, 4]
        waveforms["wave_length"] = waveform_rows[:, 5]

        return waveforms, pool

    def _build_python_parallel(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
        n_workers: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Parallel processing of cross-record peaklets.

        Split peaklets into batches and process them in parallel using multiprocessing.
        """
        n_peaklets = len(peaklets)

        # Split peaklets into batches
        batch_size = max(1, n_peaklets // n_workers)
        batches = []

        for i in range(0, n_peaklets, batch_size):
            end_idx = min(i + batch_size, n_peaklets)
            batch_peaklet_ids = np.arange(i, end_idx)

            # Filter components for this batch
            batch_component_mask = np.isin(components["peak_id"], batch_peaklet_ids)
            batch_components = components[batch_component_mask].copy()

            # Remap peak_id to be 0-based within this batch
            old_to_new = np.full(n_peaklets, -1, dtype=np.int64)
            old_to_new[batch_peaklet_ids] = np.arange(len(batch_peaklet_ids))
            batch_components["peak_id"] = old_to_new[batch_components["peak_id"]]

            batches.append(
                {
                    "peaklets": peaklets[batch_peaklet_ids],
                    "components": batch_components,
                    "merged": merged,
                    "records": records,
                    "wave_pool": wave_pool,
                    "hit_merged_components": getattr(self, "_hit_merged_components", None),
                    "hit_threshold": getattr(self, "_hit_threshold", None),
                    "clip_negative_signal": bool(getattr(self, "_clip_negative_signal", False)),
                    "peaklet_id_offset": i,
                }
            )

        # Process batches in parallel
        with Pool(n_workers) as pool:
            results = pool.map(_process_peaklet_batch, batches)

        # Merge results from all batches
        all_waveforms = []
        all_pools = []
        cumulative_offset = 0

        for batch, (batch_waveforms, batch_pool) in zip(batches, results, strict=False):
            # Adjust wave_offset
            if len(batch_waveforms) > 0:
                batch_waveforms["wave_offset"] += cumulative_offset
                batch_waveforms["peak_id"] += int(batch["peaklet_id_offset"])
            all_waveforms.append(batch_waveforms)
            all_pools.append(batch_pool)
            cumulative_offset += len(batch_pool)

        # Concatenate all results
        if all_waveforms:
            final_waveforms = np.concatenate(all_waveforms)
        else:
            final_waveforms = _empty_waveforms()

        if all_pools:
            final_pool = np.concatenate(all_pools).astype(np.float32, copy=False)
        else:
            final_pool = _empty_waveform_pool()

        return final_waveforms, final_pool

    def _build_python(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Python fallback 路径，支持跨 record 的 hit_merged"""
        record_lookup = RecordLookup(records)

        # Get cross-record dependencies (from _compute_waveforms_and_pool)
        hit_merged_components = getattr(self, "_hit_merged_components", None)
        hit_threshold = getattr(self, "_hit_threshold", None)
        if (
            hit_merged_components is not None
            and len(hit_merged_components) > 0
            and getattr(self, "_hit_merged_components_index", None) is None
        ):
            self._hit_merged_components_index = _build_hit_merged_components_index(
                hit_merged_components
            )

        component_groups = _components_by_peaklet(components, len(peaklets))
        rows: list[tuple[int, int, int, int, int, int]] = []
        pools: list[np.ndarray] = []
        wave_offset = 0

        for peaklet_id, merged_indices in enumerate(component_groups):
            if len(merged_indices) == 0:
                rows.append((peaklet_id, 0, 0, 0, wave_offset, 0))
                continue

            segments: list[dict[str, Any]] = []

            for merged_index in merged_indices:
                hit = merged[int(merged_index)]

                # Detect cross-record hit
                is_single_record = (
                    bool(hit["is_single_record"])
                    if "is_single_record" in hit.dtype.names
                    else (int(hit["sample_start"]) >= 0 and int(hit["sample_end"]) >= 0)
                )

                if (
                    not is_single_record
                    and hit_merged_components is not None
                    and hit_threshold is not None
                ):
                    # Cross-record path: expand into multiple pieces
                    multi_pieces = _merged_wave_pieces_multirecord(
                        hit=hit,
                        hit_merged_components_index=getattr(
                            self, "_hit_merged_components_index", {}
                        ),
                        hit_threshold=hit_threshold,
                        records=records,
                        record_lookup=record_lookup,
                        wave_pool=wave_pool,
                        merged_index=int(merged_index),
                        clip_negative_signal=bool(getattr(self, "_clip_negative_signal", False)),
                    )

                    for start_ps, _end_ps, piece_dt_ns, signal, record_id in multi_pieces:
                        if len(signal) == 0:
                            continue
                        segments.append(
                            {
                                "waveform": signal,
                                "abs_time_ps": start_ps
                                + np.arange(len(signal), dtype=np.int64) * piece_dt_ns * 1000,
                                "dt": piece_dt_ns,
                                "board": int(hit["board"]),
                                "channel": int(hit["channel"]),
                                "record_id": record_id,
                                "merged_index": int(merged_index),
                            }
                        )
                else:
                    # Single-record path
                    start_ps, _end_ps, piece_dt_ns, signal, record_id = _merged_wave_piece(
                        hit=hit,
                        records=records,
                        record_lookup=record_lookup,
                        wave_pool=wave_pool,
                        clip_negative_signal=bool(getattr(self, "_clip_negative_signal", False)),
                    )
                    if len(signal) == 0:
                        continue
                    segments.append(
                        {
                            "waveform": signal,
                            "abs_time_ps": start_ps
                            + np.arange(len(signal), dtype=np.int64) * piece_dt_ns * 1000,
                            "dt": piece_dt_ns,
                            "board": int(hit["board"]),
                            "channel": int(hit["channel"]),
                            "record_id": record_id,
                            "merged_index": int(merged_index),
                        }
                    )

            if not segments:
                rows.append((peaklet_id, 0, 0, 0, wave_offset, 0))
                continue

            merged_waveform = merge_waveform_segments(
                segments,
                sum_channels=True,
                dense=True,
                context=f"peaklet_id={peaklet_id}",
            )
            summed = merged_waveform["waveform"]
            dt_ns = int(merged_waveform["dt"])
            time_start = int(merged_waveform["abs_time_ps"][0])
            wave_length = len(summed)
            time_end = time_start + wave_length * dt_ns * 1000

            rows.append((peaklet_id, time_start, time_end, dt_ns, wave_offset, wave_length))
            pools.append(summed)
            wave_offset += wave_length

        pool = (
            np.concatenate(pools).astype(np.float32, copy=False)
            if pools
            else _empty_waveform_pool()
        )
        return np.array(rows, dtype=PEAKLET_WAVEFORMS_DTYPE) if rows else _empty_waveforms(), pool


__all__ = ["PeakletWaveformPlugin"]
