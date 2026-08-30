"""Channel selection, waveform preparation, and renderers."""

from importlib import import_module

__all__ = ["plot_waveforms", "plot_peak_channels_with_sum", "create_peak_plotter"]


def __getattr__(name: str):
    if name in __all__:
        return getattr(import_module(".renderer", __name__), name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
