"""Backward-compatible shim. Implementation moved to the per-plugin bundles.

- PeakletPlugin → :mod:`waveform_analysis.core.plugins.builtin.peaklets`
- PeakletComponentsPlugin → :mod:`waveform_analysis.core.plugins.builtin.peaklet_components`
- PeakletWaveformPlugin → :mod:`waveform_analysis.core.plugins.builtin.peaklet_waveforms`
- PeakletWaveformPoolPlugin → :mod:`waveform_analysis.core.plugins.builtin.peaklet_waveform_pool`
- PeakletFeaturesPlugin → :mod:`waveform_analysis.core.plugins.builtin.peaklet_features`
- PeakletChannelsPlugin → :mod:`waveform_analysis.core.plugins.builtin.peaklet_channels`
- PeaksPlugin → :mod:`waveform_analysis.core.plugins.builtin.peaks`
"""

from waveform_analysis.core.plugins.builtin.peaklet_channels import (
    PeakletChannelsPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklet_components import (
    PeakletComponentsPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklet_features import (
    PeakletFeaturesPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklet_waveform_pool import (
    PeakletWaveformPoolPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklet_waveforms import (
    PeakletWaveformPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklets import PEAKLET_DTYPE, PeakletPlugin
from waveform_analysis.core.plugins.builtin.peaklets._compute import (
    PEAKLET_COMPONENTS_DTYPE,
    PEAKLET_FEATURES_DTYPE,
    PEAKLET_WAVEFORMS_DTYPE,
    PEAKS_DTYPE,
    _build_hmc_csr,
    _build_peaklet_component_csr,
)
from waveform_analysis.core.plugins.builtin.peaks.plugin import PeaksPlugin

__all__ = [
    "PEAKLET_DTYPE",
    "PEAKLET_COMPONENTS_DTYPE",
    "PEAKLET_WAVEFORMS_DTYPE",
    "PEAKLET_FEATURES_DTYPE",
    "PEAKS_DTYPE",
    "PeakletPlugin",
    "PeakletComponentsPlugin",
    "PeakletWaveformPlugin",
    "PeakletWaveformPoolPlugin",
    "PeakletFeaturesPlugin",
    "PeakletChannelsPlugin",
    "PeaksPlugin",
]
