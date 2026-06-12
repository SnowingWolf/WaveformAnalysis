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
    version = "1.0.0"
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

        features_by_merged = {
            int(row["merged_index"]): row for row in features if int(row["valid"]) != 0
        }
        area_by_peaklet = {int(row["peak_id"]): float(row["area"]) for row in peaklet_features}
        grouped: dict[tuple[int, int, int], dict[str, float | int]] = {}

        for component in components:
            peaklet_id = int(component["peak_id"])
            merged_index = int(component["merged_index"])
            feature = features_by_merged.get(merged_index)
            if feature is None:
                continue

            key = (peaklet_id, int(feature["board"]), int(feature["channel"]))
            values = grouped.setdefault(
                key,
                {
                    "area": 0.0,
                    "height": 0.0,
                    "n_hits": 0,
                },
            )
            values["area"] = float(values["area"]) + float(feature["area"])
            values["height"] = max(float(values["height"]), float(feature["height"]))
            values["n_hits"] = int(values["n_hits"]) + int(feature["n_hits"])

        rows: list[tuple[int, int, int, float, float, int, float]] = []
        for key in sorted(grouped):
            peaklet_id, board, channel = key
            values = grouped[key]
            channel_area = float(values["area"])
            peaklet_area = area_by_peaklet.get(peaklet_id, 0.0)
            area_fraction = channel_area / peaklet_area if peaklet_area != 0.0 else 0.0
            rows.append(
                (
                    peaklet_id,
                    board,
                    channel,
                    channel_area,
                    float(values["height"]),
                    int(values["n_hits"]),
                    area_fraction,
                )
            )

        return np.array(rows, dtype=PEAKLET_CHANNELS_DTYPE) if rows else _empty_channels()


__all__ = ["PEAKLET_CHANNELS_DTYPE", "PeakletChannelsPlugin"]
