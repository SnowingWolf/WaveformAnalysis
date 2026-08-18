"""peaklet_channels bundle - provides 'peaklet_channels'。"""

from typing import Any

import numba as nb
import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._record_utils import RecordLookup
from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    WAVE_SOURCE_RECORDS,
    load_wave_input,
    resolve_wave_input_spec,
)
from waveform_analysis.core.plugins.builtin.shared.waveform_merge import merge_waveform_segments
from waveform_analysis.core.plugins.core.base import Option, Plugin

PEAKLET_CHANNELS_DTYPE = np.dtype(
    [
        ("peaklet_id", "i8"),
        ("board", "i2"),
        ("channel", "i2"),
        ("area", "f4"),
        ("height", "f4"),
        ("n_hits", "i4"),
        ("area_fraction", "f4"),
    ]
)


def _empty_channels() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_CHANNELS_DTYPE)


def _validate_peaklet_components(peaklets: np.ndarray, components: np.ndarray) -> None:
    if "component_count" not in (peaklets.dtype.names or ()):
        return

    peaklet_ids = components["peak_id"].astype(np.int64, copy=False)
    invalid = (peaklet_ids < 0) | (peaklet_ids >= len(peaklets))
    if np.any(invalid):
        peaklet_id = int(peaklet_ids[np.flatnonzero(invalid)[0]])
        raise ValueError(
            "peaklet_channels found peaklet_components row with out-of-range "
            f"peak_id={peaklet_id}"
        )
    counts = np.bincount(peaklet_ids, minlength=len(peaklets)).astype(np.int64, copy=False)
    expected = peaklets["component_count"].astype(np.int64, copy=False)
    if not np.array_equal(counts, expected):
        raise ValueError("peaklet_channels found peaklet_components inconsistent with peaklets")


@nb.njit(cache=True, nogil=True, parallel=True)
def _mark_waveform_rebuild_groups_kernel(
    group_offsets,
    grouped_merged_indices,
    merged_sample_start,
    merged_sample_end,
    merged_time_start,
    merged_time_end,
    rebuild_groups,
):
    """Mark only channel groups whose aggregate features are insufficient.

    A single record-backed merged hit can be reused exactly.  Any multi-hit
    group is rebuilt from samples: adding quantized float32 feature areas is
    not bitwise equivalent to the canonical float64 waveform integral.
    """
    n_groups = len(group_offsets) - 1
    for group_index in nb.prange(n_groups):
        start = group_offsets[group_index]
        end = group_offsets[group_index + 1]
        if end <= start:
            rebuild_groups[group_index] = 1
            continue
        if end - start == 1:
            merged_index = grouped_merged_indices[start]
            rebuild_groups[group_index] = int(
                merged_sample_start[merged_index] < 0
                or merged_sample_end[merged_index] <= merged_sample_start[merged_index]
            )
            continue

        rebuild_groups[group_index] = 1


class PeakletChannelsPlugin(Plugin):
    """Reconstruct peaklets into deduplicated per-board/channel contribution rows."""

    provides = "peaklet_channels"
    lineage_virtual = True
    depends_on = [
        "peaklets",
        "peaklet_components",
        "hit_merged",
        "hit_merged_components",
        "hit_threshold",
        "hit_merged_features",
        "peaklet_features",
        "records",
        "wave_pool",
    ]
    description = "Reconstruct deduplicated per-peaklet channel waveform contributions."
    version = "2.0.1"
    output_dtype = PEAKLET_CHANNELS_DTYPE
    save_when = "always"

    options = {
        "wave_source": Option(
            default=WAVE_SOURCE_RECORDS,
            type=str,
            help="波形来源；peaklet_channels 当前正式支持 records。",
        ),
        "use_filtered": Option(
            default=False,
            type=bool,
            help="是否从 wave_pool_filtered 重建通道波形。",
        ),
        "clip_negative_signal": Option(
            default=False,
            type=bool,
            help="是否在通道波形合并与积分前把负采样裁剪为 0。",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        spec = resolve_wave_input_spec(context, self)
        if not spec.is_records:
            raise ValueError("peaklet_channels currently supports wave_source='records' only")
        return [
            "peaklets",
            "peaklet_components",
            "hit_merged",
            "hit_merged_components",
            "hit_threshold",
            "hit_merged_features",
            "peaklet_features",
            *spec.depends_on,
        ]

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        peaklets = context.get_data(run_id, "peaklets")
        if not isinstance(peaklets, np.ndarray):
            raise ValueError("peaklet_channels expects peaklets as a structured array")
        if len(peaklets) == 0:
            return _empty_channels()

        components = context.get_data(run_id, "peaklet_components")
        if not isinstance(components, np.ndarray):
            raise ValueError("peaklet_channels expects peaklet_components as a structured array")
        _validate_peaklet_components(peaklets, components)

        features = context.get_data(run_id, "hit_merged_features")
        if not isinstance(features, np.ndarray):
            raise ValueError("peaklet_channels expects hit_merged_features as a structured array")
        peaklet_features = context.get_data(run_id, "peaklet_features")
        if not isinstance(peaklet_features, np.ndarray):
            raise ValueError("peaklet_channels expects peaklet_features as a structured array")

        out, group_offsets, grouped_merged_indices = self._compute_channels(
            peaklets=peaklets,
            components=components,
            features=features,
            peaklet_features=peaklet_features,
            validate=False,
            return_groups=True,
        )
        if len(out) == 0:
            self._validate_and_fill_fractions(out, peaklets, peaklet_features)
            return out

        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("peaklet_channels requires hit_merged as a structured array")
        rebuild_groups = np.zeros(len(out), dtype=np.uint8)
        _mark_waveform_rebuild_groups_kernel(
            group_offsets,
            grouped_merged_indices,
            merged["sample_start"].astype(np.int64, copy=False),
            merged["sample_end"].astype(np.int64, copy=False),
            merged["time_start"].astype(np.int64, copy=False),
            merged["time_end"].astype(np.int64, copy=False),
            rebuild_groups,
        )
        if np.any(rebuild_groups):
            component_hits = context.get_data(run_id, "hit_merged_components")
            hits = context.get_data(run_id, "hit_threshold")
            if not all(isinstance(value, np.ndarray) for value in (component_hits, hits)):
                raise ValueError("peaklet_channels requires structured hit reconstruction products")
            loaded = load_wave_input(context, self, run_id)
            if not loaded.spec.is_records or loaded.records is None or loaded.wave_pool is None:
                raise ValueError("peaklet_channels currently supports wave_source='records' only")
            self._replace_with_waveform_features(
                out=out,
                group_offsets=group_offsets,
                grouped_merged_indices=grouped_merged_indices,
                rebuild_groups=rebuild_groups,
                merged=merged,
                component_hits=component_hits,
                hits=hits,
                records=loaded.records,
                wave_pool=loaded.wave_pool,
                clip_negative_signal=bool(context.get_config(self, "clip_negative_signal")),
            )
        self._validate_and_fill_fractions(out, peaklets, peaklet_features)
        return out

    @staticmethod
    def _signal(record: np.void, raw: np.ndarray, clip_negative_signal: bool) -> np.ndarray:
        polarity_value = record["polarity"] if "polarity" in record.dtype.names else "negative"
        polarity = (
            polarity_value.decode("utf-8")
            if isinstance(polarity_value, bytes)
            else str(polarity_value)
        )
        baseline = np.float32(record["baseline"])
        signal = raw.astype(np.float32, copy=False) - baseline
        if polarity != "positive":
            signal = -signal
        if clip_negative_signal:
            signal = np.maximum(signal, np.float32(0.0))
        return signal

    @classmethod
    def _replace_with_waveform_features(
        cls,
        *,
        out: np.ndarray,
        group_offsets: np.ndarray,
        grouped_merged_indices: np.ndarray,
        rebuild_groups: np.ndarray,
        merged: np.ndarray,
        component_hits: np.ndarray,
        hits: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
        clip_negative_signal: bool,
    ) -> None:
        """Rebuild only the channel groups that can contain shared samples."""
        record_lookup = RecordLookup(records)
        hit_indices = component_hits["hit_index"].astype(np.int64, copy=False)

        for group_index in np.flatnonzero(rebuild_groups):
            out_row = out[group_index]
            peaklet_id = int(out_row["peaklet_id"])
            board = int(out_row["board"])
            channel = int(out_row["channel"])
            group_start = int(group_offsets[group_index])
            group_end = int(group_offsets[group_index + 1])
            segments: list[dict[str, Any]] = []
            for grouped_index in range(group_start, group_end):
                merged_index = int(grouped_merged_indices[grouped_index])
                merged_row = merged[merged_index]
                sample_start = int(merged_row["sample_start"])
                sample_end = int(merged_row["sample_end"])
                is_single = (
                    bool(merged_row["is_single_record"])
                    if "is_single_record" in merged.dtype.names
                    else sample_start >= 0 and sample_end > sample_start
                )
                component_offset = int(merged_row["component_offset"])
                component_count = int(merged_row["component_count"])
                if (
                    component_count > 0
                    and component_offset >= 0
                    and component_offset + component_count <= len(hit_indices)
                    and np.all(
                        component_hits["merged_index"][
                            component_offset : component_offset + component_count
                        ]
                        == merged_index
                    )
                ):
                    merged_hit_indices = hit_indices[
                        component_offset : component_offset + component_count
                    ]
                else:
                    # Compatibility fallback for older/incomplete merged rows.
                    # Production rows use the O(1) CSR slice above.
                    merged_hit_indices = hit_indices[component_hits["merged_index"] == merged_index]
                windows = (
                    [(int(merged_row["record_id"]), sample_start, sample_end)]
                    if is_single and sample_start >= 0 and sample_end > sample_start
                    else [
                        (
                            int(hits[hit_index]["record_id"]),
                            int(hits[hit_index]["edge_start"]),
                            int(hits[hit_index]["edge_end"]),
                        )
                        for hit_index in merged_hit_indices
                    ]
                )
                for record_id, start, end in windows:
                    record_index = int(record_lookup.get_indices(np.array([record_id]))[0])
                    record = records[record_index]
                    clipped_start = max(0, start)
                    clipped_end = min(int(record["event_length"]), end)
                    if clipped_end <= clipped_start:
                        continue
                    offset = int(record["wave_offset"])
                    signal = cls._signal(
                        record,
                        wave_pool[offset + clipped_start : offset + clipped_end],
                        clip_negative_signal,
                    )
                    dt_ns = int(record["dt"])
                    dt_ps = dt_ns * 1000
                    abs_time_ps = (
                        int(record["timestamp"])
                        + np.arange(clipped_start, clipped_end, dtype=np.int64) * dt_ps
                    )
                    segments.append(
                        {
                            "waveform": signal,
                            "abs_time_ps": abs_time_ps,
                            "dt": dt_ns,
                            "board": board,
                            "channel": channel,
                            "record_id": record_id,
                            "merged_index": merged_index,
                        }
                    )

            channel_wave = merge_waveform_segments(
                segments,
                sum_channels=False,
                dense=False,
                context=(
                    f"peaklet_channels peaklet_id={peaklet_id}, board={board}, channel={channel}"
                ),
            )["waveform"]
            if len(channel_wave) == 0:
                raise ValueError(
                    "peaklet_channels could not reconstruct waveform for "
                    f"peaklet_id={peaklet_id}, board={board}, channel={channel}"
                )
            out_row["area"] = np.sum(channel_wave, dtype=np.float64)
            out_row["height"] = np.max(channel_wave)

    @staticmethod
    def _validate_and_fill_fractions(
        out: np.ndarray, peaklets: np.ndarray, peaklet_features: np.ndarray
    ) -> None:
        area_by_peaklet = np.zeros(len(peaklets), dtype=np.float64)
        feature_ids = peaklet_features["peak_id"].astype(np.int64, copy=False)
        valid_features = (feature_ids >= 0) & (feature_ids < len(peaklets))
        area_by_peaklet[feature_ids[valid_features]] = peaklet_features["area"][
            valid_features
        ].astype(np.float64, copy=False)
        out_ids = out["peaklet_id"].astype(np.int64, copy=False)
        valid_out = (out_ids >= 0) & (out_ids < len(peaklets))
        channel_sums = np.zeros(len(peaklets), dtype=np.float64)
        np.add.at(channel_sums, out_ids[valid_out], out["area"][valid_out])
        mismatch = ~np.isclose(channel_sums, area_by_peaklet, rtol=1e-5, atol=1e-3)
        if np.any(mismatch):
            peaklet_id = int(np.flatnonzero(mismatch)[0])
            raise ValueError(
                "peaklet_channels area conservation failed for "
                f"peaklet_id={peaklet_id}: channel_area={channel_sums[peaklet_id]} "
                f"!= peak_area={area_by_peaklet[peaklet_id]}"
            )
        denominators = area_by_peaklet[out_ids]
        out["area_fraction"] = np.divide(
            out["area"],
            denominators,
            out=np.zeros(len(out), dtype=np.float32),
            where=denominators != 0.0,
        )
        fraction_sums = np.zeros(len(peaklets), dtype=np.float64)
        np.add.at(fraction_sums, out_ids[valid_out], out["area_fraction"][valid_out])
        nonzero_area = area_by_peaklet != 0.0
        fraction_mismatch = nonzero_area & ~np.isclose(fraction_sums, 1.0, rtol=1e-5, atol=1e-3)
        if np.any(fraction_mismatch):
            peaklet_id = int(np.flatnonzero(fraction_mismatch)[0])
            raise ValueError(
                "peaklet_channels fraction conservation failed for "
                f"peaklet_id={peaklet_id}: fraction_sum={fraction_sums[peaklet_id]}"
            )

    def _compute_channels(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        features: np.ndarray,
        peaklet_features: np.ndarray,
        validate: bool = True,
        return_groups: bool = False,
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray, np.ndarray]:
        if len(components) == 0 or len(features) == 0:
            empty = _empty_channels()
            if return_groups:
                return empty, np.zeros(1, dtype=np.int64), np.zeros(0, dtype=np.int64)
            return empty

        valid_features = features[features["valid"] != 0]
        if len(valid_features) == 0:
            empty = _empty_channels()
            if return_groups:
                return empty, np.zeros(1, dtype=np.int64), np.zeros(0, dtype=np.int64)
            return empty

        feature_merged = valid_features["merged_index"].astype(np.int64, copy=False)
        feature_order = np.argsort(feature_merged, kind="mergesort")
        sorted_merged = feature_merged[feature_order]

        component_merged = components["merged_index"].astype(np.int64, copy=False)
        matched_pos = np.searchsorted(sorted_merged, component_merged, side="right") - 1
        matched = matched_pos >= 0
        matched[matched] &= sorted_merged[matched_pos[matched]] == component_merged[matched]
        if not np.any(matched):
            empty = _empty_channels()
            if return_groups:
                return empty, np.zeros(1, dtype=np.int64), np.zeros(0, dtype=np.int64)
            return empty

        matched_features = valid_features[feature_order[matched_pos[matched]]]
        peaklet_ids = components["peak_id"][matched].astype(np.int64, copy=False)
        boards = matched_features["board"].astype(np.int64, copy=False)
        channels = matched_features["channel"].astype(np.int64, copy=False)

        group_order = np.lexsort((channels, boards, peaklet_ids))
        peaklet_ids = peaklet_ids[group_order]
        boards = boards[group_order]
        channels = channels[group_order]
        areas = matched_features["area"][group_order].astype(np.float32, copy=False)
        heights = matched_features["height"][group_order].astype(np.float32, copy=False)
        n_hits = matched_features["n_hits"][group_order].astype(np.int32, copy=False)
        grouped_merged_indices = component_merged[matched][group_order]

        group_start_mask = np.r_[
            True,
            (peaklet_ids[1:] != peaklet_ids[:-1])
            | (boards[1:] != boards[:-1])
            | (channels[1:] != channels[:-1]),
        ]
        group_starts = np.flatnonzero(group_start_mask)

        out = np.zeros(len(group_starts), dtype=PEAKLET_CHANNELS_DTYPE)
        out["peaklet_id"] = peaklet_ids[group_starts]
        out["board"] = boards[group_starts]
        out["channel"] = channels[group_starts]
        out["area"] = np.add.reduceat(areas, group_starts).astype(np.float32, copy=False)
        out["height"] = np.maximum.reduceat(heights, group_starts).astype(np.float32, copy=False)
        out["n_hits"] = np.add.reduceat(n_hits, group_starts).astype(np.int32, copy=False)

        group_offsets = np.empty(len(group_starts) + 1, dtype=np.int64)
        group_offsets[:-1] = group_starts
        group_offsets[-1] = len(grouped_merged_indices)

        if not validate:
            if return_groups:
                return out, group_offsets, grouped_merged_indices
            return out

        area_by_peaklet = np.zeros(len(peaklets), dtype=np.float32)
        feature_peaklet_ids = peaklet_features["peak_id"].astype(np.int64, copy=False)
        in_range = (feature_peaklet_ids >= 0) & (feature_peaklet_ids < len(peaklets))
        area_by_peaklet[feature_peaklet_ids[in_range]] = peaklet_features["area"][in_range].astype(
            np.float32, copy=False
        )
        out_peaklet_ids = out["peaklet_id"].astype(np.int64, copy=False)
        fraction_denominator = np.zeros(len(out), dtype=np.float32)
        valid_out_peaklets = (out_peaklet_ids >= 0) & (out_peaklet_ids < len(area_by_peaklet))
        fraction_denominator[valid_out_peaklets] = area_by_peaklet[
            out_peaklet_ids[valid_out_peaklets]
        ]

        channel_area_by_peaklet = np.zeros(len(peaklets), dtype=np.float64)
        np.add.at(
            channel_area_by_peaklet,
            out_peaklet_ids[valid_out_peaklets],
            out["area"][valid_out_peaklets].astype(np.float64, copy=False),
        )
        feature_area_by_peaklet = area_by_peaklet.astype(np.float64, copy=False)
        mismatch = ~np.isclose(
            channel_area_by_peaklet,
            feature_area_by_peaklet,
            rtol=1e-5,
            atol=1e-3,
        )
        if np.any(mismatch):
            peaklet_id = int(np.flatnonzero(mismatch)[0])
            raise ValueError(
                "peaklet_channels area conservation failed for "
                f"peaklet_id={peaklet_id}: channel_area="
                f"{channel_area_by_peaklet[peaklet_id]} != peak_area="
                f"{feature_area_by_peaklet[peaklet_id]}"
            )
        out["area_fraction"] = np.divide(
            out["area"],
            fraction_denominator,
            out=np.zeros(len(out), dtype=np.float32),
            where=fraction_denominator != 0.0,
        )
        fraction_sums = np.zeros(len(peaklets), dtype=np.float64)
        np.add.at(
            fraction_sums,
            out_peaklet_ids[valid_out_peaklets],
            out["area_fraction"][valid_out_peaklets],
        )
        nonzero_area = feature_area_by_peaklet != 0.0
        fraction_mismatch = nonzero_area & ~np.isclose(fraction_sums, 1.0, rtol=1e-5, atol=1e-3)
        if np.any(fraction_mismatch):
            peaklet_id = int(np.flatnonzero(fraction_mismatch)[0])
            raise ValueError(
                "peaklet_channels fraction conservation failed for "
                f"peaklet_id={peaklet_id}: fraction_sum={fraction_sums[peaklet_id]}"
            )
        if return_groups:
            return out, group_offsets, grouped_merged_indices
        return out


__all__ = ["PEAKLET_CHANNELS_DTYPE", "PeakletChannelsPlugin"]
