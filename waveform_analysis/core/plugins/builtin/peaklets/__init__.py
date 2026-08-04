"""peaklets bundle - provides 'peaklets'。"""

from waveform_analysis.core.plugins.builtin.peaklets._compute import PEAKLET_DTYPE
from waveform_analysis.core.plugins.builtin.peaklets.plugin import PeakletPlugin

__all__ = ["PeakletPlugin", "PEAKLET_DTYPE"]
