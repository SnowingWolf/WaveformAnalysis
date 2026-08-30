"""Canonical visualization APIs for dashboards, waveforms, lineage, and statistics."""

from importlib import import_module

__all__ = [
    "render_position_dashboard",
    "render_position_dashboard_2d",
    "render_position_dashboard_with_2d_hist",
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
    "render_position_dashboard": (".dashboard", "render_position_dashboard"),
    "render_position_dashboard_2d": (".dashboard_2d", "render_position_dashboard_2d"),
    "render_position_dashboard_with_2d_hist": (
        ".dashboard_2d_hist_layout",
        "render_position_dashboard_with_2d_hist",
    ),
    "plot_lineage_labview": (".lineage_visualizer", "plot_lineage_labview"),
    "plot_lineage_plotly": (".lineage_visualizer", "plot_lineage_plotly"),
    "plot_waveforms": (".waveform_visualizer", "plot_waveforms"),
    "plot_peak_channels_with_sum": (
        ".waveform_visualizer",
        "plot_peak_channels_with_sum",
    ),
    "create_peak_plotter": (".waveform_visualizer", "create_peak_plotter"),
    "corner_hist": (".statistical_plots", "corner_hist"),
    "plot_1d_cut_on_corner": (".statistical_plots", "plot_1d_cut_on_corner"),
    "plot_2d_cut_on_corner": (".statistical_plots", "plot_2d_cut_on_corner"),
    "save_figures_pdf": (".pdf_export", "save_figures_pdf"),
}


def __getattr__(name: str):
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        value = getattr(import_module(module_name, __name__), attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(_LAZY_ATTRS))
