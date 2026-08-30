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
