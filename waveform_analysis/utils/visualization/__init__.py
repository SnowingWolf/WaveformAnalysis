"""可视化模块 - 血缘关系、波形和统计图表。"""

# 延迟导入以避免循环依赖
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


def __getattr__(name: str):
    """懒加载导入，避免循环依赖"""
    if name == "plot_lineage_labview":
        from .lineage_visualizer import plot_lineage_labview

        return plot_lineage_labview
    elif name == "plot_lineage_plotly":
        from .lineage_visualizer import plot_lineage_plotly

        return plot_lineage_plotly
    elif name == "plot_waveforms":
        from .waveform_visualizer import plot_waveforms

        return plot_waveforms
    elif name == "plot_peak_channels_with_sum":
        from .waveform_visualizer import plot_peak_channels_with_sum

        return plot_peak_channels_with_sum
    elif name == "create_peak_plotter":
        from .waveform_visualizer import create_peak_plotter

        return create_peak_plotter
    elif name == "corner_hist":
        from .statistical_plots import corner_hist

        return corner_hist
    elif name == "plot_1d_cut_on_corner":
        from .statistical_plots import plot_1d_cut_on_corner

        return plot_1d_cut_on_corner
    elif name == "plot_2d_cut_on_corner":
        from .statistical_plots import plot_2d_cut_on_corner

        return plot_2d_cut_on_corner
    elif name == "save_figures_pdf":
        from .pdf_export import save_figures_pdf

        return save_figures_pdf
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
