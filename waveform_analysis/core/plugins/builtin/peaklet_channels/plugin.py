"""peaklet_channels bundle - provides 'peaklet_channels'。"""

from typing import Any

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

    counts = np.zeros(len(peaklets), dtype=np.int64)
    for row in components:
        peaklet_id = int(row["peak_id"])
        if not 0 <= peaklet_id < len(peaklets):
            raise ValueError(
                "peaklet_channels found peaklet_components row with out-of-range "
                f"peak_id={peaklet_id}"
            )
        counts[peaklet_id] += 1

    expected = peaklets["component_count"].astype(np.int64, copy=False)
    if not np.array_equal(counts, expected):
        raise ValueError("peaklet_channels found peaklet_components inconsistent with peaklets")


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
    version = "2.0.0"
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

        out = self._compute_channels(
            peaklets=peaklets,
            components=components,
            features=features,
            peaklet_features=peaklet_features,
            validate=False,
        )
        if len(out) == 0:
            self._validate_and_fill_fractions(out, peaklets, peaklet_features)
            return out

        merged = context.get_data(run_id, "hit_merged")
        component_hits = context.get_data(run_id, "hit_merged_components")
        hits = context.get_data(run_id, "hit_threshold")
        if not all(isinstance(value, np.ndarray) for value in (merged, component_hits, hits)):
            raise ValueError("peaklet_channels requires structured hit reconstruction products")
        loaded = load_wave_input(context, self, run_id)
        if not loaded.spec.is_records or loaded.records is None or loaded.wave_pool is None:
            raise ValueError("peaklet_channels currently supports wave_source='records' only")

        self._replace_with_waveform_features(
            out=out,
            components=components,
            features=features,
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
        components: np.ndarray,
        features: np.ndarray,
        merged: np.ndarray,
        component_hits: np.ndarray,
        hits: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
        clip_negative_signal: bool,
    ) -> None:
        """Replace aggregate features with canonical per-channel waveform features."""
        record_lookup = RecordLookup(records)
        merged_to_hits: dict[int, list[int]] = {}
        for row in component_hits:
            merged_to_hits.setdefault(int(row["merged_index"]), []).append(int(row["hit_index"]))

        for out_row in out:
            peaklet_id = int(out_row["peaklet_id"])
            board = int(out_row["board"])
            channel = int(out_row["channel"])
            component_rows = components[components["peak_id"] == peaklet_id]
            merged_indices = [
                int(row["merged_index"])
                for row in component_rows
                if int(merged[int(row["merged_index"])]["board"]) == board
                and int(merged[int(row["merged_index"])]["channel"]) == channel
            ]
            segments: list[dict[str, Any]] = []
            for merged_index in merged_indices:
                merged_row = merged[merged_index]
                sample_start = int(merged_row["sample_start"])
                sample_end = int(merged_row["sample_end"])
                is_single = (
                    bool(merged_row["is_single_record"])
                    if "is_single_record" in merged.dtype.names
                    else sample_start >= 0 and sample_end > sample_start
                )
                windows = (
                    [(int(merged_row["record_id"]), sample_start, sample_end)]
                    if is_single and sample_start >= 0 and sample_end > sample_start
                    else [
                        (
                            int(hits[hit_index]["record_id"]),
                            int(hits[hit_index]["edge_start"]),
                            int(hits[hit_index]["edge_end"]),
                        )
                        for hit_index in merged_to_hits.get(merged_index, ())
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
    ) -> np.ndarray:
        if len(components) == 0 or len(features) == 0:
            return _empty_channels()

        valid_features = features[features["valid"] != 0]
        if len(valid_features) == 0:
            return _empty_channels()

        feature_merged = valid_features["merged_index"].astype(np.int64, copy=False)
        feature_order = np.argsort(feature_merged, kind="mergesort")
        sorted_merged = feature_merged[feature_order]

        component_merged = components["merged_index"].astype(np.int64, copy=False)
        matched_pos = np.searchsorted(sorted_merged, component_merged, side="right") - 1
        matched = matched_pos >= 0
        matched[matched] &= sorted_merged[matched_pos[matched]] == component_merged[matched]
        if not np.any(matched):
            return _empty_channels()

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

        if not validate:
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
        return out


__all__ = ["PEAKLET_CHANNELS_DTYPE", "PeakletChannelsPlugin"]
