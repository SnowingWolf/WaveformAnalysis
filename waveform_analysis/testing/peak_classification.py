"""Opt-in experimental peak-classification plugin for integration tests.

This module is intentionally outside the builtin plugin bundles and is not
included in the default profiles.  Register it explicitly with
``allow_override=True`` when testing the height/area and negative-rise rules
against the production ``peak_classification`` contract.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.peak_classification import (
    LABEL_S1,
    LABEL_S1_S2,
    LABEL_S2,
    PeakClassificationPlugin,
)
from waveform_analysis.core.plugins.core.base import Option

HEIGHT_PER_AREA_ADC_CUT = 0.04
NEGATIVE_RISE_S1_S2_HEIGHT_MIN_ADC = 3e4
NEGATIVE_RISE_TIME_10_50_CUT_NS = 1e2
NEGATIVE_RISE_AREA_CUT_PE = 1e3
ADC_PER_PE = 155.0


class HeightAreaLinePeakClassificationPlugin(PeakClassificationPlugin):
    """Apply the experimental height/area and negative-rise overrides.

    The plugin preserves the builtin output dtype and ``provides`` name, so
    downstream consumers can be exercised unchanged after explicit override.
    Peaks strictly above ``height / area_ADC`` are forced to S1.  Existing
    S1_S2 labels are first merged into S2.  For negative ``rise_time`` rows,
    the strict height, rise-time, and area boundaries below are then applied
    in order.  Equality rows retain the preceding line-rule result.
    """

    provides = "peak_classification"
    depends_on = ["peaks"]
    version = "1.5.0.dev2"
    description = "Experimental peak classification with height/area and negative-rise overrides."
    options = {
        **PeakClassificationPlugin.options,
        "height_per_area_adc_cut": Option(
            default=HEIGHT_PER_AREA_ADC_CUT,
            type=float,
            help=(
                "Peaks with height / area_ADC strictly above this line are forced to S1; "
                "S1_S2 peaks below it are merged into S2."
            ),
            min_value=0.0,
        ),
        "negative_rise_s1_s2_height_min_adc": Option(
            default=NEGATIVE_RISE_S1_S2_HEIGHT_MIN_ADC,
            type=float,
            help=(
                "Peaks with height strictly above this value and rise_time < 0 "
                "are forced to S1_S2 after the height/area override."
            ),
            min_value=0.0,
        ),
    }

    @staticmethod
    def apply_line_override(
        peaks: np.ndarray,
        classification: np.ndarray,
        threshold: float,
        negative_rise_height_min_adc: float = NEGATIVE_RISE_S1_S2_HEIGHT_MIN_ADC,
        *,
        inclusive: bool = False,
        negative_rise_time_10_50_cut_ns: float = NEGATIVE_RISE_TIME_10_50_CUT_NS,
        negative_rise_area_cut_pe: float = NEGATIVE_RISE_AREA_CUT_PE,
        adc_per_pe: float = ADC_PER_PE,
    ) -> np.ndarray:
        """Return a copy with the line and negative-rise rules applied."""

        if len(peaks) != len(classification) or not np.array_equal(
            peaks["peak_id"], classification["peak_id"]
        ):
            raise ValueError("peaks and peak_classification must be aligned by peak_id")

        result = classification.copy()
        area_adc = np.asarray(peaks["area"], dtype=np.float64)
        height_adc = np.asarray(peaks["height"], dtype=np.float64)
        rise_time = np.asarray(peaks["rise_time"], dtype=np.float64)
        rise_time_10_50 = np.asarray(peaks["rise_time_10_50"], dtype=np.float64)
        area_pe = area_adc / adc_per_pe

        ratio = np.full(len(peaks), np.nan, dtype=np.float64)
        np.divide(height_adc, area_adc, out=ratio, where=area_adc > 0)
        passes_threshold = ratio >= threshold if inclusive else ratio > threshold
        above_line = (
            np.isfinite(area_adc) & np.isfinite(height_adc) & (area_adc > 0) & passes_threshold
        )

        negative_rise = np.isfinite(rise_time) & (rise_time < 0)
        finite_negative_features = (
            negative_rise
            & np.isfinite(height_adc)
            & np.isfinite(rise_time_10_50)
            & np.isfinite(area_pe)
        )
        high_height = finite_negative_features & (height_adc > negative_rise_height_min_adc)
        low_height = finite_negative_features & (height_adc < negative_rise_height_min_adc)
        fast_rise = low_height & (rise_time_10_50 < negative_rise_time_10_50_cut_ns)
        slow_rise = low_height & (rise_time_10_50 > negative_rise_time_10_50_cut_ns)
        slow_small = slow_rise & (area_pe < negative_rise_area_cut_pe)
        slow_large = slow_rise & (area_pe > negative_rise_area_cut_pe)

        # Precedence matches the validated notebook rule: merge S1_S2 first,
        # then apply the line rule and finally the negative-rise categories.
        result["label"][result["label"] == LABEL_S1_S2] = LABEL_S2
        result["label"][above_line] = LABEL_S1
        result["label"][high_height] = LABEL_S1_S2
        result["label"][fast_rise] = LABEL_S1
        result["label"][slow_small] = LABEL_S2
        result["label"][slow_large] = LABEL_S2
        return result

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        peaks = context.get_data(run_id, "peaks")
        classification = super().compute(context, run_id, **kwargs)
        threshold = context.get_config(self, "height_per_area_adc_cut")
        negative_rise_height_min_adc = context.get_config(
            self, "negative_rise_s1_s2_height_min_adc"
        )
        return self.apply_line_override(
            peaks,
            classification,
            threshold,
            negative_rise_height_min_adc,
        )


__all__ = [
    "ADC_PER_PE",
    "HEIGHT_PER_AREA_ADC_CUT",
    "NEGATIVE_RISE_AREA_CUT_PE",
    "NEGATIVE_RISE_S1_S2_HEIGHT_MIN_ADC",
    "NEGATIVE_RISE_TIME_10_50_CUT_NS",
    "HeightAreaLinePeakClassificationPlugin",
]
