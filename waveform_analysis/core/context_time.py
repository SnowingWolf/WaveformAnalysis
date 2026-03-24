from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np

from .hardware.channel import HardwareChannel


class ContextTimeDomain:
    """Time-axis and time-range helpers used by Context."""

    def __init__(self, context: Any) -> None:
        self.ctx = context

    def normalize_time_domain(self, time_domain: str) -> str:
        normalized = str(time_domain).strip().lower()
        if normalized not in self.ctx._TIME_DOMAIN_CHOICES:
            allowed = ", ".join(sorted(self.ctx._TIME_DOMAIN_CHOICES))
            raise ValueError(
                f"Unsupported time_domain '{time_domain}'. Expected one of: {allowed}."
            )
        return normalized

    def resolve_time_axis(
        self,
        data: np.ndarray,
        data_name: str,
        time_domain: str,
        time_field: str | None = None,
    ) -> tuple[str, np.ndarray | None]:
        if not isinstance(data, np.ndarray) or data.dtype.names is None:
            raise ValueError(
                f"Data '{data_name}' is not a structured array; cannot resolve time axis."
            )
        domain = self.normalize_time_domain(time_domain)
        names = data.dtype.names or ()
        if time_field:
            if time_field not in names:
                raise ValueError(
                    f"Time field '{time_field}' not found in {data_name}. Available fields: {list(names)}"
                )
            return time_field, None
        if domain == self.ctx._TIME_DOMAIN_RAW_PS:
            for candidate in ("timestamp_ps", "timestamp"):
                if candidate in names:
                    return candidate, None
            raise ValueError(
                f"Cannot resolve raw_ps time axis for {data_name}. "
                "Expected one of ['timestamp_ps', 'timestamp']."
            )
        for candidate in ("time_ns", "time"):
            if candidate in names:
                return candidate, None
        for candidate in ("timestamp_ps", "timestamp"):
            if candidate in names:
                derived = np.asarray(data[candidate], dtype=np.int64) // 1000
                return "time_ns", derived
        raise ValueError(
            f"Cannot resolve system_ns time axis for {data_name}. "
            "Expected one of ['time_ns', 'time', 'timestamp_ps', 'timestamp']."
        )

    def build_time_index(
        self,
        run_id: str,
        data_name: str,
        time_field: str | None = None,
        endtime_field: str | None = None,
        force_rebuild: bool = False,
        time_domain: str = "system_ns",
    ) -> dict[str, Any]:
        from waveform_analysis.core.data.query import TimeRangeQueryEngine

        if not hasattr(self.ctx, "_time_query_engine"):
            self.ctx._time_query_engine = TimeRangeQueryEngine()
        engine = self.ctx._time_query_engine
        data = self.ctx.get_data(run_id, data_name)
        if data is None or (hasattr(data, "__len__") and len(data) == 0):
            self.ctx.logger.warning("No data found for %s, cannot build index", data_name)
            return {"type": "empty", "indices": [], "stats": {}}
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], np.ndarray):
            if self.ctx._expects_flat_channel_array(data_name):
                self.ctx.logger.warning(
                    "Data '%s' is a legacy list-of-arrays. Recompute to use a single array with a channel field.",
                    data_name,
                )
            return self.build_multi_channel_time_index(
                engine,
                run_id,
                data_name,
                data,
                time_field,
                endtime_field,
                force_rebuild,
                time_domain,
            )
        if isinstance(data, np.ndarray) and data.dtype.names is not None:
            resolved_time_field, derived_time_values = self.resolve_time_axis(
                data, data_name, time_domain, time_field=time_field
            )
            engine.build_index(
                run_id,
                data_name,
                data,
                resolved_time_field,
                endtime_field,
                force_rebuild,
                time_values=derived_time_values,
            )
            index = engine.get_index(run_id, data_name)
            return {
                "type": "single",
                "indices": [data_name],
                "stats": {
                    data_name: {
                        "n_records": index.n_records if index else 0,
                        "time_range": (index.min_time, index.max_time) if index else (0, 0),
                        "build_time": index.build_time if index else 0.0,
                    }
                },
            }
        self.ctx.logger.warning("Data '%s' is not a supported type for time indexing", data_name)
        return {"type": "unsupported", "indices": [], "stats": {}}

    def time_range(
        self,
        run_id: str,
        data_name: str,
        start_time: int | None = None,
        end_time: int | None = None,
        time_field: str | None = None,
        endtime_field: str | None = None,
        auto_build_index: bool = True,
        channel: int | HardwareChannel | tuple[int, int] | str | None = None,
        time_domain: str = "system_ns",
    ) -> np.ndarray | list[np.ndarray]:
        from waveform_analysis.core.data.query import TimeRangeQueryEngine

        if not hasattr(self.ctx, "_time_query_engine"):
            self.ctx._time_query_engine = TimeRangeQueryEngine()
        engine = self.ctx._time_query_engine
        data = self.ctx.get_data(run_id, data_name)
        if data is None:
            return np.array([], dtype=np.float64)
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], np.ndarray):
            if self.ctx._expects_flat_channel_array(data_name):
                self.ctx.logger.warning(
                    "Data '%s' is a legacy list-of-arrays. Recompute to use a single array with a channel field.",
                    data_name,
                )
            return self.query_multi_channel_time_range(
                engine,
                run_id,
                data_name,
                data,
                start_time,
                end_time,
                time_field,
                endtime_field,
                auto_build_index,
                channel,
                time_domain,
            )
        if isinstance(data, np.ndarray):
            if len(data) == 0:
                return np.array([], dtype=data.dtype)
            if data.dtype.names is None:
                self.ctx.logger.warning(
                    "Data '%s' is not a structured array, returning full data", data_name
                )
                return data
            return self.query_single_array_time_range(
                engine,
                run_id,
                data_name,
                data,
                start_time,
                end_time,
                time_field,
                endtime_field,
                auto_build_index,
                channel,
                time_domain,
            )
        self.ctx.logger.warning("Data '%s' is not a supported type, returning as-is", data_name)
        return data

    def clear_time_index(self, run_id: str | None = None, data_name: str | None = None) -> None:
        if hasattr(self.ctx, "_time_query_engine"):
            self.ctx._time_query_engine.clear_index(run_id, data_name)

    def get_time_index_stats(self) -> dict[str, Any]:
        if hasattr(self.ctx, "_time_query_engine"):
            return self.ctx._time_query_engine.get_stats()
        return {"total_indices": 0, "indices": {}}

    def normalize_channel_ref(
        self,
        channel: int | HardwareChannel | tuple[int, int] | str | None,
    ) -> int | HardwareChannel | None:
        if channel is None:
            return None
        if isinstance(channel, HardwareChannel):
            return channel
        if isinstance(channel, tuple) and len(channel) == 2:
            return HardwareChannel(int(channel[0]), int(channel[1]))
        if isinstance(channel, str):
            if ":" not in channel:
                raise ValueError(
                    f"Invalid channel selector {channel!r}; expected an integer index for "
                    'legacy list data, or "board:channel" for flat arrays.'
                )
            board, ch = channel.split(":", 1)
            return HardwareChannel(int(board.strip()), int(ch.strip()))
        if isinstance(channel, int):
            return channel
        raise ValueError(
            f"Invalid channel selector {channel!r}; expected int, HardwareChannel, "
            '(board, channel), or "board:channel".'
        )

    def query_single_array_time_range(
        self,
        engine: Any,
        run_id: str,
        data_name: str,
        data: np.ndarray,
        start_time: int | None,
        end_time: int | None,
        time_field: str | None,
        endtime_field: str | None,
        auto_build_index: bool,
        channel: int | HardwareChannel | tuple[int, int] | str | None = None,
        time_domain: str = "system_ns",
    ) -> np.ndarray:
        resolved_time_field, derived_time_values = self.resolve_time_axis(
            data, data_name, time_domain, time_field=time_field
        )
        if auto_build_index and not engine.has_index(run_id, data_name):
            engine.build_index(
                run_id,
                data_name,
                data,
                resolved_time_field,
                endtime_field,
                time_values=derived_time_values,
            )
        if engine.has_index(run_id, data_name):
            indices = engine.query(run_id, data_name, start_time, end_time)
            result = (
                data[indices]
                if indices is not None and len(indices) > 0
                else np.array([], dtype=data.dtype)
            )
        else:
            self.ctx.logger.warning("No index for %s, using direct filtering", data_name)
            times = (
                derived_time_values
                if derived_time_values is not None
                else np.asarray(data[resolved_time_field], dtype=np.int64)
            )
            filter_start = start_time if start_time is not None else int(times.min())
            filter_end = end_time if end_time is not None else int(times.max()) + 1
            mask = (times >= filter_start) & (times < filter_end)
            result = data[mask]
        normalized_channel = self.normalize_channel_ref(channel)
        if normalized_channel is None:
            return result
        if not isinstance(normalized_channel, HardwareChannel):
            raise ValueError(
                'Flat array time_range filtering now requires an explicit hardware channel like "board:channel" or (board, channel).'
            )
        if "channel" not in result.dtype.names or "board" not in result.dtype.names:
            raise ValueError(
                f"Data '{data_name}' must expose both 'board' and 'channel' fields for flat-array channel filtering."
            )
        return result[
            (result["board"] == normalized_channel.board)
            & (result["channel"] == normalized_channel.channel)
        ]

    def query_multi_channel_time_range(
        self,
        engine: Any,
        run_id: str,
        data_name: str,
        data: list[np.ndarray],
        start_time: int | None,
        end_time: int | None,
        time_field: str | None,
        endtime_field: str | None,
        auto_build_index: bool,
        channel: int | HardwareChannel | tuple[int, int] | str | None,
        time_domain: str,
    ) -> np.ndarray | list[np.ndarray]:
        n_channels = len(data)
        if auto_build_index:
            has_indices = (
                hasattr(self.ctx, "_multi_channel_indices")
                and (run_id, data_name) in self.ctx._multi_channel_indices
            )
            if not has_indices:
                self.build_time_index(
                    run_id,
                    data_name,
                    time_field=time_field,
                    endtime_field=endtime_field,
                    time_domain=time_domain,
                )
        normalized_channel = self.normalize_channel_ref(channel)
        if normalized_channel is not None:
            if not isinstance(normalized_channel, int):
                raise ValueError(
                    "Legacy list-of-arrays time_range only supports integer channel indices."
                )
            channel = normalized_channel
            if channel < 0 or channel >= n_channels:
                self.ctx.logger.warning(
                    "Channel %s out of range [0, %s), returning empty array", channel, n_channels
                )
                return np.array([], dtype=data[0].dtype if n_channels > 0 else np.float64)
            return self.query_channel_time_range(
                engine,
                run_id,
                data_name,
                data[channel],
                channel,
                start_time,
                end_time,
                time_field,
                time_domain,
            )
        return [
            self.query_channel_time_range(
                engine,
                run_id,
                data_name,
                ch_data,
                ch_idx,
                start_time,
                end_time,
                time_field,
                time_domain,
            )
            for ch_idx, ch_data in enumerate(data)
        ]

    def query_channel_time_range(
        self,
        engine: Any,
        run_id: str,
        data_name: str,
        ch_data: np.ndarray,
        ch_idx: int,
        start_time: int | None,
        end_time: int | None,
        time_field: str | None,
        time_domain: str,
    ) -> np.ndarray:
        if ch_data is None or len(ch_data) == 0:
            return np.array([], dtype=ch_data.dtype if ch_data is not None else np.float64)
        index_name = f"{data_name}_ch{ch_idx}"
        if engine.has_index(run_id, index_name):
            indices = engine.query(run_id, index_name, start_time, end_time)
            return (
                ch_data[indices]
                if indices is not None and len(indices) > 0
                else np.array([], dtype=ch_data.dtype)
            )
        resolved_time_field, derived_time_values = self.resolve_time_axis(
            ch_data,
            f"{data_name}_ch{ch_idx}",
            time_domain,
            time_field=time_field,
        )
        times = (
            derived_time_values
            if derived_time_values is not None
            else np.asarray(ch_data[resolved_time_field], dtype=np.int64)
        )
        if len(times) == 0:
            return np.array([], dtype=ch_data.dtype)
        filter_start = start_time if start_time is not None else int(times.min())
        filter_end = end_time if end_time is not None else int(times.max()) + 1
        mask = (times >= filter_start) & (times < filter_end)
        return ch_data[mask]

    def build_multi_channel_time_index(
        self,
        engine: Any,
        run_id: str,
        data_name: str,
        data: list[np.ndarray],
        time_field: str | None,
        endtime_field: str | None,
        force_rebuild: bool,
        time_domain: str,
    ) -> dict[str, Any]:
        indices = []
        stats = {}
        n_channels = len(data)
        self.ctx.logger.info("Building time index for %s with %s channels", data_name, n_channels)
        for ch_idx, ch_data in enumerate(data):
            if ch_data is None or len(ch_data) == 0:
                self.ctx.logger.warning("Channel %s is empty, skipping", ch_idx)
                continue
            if not isinstance(ch_data, np.ndarray) or ch_data.dtype.names is None:
                self.ctx.logger.warning("Channel %s is not a structured array, skipping", ch_idx)
                continue
            resolved_time_field, derived_time_values = self.resolve_time_axis(
                ch_data,
                f"{data_name}_ch{ch_idx}",
                time_domain,
                time_field=time_field,
            )
            index_name = f"{data_name}_ch{ch_idx}"
            engine.build_index(
                run_id,
                index_name,
                ch_data,
                resolved_time_field,
                endtime_field,
                force_rebuild,
                time_values=derived_time_values,
            )
            index = engine.get_index(run_id, index_name)
            if index:
                indices.append(index_name)
                stats[index_name] = {
                    "channel": ch_idx,
                    "n_records": index.n_records,
                    "time_range": (index.min_time, index.max_time),
                    "build_time": index.build_time,
                }
        if not hasattr(self.ctx, "_multi_channel_indices"):
            self.ctx._multi_channel_indices = {}
        self.ctx._multi_channel_indices[(run_id, data_name)] = {
            "n_channels": n_channels,
            "channel_indices": indices,
        }
        self.ctx.logger.info(
            "Built %s channel indices for %s, total records: %s",
            len(indices),
            data_name,
            sum(s["n_records"] for s in stats.values()),
        )
        return {
            "type": "multi_channel",
            "n_channels": n_channels,
            "indices": indices,
            "stats": stats,
        }

    def set_epoch(self, run_id: str, epoch: datetime | float | str, time_unit: str = "ns") -> None:
        from waveform_analysis.core.foundation.time_conversion import EpochInfo
        from waveform_analysis.utils.formats.base import TimestampUnit

        unit_map = {
            "ps": TimestampUnit.PICOSECONDS,
            "ns": TimestampUnit.NANOSECONDS,
            "us": TimestampUnit.MICROSECONDS,
            "ms": TimestampUnit.MILLISECONDS,
            "s": TimestampUnit.SECONDS,
        }
        ts_unit = unit_map.get(time_unit.lower(), TimestampUnit.NANOSECONDS)
        if isinstance(epoch, datetime):
            epoch_info = EpochInfo.from_datetime(epoch, source="manual", time_unit=ts_unit)
        elif isinstance(epoch, int | float):
            epoch_info = EpochInfo.from_timestamp(float(epoch), source="manual", time_unit=ts_unit)
        elif isinstance(epoch, str):
            dt = datetime.fromisoformat(epoch.replace("Z", "+00:00"))
            epoch_info = EpochInfo.from_datetime(dt, source="manual", time_unit=ts_unit)
        else:
            raise TypeError(f"不支持的 epoch 类型: {type(epoch)}")
        self.ctx._epoch_cache[run_id] = epoch_info
        self.ctx.logger.info("Set epoch for %s: %s", run_id, epoch_info)

    def get_epoch(self, run_id: str) -> Any | None:
        return self.ctx._epoch_cache.get(run_id)

    def auto_extract_epoch(
        self,
        run_id: str,
        strategy: str | None = None,
        file_paths: list[str] | None = None,
    ) -> Any:
        from waveform_analysis.core.foundation.time_conversion import EpochExtractor

        if file_paths is None:
            try:
                raw_files = self.ctx.get_data(run_id, "raw_files")
                if raw_files is not None and len(raw_files) > 0:
                    if isinstance(raw_files[0], list):
                        file_paths = [f for ch_files in raw_files for f in ch_files]
                    else:
                        file_paths = list(raw_files)
            except Exception as e:
                self.ctx.logger.warning("无法获取 raw_files: %s", e)
        if not file_paths:
            raise ValueError(
                f"无法提取 epoch：未找到数据文件。请确保 run '{run_id}' 有 raw_files 数据，或手动提供 file_paths 参数。"
            )
        if strategy is None:
            strategy = self.ctx.config.get("epoch_extraction_strategy", "auto")
        extractor = EpochExtractor(filename_patterns=self.ctx.config.get("epoch_filename_patterns"))
        epoch_info = extractor.auto_extract(file_paths=file_paths, strategy=strategy)
        self.ctx._epoch_cache[run_id] = epoch_info
        self.ctx.logger.info("Auto-extracted epoch for %s: %s", run_id, epoch_info)
        return epoch_info

    def get_data_time_range_absolute(
        self,
        run_id: str,
        data_name: str,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        time_field: str | None = None,
        endtime_field: str | None = None,
        auto_build_index: bool = True,
        channel: int | HardwareChannel | tuple[int, int] | str | None = None,
        auto_extract_epoch: bool = True,
        time_domain: str = "system_ns",
    ) -> np.ndarray | list[np.ndarray]:
        from waveform_analysis.core.foundation.time_conversion import TimeConverter

        epoch_info = self.get_epoch(run_id)
        if epoch_info is None:
            if auto_extract_epoch and self.ctx.config.get("auto_extract_epoch", True):
                try:
                    epoch_info = self.auto_extract_epoch(run_id, strategy=None)
                except ValueError as e:
                    raise ValueError(
                        f"无法使用绝对时间查询：{e}\n请使用 ctx.set_epoch('{run_id}', epoch) 手动设置 epoch。"
                    ) from e
            else:
                raise ValueError(
                    f"无法使用绝对时间查询：run '{run_id}' 未设置 epoch。\n"
                    f"请使用 ctx.set_epoch() 或 ctx.auto_extract_epoch() 设置 epoch。"
                )
        converter = TimeConverter(epoch_info)
        start_rel, end_rel = converter.convert_time_range(start_dt, end_dt)
        domain = self.normalize_time_domain(time_domain)
        source_unit = getattr(getattr(epoch_info, "time_unit", None), "value", "ns")
        target_unit = "ns" if domain == self.ctx._TIME_DOMAIN_SYSTEM_NS else "ps"
        if source_unit != target_unit:
            from waveform_analysis.core.compat import convert_time

            if start_rel is not None:
                start_rel = int(round(convert_time(float(start_rel), source_unit, target_unit)))
            if end_rel is not None:
                end_rel = int(round(convert_time(float(end_rel), source_unit, target_unit)))
        return self.time_range(
            run_id=run_id,
            data_name=data_name,
            start_time=start_rel,
            end_time=end_rel,
            time_field=time_field,
            endtime_field=endtime_field,
            auto_build_index=auto_build_index,
            channel=channel,
            time_domain=domain,
        )
