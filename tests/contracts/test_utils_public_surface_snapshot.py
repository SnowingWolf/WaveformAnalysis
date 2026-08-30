from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")


SNAPSHOT_PATH = Path(__file__).with_name("utils_public_surface.json")


def _snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_utils_public_names_and_private_patch_points_match_snapshot():
    # The current package initializes core before importing Accessor/lineage leaf modules.
    import waveform_analysis.core  # noqa: F401
    import waveform_analysis.utils as utils

    snapshot = _snapshot()
    assert utils.__all__ == snapshot["root_all"]
    assert set(snapshot["root_dir_extra"]).issubset(dir(utils))

    for module_name, expected_names in snapshot["module_public_names"].items():
        module = importlib.import_module(module_name)
        if hasattr(module, "__all__"):
            assert set(expected_names) == set(module.__all__), module_name
        for name in expected_names:
            assert getattr(module, name) is not None, f"{module_name}.{name}"

    for module_name, expected_names in snapshot["private_patch_points"].items():
        module = importlib.import_module(module_name)
        assert set(expected_names).issubset(dir(module)), module_name


def test_utils_key_signatures_match_snapshot():
    import waveform_analysis.core  # noqa: F401
    import waveform_analysis.utils as utils
    from waveform_analysis.utils.io import parse_and_stack_files

    values = {
        "DAQAnalyzer": utils.DAQAnalyzer,
        "DAQRun": utils.DAQRun,
        "PeakChannelAccessor": utils.PeakChannelAccessor,
        "S1S2PairAccessor": utils.S1S2PairAccessor,
        "adaptive_sample_count": utils.adaptive_sample_count,
        "parse_and_stack_files": parse_and_stack_files,
    }
    expected = _snapshot()["key_signatures"]
    assert {name: str(inspect.signature(value)) for name, value in values.items()} == expected


def test_utils_registry_and_representative_visual_structure_match_snapshot():
    import waveform_analysis.core  # noqa: F401
    from waveform_analysis.utils import corner_hist, formats

    expected = _snapshot()["registries"]
    assert formats.list_formats() == expected["formats"]
    assert formats.list_adapters() == expected["adapters"]
    assert type(formats.get_adapter("v1725")).__name__ == expected["v1725_adapter_type"]
    assert type(formats.get_adapter("vx2730")).__name__ == expected["vx2730_adapter_type"]

    fig, axes = corner_hist(
        [np.array([1.0, 2.0, 3.0]), np.array([2.0, 4.0, 8.0])],
        names=["x", "y"],
        bins=3,
        tight_layout=False,
    )
    try:
        assert axes.shape == (2, 2)
        assert axes[0, 0].get_xscale() == "linear"
        assert axes[1, 0].get_yscale() == "linear"
        assert len(axes[0, 1].lines) == 0
        assert len(axes[0, 1].patches) == 0
        assert len(axes[0, 1].collections) == 0
    finally:
        matplotlib.pyplot.close(fig)


def test_importing_utils_remains_lazy_in_fresh_process():
    code = """
import json
import sys
import waveform_analysis.utils as utils
print(json.dumps({
    "root_all": utils.__all__,
    "dir_has_parse_files_generator": "parse_files_generator" in dir(utils),
    "heavy": {
        name: name in sys.modules
        for name in ("pandas", "matplotlib", "polars", "pyarrow")
    },
    "sampling_loaded": "waveform_analysis.utils.sampling" in sys.modules,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)
    assert observed["root_all"] == _snapshot()["root_all"]
    assert observed["dir_has_parse_files_generator"] is True
    assert observed["heavy"] == {
        "pandas": False,
        "matplotlib": False,
        "polars": False,
        "pyarrow": False,
    }
    assert observed["sampling_loaded"] is False


def test_visualization_legacy_modules_share_canonical_implementations():
    pairs = (
        ("lineage_visualizer", "plot_lineage_labview"),
        ("statistical_plots", "corner_hist"),
        ("waveform_visualizer", "plot_waveforms"),
        ("pdf_export", "save_figures_pdf"),
    )
    for leaf, public_name in pairs:
        canonical = importlib.import_module(f"waveform_analysis.visualization.{leaf}")
        legacy = importlib.import_module(f"waveform_analysis.utils.visualization.{leaf}")
        assert legacy is canonical
        assert getattr(legacy, public_name) is getattr(canonical, public_name)
        assert canonical.__name__ == f"waveform_analysis.visualization.{leaf}"

    canonical_package = importlib.import_module("waveform_analysis.visualization")
    legacy_package = importlib.import_module("waveform_analysis.utils.visualization")
    for public_name in legacy_package.__all__:
        assert getattr(legacy_package, public_name) is getattr(canonical_package, public_name)


def test_visualization_responsibility_modules_preserve_public_objects():
    from waveform_analysis.visualization import (
        corner_hist,
        plot_lineage_labview,
        plot_lineage_plotly,
        plot_waveforms,
    )
    from waveform_analysis.visualization.lineage.matplotlib_renderer import (
        plot_lineage_labview as split_labview,
    )
    from waveform_analysis.visualization.lineage.plotly_renderer import (
        plot_lineage_plotly as split_plotly,
    )
    from waveform_analysis.visualization.statistical.corner import (
        corner_hist as split_corner_hist,
    )
    from waveform_analysis.visualization.waveforms.renderer import (
        plot_waveforms as split_plot_waveforms,
    )

    assert split_labview is plot_lineage_labview
    assert split_plotly is plot_lineage_plotly
    assert split_corner_hist is corner_hist
    assert split_plot_waveforms is plot_waveforms


def test_analysis_legacy_modules_share_canonical_implementations():
    pairs = (
        ("peak_channel_accessor", "peak_channel_accessor", "PeakChannelAccessor"),
        ("s1_s2_pair_accessor", "s1_s2_pair_accessor", "S1S2PairAccessor"),
        ("query_helpers", "queries", "get_hits_for_peak"),
        ("event_filters", "filters", "filter_events_by_function"),
        ("sampling", "sampling", "adaptive_stratified_sample_2d"),
        ("cache_tools", "cache_queries", "list_channel_cache_keys"),
    )
    for legacy_leaf, canonical_leaf, public_name in pairs:
        legacy = importlib.import_module(f"waveform_analysis.utils.{legacy_leaf}")
        canonical = importlib.import_module(f"waveform_analysis.analysis.{canonical_leaf}")
        assert legacy is canonical
        assert getattr(legacy, public_name) is getattr(canonical, public_name)

    import waveform_analysis.analysis as analysis
    import waveform_analysis.utils as utils

    for public_name in analysis.__all__:
        assert getattr(utils, public_name) is getattr(analysis, public_name)


def test_analysis_accessor_responsibility_modules_preserve_method_objects():
    from waveform_analysis.analysis import PeakChannelAccessor, S1S2PairAccessor
    from waveform_analysis.analysis.accessors.pairs.filters import mask
    from waveform_analysis.analysis.accessors.pairs.plotting import plot as pair_plot
    from waveform_analysis.analysis.accessors.peak.plotting import plot as peak_plot
    from waveform_analysis.analysis.accessors.peak.sum_waveforms import get_sum_waveform

    assert peak_plot is PeakChannelAccessor.plot
    assert get_sum_waveform is PeakChannelAccessor.get_sum_waveform
    assert mask is S1S2PairAccessor.mask
    assert pair_plot is S1S2PairAccessor.plot
