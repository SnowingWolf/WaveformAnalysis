"""Compatibility wrapper for the canonical waveform visualizer module."""

from waveform_analysis.utils.visualization.waveform_visualizer import (
    create_interactive_browser,
    plot_waveforms,
)

__all__ = ["plot_waveforms", "create_interactive_browser"]
