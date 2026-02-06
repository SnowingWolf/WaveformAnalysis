# -*- coding: utf-8 -*-
"""
S1/S2 classifier plugin based on waveform width and basic features.

This plugin classifies each detected peak (from WaveformWidthPlugin) as:
- 0: Unknown
- 1: S1
- 2: S2

Classification uses configurable ranges on width/area/height derived from:
- waveform_width: total_width / total_width_samples per peak
- basic_features: area / height per event
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.core.base import Option, Plugin

export, __all__ = exporter()

LABEL_UNKNOWN = export(0, name="LABEL_UNKNOWN")
LABEL_S1 = export(1, name="LABEL_S1")
LABEL_S2 = export(2, name="LABEL_S2")

S1_S2_CLASSIFIER_DTYPE = np.dtype([
    ("label", "i1"),
    ("width_ns", "f4"),
    ("width_samples", "f4"),
    ("height", "f4"),
    ("area", "f4"),
    ("timestamp", "i8"),
    ("channel", "i2"),
    ("event_index", "i8"),
    ("peak_position", "i8"),
])


def _normalize_range(value: Optional[Tuple[Optional[float], Optional[float]]]):
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError("range must be a tuple of (min, max)")
    lo, hi = value
    if lo is None and hi is None:
        return None
    return (None if lo is None else float(lo), None if hi is None else float(hi))


def _value_in_range(
    value: float,
    bounds: Optional[Tuple[Optional[float], Optional[float]]],
) -> bool:
    if bounds is None:
        return True
    if value is None or np.isnan(value):
        return False
    lo, hi = bounds
    if lo is not None and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


@export
class S1S2ClassifierPlugin(Plugin):
    """Classify peaks into S1/S2/Unknown using waveform width + basic features."""

    provides = "s1_s2"
    depends_on = ["waveform_width", "basic_features"]
    description = "Classify peaks into S1/S2 using width/area/height ranges."
    version = "0.2.0"
    save_when = "always"
    output_dtype = S1_S2_CLASSIFIER_DTYPE

    options = {
        "width_unit": Option(
            default="ns",
            type=str,
            choices=["ns", "samples"],
            help="Width unit used for range checks: 'ns' or 'samples'.",
        ),
        "s1_width_range": Option(
            default=None,
            type=tuple,
            help="S1 width range (min, max) in width_unit. None disables.",
        ),
        "s2_width_range": Option(
            default=None,
            type=tuple,
            help="S2 width range (min, max) in width_unit. None disables.",
        ),
        "s1_area_range": Option(
            default=None,
            type=tuple,
            help="S1 area range (min, max). None disables.",
        ),
        "s2_area_range": Option(
            default=None,
            type=tuple,
            help="S2 area range (min, max). None disables.",
        ),
        "s1_height_range": Option(
            default=None,
            type=tuple,
            help="S1 height range (min, max). None disables.",
        ),
        "s2_height_range": Option(
            default=None,
            type=tuple,
            help="S2 height range (min, max). None disables.",
        ),
        "conflict_policy": Option(
            default="unknown",
            type=str,
            choices=["unknown", "prefer_s1", "prefer_s2"],
            help="How to resolve when both S1 and S2 criteria match.",
        ),
        "strict": Option(
            default=False,
            type=bool,
            help="Raise if no S1/S2 criteria are configured.",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        widths = context.get_data(run_id, "waveform_width")
        features = context.get_data(run_id, "basic_features")

        width_unit = context.get_config(self, "width_unit")

        s1_width_range = _normalize_range(context.get_config(self, "s1_width_range"))
        s2_width_range = _normalize_range(context.get_config(self, "s2_width_range"))
        s1_area_range = _normalize_range(context.get_config(self, "s1_area_range"))
        s2_area_range = _normalize_range(context.get_config(self, "s2_area_range"))
        s1_height_range = _normalize_range(context.get_config(self, "s1_height_range"))
        s2_height_range = _normalize_range(context.get_config(self, "s2_height_range"))

        conflict_policy = context.get_config(self, "conflict_policy")
        strict = context.get_config(self, "strict")

        s1_enabled = any(r is not None for r in (s1_width_range, s1_area_range, s1_height_range))
        s2_enabled = any(r is not None for r in (s2_width_range, s2_area_range, s2_height_range))
        if strict and not s1_enabled and not s2_enabled:
            raise ValueError("No S1/S2 criteria configured; set ranges or disable strict.")

        if not isinstance(widths, np.ndarray):
            raise ValueError("s1_s2 expects waveform_width as a single array")
        if not isinstance(features, np.ndarray):
            raise ValueError("s1_s2 expects basic_features as a single array")

        if len(widths) == 0:
            return np.zeros(0, dtype=S1_S2_CLASSIFIER_DTYPE)

        rows = []
        for peak in widths:
            width_ns = float(peak["total_width"])
            width_samples = float(peak["total_width_samples"])
            event_index = int(peak["event_index"])

            height = np.nan
            area = np.nan
            if 0 <= event_index < len(features):
                height = float(features["height"][event_index])
                area = float(features["area"][event_index])

            width_value = width_samples if width_unit == "samples" else width_ns

            s1_ok = s1_enabled and _value_in_range(width_value, s1_width_range)
            if s1_ok:
                s1_ok = s1_ok and _value_in_range(area, s1_area_range)
                s1_ok = s1_ok and _value_in_range(height, s1_height_range)

            s2_ok = s2_enabled and _value_in_range(width_value, s2_width_range)
            if s2_ok:
                s2_ok = s2_ok and _value_in_range(area, s2_area_range)
                s2_ok = s2_ok and _value_in_range(height, s2_height_range)

            if s1_ok and not s2_ok:
                label = LABEL_S1
            elif s2_ok and not s1_ok:
                label = LABEL_S2
            elif s1_ok and s2_ok:
                if conflict_policy == "prefer_s1":
                    label = LABEL_S1
                elif conflict_policy == "prefer_s2":
                    label = LABEL_S2
                else:
                    label = LABEL_UNKNOWN
            else:
                label = LABEL_UNKNOWN

            rows.append(
                (
                    int(label),
                    float(width_ns),
                    float(width_samples),
                    float(height),
                    float(area),
                    int(peak["timestamp"]),
                    int(peak["channel"]),
                    int(event_index),
                    int(peak["peak_position"]),
                )
            )

        if rows:
            return np.array(rows, dtype=S1_S2_CLASSIFIER_DTYPE)
        return np.zeros(0, dtype=S1_S2_CLASSIFIER_DTYPE)
