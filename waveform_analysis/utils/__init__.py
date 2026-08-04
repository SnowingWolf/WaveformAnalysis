"""
Utils module - 工具函数
"""

from importlib import import_module

__all__ = [
    "DAQRun",
    "DAQAnalyzer",
    "get_raw_files",
    "get_waveforms",
    "get_waveforms_generator",
    "filter_events_by_function",
    "filter_coincidence_events",
    "extract_channel_attributes",
    "plot_records_waveforms",
    "plot_lineage_labview",
    "plot_lineage_plotly",
    "plot_waveforms",
    "plot_peak_channels_with_sum",
    "create_peak_plotter",
    "save_figures_pdf",
    "corner_hist",
    "plot_1d_cut_on_corner",
    "plot_2d_cut_on_corner",
    "get_merged_indices_for_peak",
    "get_hit_indices_for_merged",
    "get_hits_for_merged",
    "get_hits_for_peak",
    "build_peak_to_merged_lookup",
    "build_merged_to_hit_lookup",
    "S1S2PairAccessor",
    "PeakChannelAccessor",
]

_LAZY_ATTRS: dict[str, tuple[str, str | None]] = {
    "DAQRun": (".daq", "DAQRun"),
    "DAQAnalyzer": (".daq", "DAQAnalyzer"),
    "get_raw_files": ("waveform_analysis.core.processing.loader", "get_raw_files"),
    "get_waveforms": ("waveform_analysis.core.processing.loader", "get_waveforms"),
    "get_waveforms_generator": (
        "waveform_analysis.core.processing.loader",
        "get_waveforms_generator",
    ),
    "filter_events_by_function": (".event_filters", "filter_events_by_function"),
    "filter_coincidence_events": (".event_filters", "filter_coincidence_events"),
    "extract_channel_attributes": (".event_filters", "extract_channel_attributes"),
    "parse_files_generator": (".io", "parse_files_generator"),
    "plot_records_waveforms": (".preview", "plot_records_waveforms"),
    "plot_lineage_labview": (".visualization", "plot_lineage_labview"),
    "plot_lineage_plotly": (".visualization", "plot_lineage_plotly"),
    "plot_waveforms": (".visualization", "plot_waveforms"),
    "plot_peak_channels_with_sum": (".visualization", "plot_peak_channels_with_sum"),
    "create_peak_plotter": (".visualization", "create_peak_plotter"),
    "save_figures_pdf": (".visualization", "save_figures_pdf"),
    "corner_hist": (".visualization.statistical_plots", "corner_hist"),
    "plot_1d_cut_on_corner": (".visualization.statistical_plots", "plot_1d_cut_on_corner"),
    "plot_2d_cut_on_corner": (".visualization.statistical_plots", "plot_2d_cut_on_corner"),
    "get_merged_indices_for_peak": (".query_helpers", "get_merged_indices_for_peak"),
    "get_hit_indices_for_merged": (".query_helpers", "get_hit_indices_for_merged"),
    "get_hits_for_merged": (".query_helpers", "get_hits_for_merged"),
    "get_hits_for_peak": (".query_helpers", "get_hits_for_peak"),
    "build_peak_to_merged_lookup": (".query_helpers", "build_peak_to_merged_lookup"),
    "build_merged_to_hit_lookup": (".query_helpers", "build_merged_to_hit_lookup"),
    "S1S2PairAccessor": (".s1_s2_pair_accessor", "S1S2PairAccessor"),
    "PeakChannelAccessor": (".peak_channel_accessor", "PeakChannelAccessor"),
}


def __getattr__(name: str):
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        module = import_module(module_name, __name__)
        value = getattr(module, attr_name) if attr_name else module
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(_LAZY_ATTRS))
