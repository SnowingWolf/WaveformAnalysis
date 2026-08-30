"""Backward-compatible lazy facade for :mod:`waveform_analysis.visualization`."""

from importlib import import_module

from waveform_analysis._module_aliases import register_module_aliases

_CANONICAL = "waveform_analysis.visualization"
register_module_aliases(
    {
        f"{__name__}.{child}": f"{_CANONICAL}.{child}"
        for child in (
            "_s1_s2_candidates",
            "lineage_visualizer",
            "pdf_export",
            "statistical_plots",
            "waveform_visualizer",
        )
    }
)

__all__ = [
    "plot_lineage_labview",
    "plot_lineage_plotly",
    "plot_waveforms",
    "plot_peak_channels_with_sum",
    "create_peak_plotter",
    "corner_hist",
    "plot_1d_cut_on_corner",
    "plot_2d_cut_on_corner",
    "save_figures_pdf",
]

_LAZY_ATTRS = {
    "plot_lineage_labview": ("lineage_visualizer", "plot_lineage_labview"),
    "plot_lineage_plotly": ("lineage_visualizer", "plot_lineage_plotly"),
    "plot_waveforms": ("waveform_visualizer", "plot_waveforms"),
    "plot_peak_channels_with_sum": (
        "waveform_visualizer",
        "plot_peak_channels_with_sum",
    ),
    "create_peak_plotter": ("waveform_visualizer", "create_peak_plotter"),
    "corner_hist": ("statistical_plots", "corner_hist"),
    "plot_1d_cut_on_corner": ("statistical_plots", "plot_1d_cut_on_corner"),
    "plot_2d_cut_on_corner": ("statistical_plots", "plot_2d_cut_on_corner"),
    "save_figures_pdf": ("pdf_export", "save_figures_pdf"),
}


def __getattr__(name: str):
    """Resolve legacy attributes from their canonical implementation modules."""
    try:
        module_name, attr_name = _LAZY_ATTRS[name]
    except KeyError as exc:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'") from exc
    return getattr(import_module(f"{_CANONICAL}.{module_name}"), attr_name)
