"""Per-channel contribution table for peaklets."""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.core.base import Plugin

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
    """Expand peaklets into per-board/channel contribution rows."""

    provides = "peaklet_channels"
    depends_on = ["peaklets", "peaklet_components", "hit_merged_features", "peaklet_features"]
    description = "Aggregate hit_merged_features into per-peaklet channel contribution rows."
    version = "1.0.1"
    output_dtype = PEAKLET_CHANNELS_DTYPE
    save_when = "always"

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

        return self._compute_channels(
            peaklets=peaklets,
            components=components,
            features=features,
            peaklet_features=peaklet_features,
        )

    def _compute_channels(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        features: np.ndarray,
        peaklet_features: np.ndarray,
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
        out["area_fraction"] = np.divide(
            out["area"],
            fraction_denominator,
            out=np.zeros(len(out), dtype=np.float32),
            where=fraction_denominator != 0.0,
        )
        return out


__all__ = ["PEAKLET_CHANNELS_DTYPE", "PeakletChannelsPlugin"]
