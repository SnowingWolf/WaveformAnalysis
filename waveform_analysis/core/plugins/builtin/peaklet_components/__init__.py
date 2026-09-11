"""peaklet_components bundle - provides 'peaklet_components'。"""

from waveform_analysis.core.plugins.builtin.peaklet_components.plugin import PeakletComponentsPlugin
from waveform_analysis.core.plugins.builtin.peaklets._compute import PEAKLET_COMPONENTS_DTYPE

__all__ = ["PeakletComponentsPlugin", "PEAKLET_COMPONENTS_DTYPE"]
