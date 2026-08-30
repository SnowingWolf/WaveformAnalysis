from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
import numpy as np
import pytest

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


def test_utils_exception_dtype_daq_and_parsing_contracts(tmp_path):
    from waveform_analysis.core.plugins.builtin.position_reconstruction import (
        POSITION_RECONSTRUCTION_DTYPE,
    )
    from waveform_analysis.utils import adaptive_sample_count
    from waveform_analysis.utils.daq import DAQAnalyzer
    from waveform_analysis.utils.io import parse_and_stack_files
    from waveform_analysis.utils.peak_channel_accessor import (
        PeakChannelDataUnavailableError,
        WaveformOverlapConflictError,
    )
    from waveform_analysis.utils.s1_s2_pair_accessor import WaveformNotFoundError

    snapshot = _snapshot()
    exception_types = {
        "PeakChannelDataUnavailableError": PeakChannelDataUnavailableError,
        "WaveformOverlapConflictError": WaveformOverlapConflictError,
        "WaveformNotFoundError": WaveformNotFoundError,
    }
    for name, exception_type in exception_types.items():
        assert exception_type.__base__.__name__ == snapshot["exception_contracts"][name]

    for key, call in (("adaptive_sample_count_negative", lambda: adaptive_sample_count(-1)),):
        expected_type, expected_message = snapshot["exception_contracts"][key]
        with pytest.raises(Exception) as caught:
            call()
        assert type(caught.value).__name__ == expected_type
        assert str(caught.value) == expected_message

    expected_dtype = snapshot["structured_dtypes"]["position_reconstruction"]
    assert [list(field) for field in POSITION_RECONSTRUCTION_DTYPE.descr] == expected_dtype

    raw_dir = tmp_path / "DAQ" / "run" / "RAW"
    raw_dir.mkdir(parents=True)
    fixture_path = raw_dir / "RUN_CH0_0.CSV"
    fixture_path.write_text(
        "meta\nheader\n0;0;100;0;0;0;0;1;2\n",
        encoding="utf-8",
    )
    expected_type, expected_message = snapshot["exception_contracts"][
        "parse_and_stack_files_invalid_engine"
    ]
    with pytest.raises(Exception) as caught:
        parse_and_stack_files([str(fixture_path)], engine="invalid")
    assert type(caught.value).__name__ == expected_type
    assert str(caught.value) == expected_message

    parsed = parse_and_stack_files([str(fixture_path)], engine="pandas", n_jobs=1)
    expected_parse = snapshot["parse_fixture"]
    assert list(parsed.shape) == expected_parse["shape"]
    assert parsed.dtype.str == expected_parse["dtype"]
    assert parsed.tolist() == expected_parse["values"]

    analyzer = DAQAnalyzer(tmp_path / "DAQ")
    analyzer.scan_all_runs()
    run = analyzer.get_run("run")
    assert run is not None
    observed_run = run.to_dict()
    expected_run = snapshot["daq_fixture"]
    assert {key: observed_run[key] for key in expected_run} == expected_run


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


def test_visualization_legacy_modules_share_canonical_implementations(monkeypatch):
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
    assert legacy_package is canonical_package
    for public_name in legacy_package.__all__:
        assert getattr(legacy_package, public_name) is getattr(canonical_package, public_name)
    marker = object()
    monkeypatch.setattr(legacy_package, "plot_waveforms", marker)
    assert canonical_package.plot_waveforms is marker


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


@pytest.mark.parametrize(
    ("module_name", "public_name"),
    (
        (
            "waveform_analysis.visualization.lineage.matplotlib_renderer",
            "plot_lineage_labview",
        ),
        (
            "waveform_analysis.visualization.lineage.plotly_renderer",
            "plot_lineage_plotly",
        ),
        (
            "waveform_analysis.visualization.lineage",
            "plot_lineage_labview",
        ),
        (
            "waveform_analysis.visualization.waveforms.renderer",
            "plot_waveforms",
        ),
        (
            "waveform_analysis.acquisition.readers.orchestrator",
            "parse_and_stack_files",
        ),
    ),
)
def test_split_entry_points_import_directly_in_fresh_process(module_name, public_name):
    code = f"""
import importlib
import inspect
module = importlib.import_module({module_name!r})
value = getattr(module, {public_name!r})
print(value.__name__)
print(inspect.signature(value))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    expected_name = public_name
    if public_name.startswith("plot_lineage_"):
        expected_name = f"_{public_name}_impl"
    assert result.stdout.splitlines()[0] == expected_name


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


def test_acquisition_legacy_modules_share_registries_and_implementations():
    canonical_formats = importlib.import_module("waveform_analysis.acquisition.formats")
    legacy_formats = importlib.import_module("waveform_analysis.utils.formats")
    assert legacy_formats is canonical_formats

    canonical_registry = importlib.import_module("waveform_analysis.acquisition.formats.registry")
    legacy_registry = importlib.import_module("waveform_analysis.utils.formats.registry")
    canonical_adapter = importlib.import_module("waveform_analysis.acquisition.formats.adapter")
    legacy_adapter = importlib.import_module("waveform_analysis.utils.formats.adapter")
    assert legacy_registry is canonical_registry
    assert legacy_adapter is canonical_adapter
    assert legacy_registry._FORMAT_REGISTRY is canonical_registry._FORMAT_REGISTRY
    assert legacy_registry._FORMAT_SPECS is canonical_registry._FORMAT_SPECS
    assert legacy_adapter._ADAPTER_REGISTRY is canonical_adapter._ADAPTER_REGISTRY

    formats_before = canonical_formats.list_formats()
    adapters_before = canonical_formats.list_adapters()
    canonical_formats.ensure_builtin_formats_registered()
    canonical_formats.ensure_builtin_formats_registered()
    assert canonical_formats.list_formats() == formats_before
    assert canonical_formats.list_adapters() == adapters_before

    canonical_daq = importlib.import_module("waveform_analysis.acquisition.daq")
    legacy_daq = importlib.import_module("waveform_analysis.utils.daq")
    canonical_io = importlib.import_module("waveform_analysis.acquisition.io")
    legacy_io = importlib.import_module("waveform_analysis.utils.io")
    assert legacy_daq is canonical_daq
    assert legacy_io is canonical_io
    assert legacy_daq.DAQAnalyzer is canonical_daq.DAQAnalyzer
    assert legacy_io.parse_and_stack_files is canonical_io.parse_and_stack_files
    assert legacy_io.parse_files_generator is canonical_io.parse_files_generator


def test_acquisition_responsibility_modules_share_facade_objects():
    canonical_io = importlib.import_module("waveform_analysis.acquisition.io")
    base_csv = importlib.import_module("waveform_analysis.acquisition.readers.base_csv")
    orchestrator = importlib.import_module("waveform_analysis.acquisition.readers.orchestrator")
    polars_backend = importlib.import_module("waveform_analysis.acquisition.readers.polars_backend")
    pyarrow_backend = importlib.import_module(
        "waveform_analysis.acquisition.readers.pyarrow_backend"
    )
    assert base_csv.parse_files_generator is canonical_io.parse_files_generator
    assert orchestrator.parse_and_stack_files is canonical_io.parse_and_stack_files
    assert polars_backend.read_csv_polars is canonical_io._read_csv_polars
    assert polars_backend.read_files_polars is canonical_io._read_files_polars
    assert pyarrow_backend.read_csv_pyarrow is canonical_io._read_csv_pyarrow
    assert pyarrow_backend.read_files_pyarrow is canonical_io._read_files_pyarrow

    daq_models = importlib.import_module("waveform_analysis.acquisition.daq.models")
    daq_service = importlib.import_module("waveform_analysis.acquisition.daq.service")
    daq_discovery = importlib.import_module("waveform_analysis.acquisition.daq.discovery")
    daq_presentation = importlib.import_module("waveform_analysis.acquisition.daq.presentation")
    canonical_daq_run = importlib.import_module("waveform_analysis.acquisition.daq.daq_run")
    canonical_daq_analyzer = importlib.import_module(
        "waveform_analysis.acquisition.daq.daq_analyzer"
    )
    assert daq_models.DAQRun is canonical_daq_run.DAQRun
    assert daq_service.DAQAnalyzer is canonical_daq_analyzer.DAQAnalyzer
    assert daq_discovery.scan_all_runs is canonical_daq_analyzer.DAQAnalyzer.scan_all_runs
    assert daq_discovery.scan_default is canonical_daq_run.DAQRun._scan_default
    assert daq_presentation.display_overview is canonical_daq_analyzer.DAQAnalyzer.display_overview


def test_unreachable_legacy_doc_generator_entry_is_absent():
    cli = importlib.import_module("waveform_analysis.documentation.cli")
    assert not hasattr(cli, "generate_docs")
