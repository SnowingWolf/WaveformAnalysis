"""Compatibility facade for the split waveform renderer implementation."""

from importlib import import_module

_PUBLIC_NAMES = {
    "plot_waveforms",
    "plot_peak_channels_with_sum",
    "create_peak_plotter",
    "create_interactive_browser",
}
_PRIVATE_NAMES = {"_plot_peak_channels_with_sum_impl"}
__all__ = [  # noqa: F822
    "plot_waveforms",
    "plot_peak_channels_with_sum",
    "create_peak_plotter",
]


def __getattr__(name: str):
    if name in _PUBLIC_NAMES or name in _PRIVATE_NAMES:
        value = getattr(
            import_module("waveform_analysis.visualization.waveforms.renderer"),
            name,
        )
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(globals()) | _PUBLIC_NAMES | _PRIVATE_NAMES)
