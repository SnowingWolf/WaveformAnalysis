"""Contracts for the public, lazy ``waveform_analysis.plugins`` facade."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).parents[2]
BUILTIN_ROOT = REPO_ROOT / "waveform_analysis" / "core" / "plugins" / "builtin"


def _manifest_plugin_targets() -> dict[str, tuple[str, str]]:
    targets = {}
    for manifest in sorted(BUILTIN_ROOT.glob("*/manifest.yaml")):
        class_name = next(
            line.partition(":")[2].strip()
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.startswith("plugin_class:")
        )
        targets[class_name] = (
            f"waveform_analysis.core.plugins.builtin.{manifest.parent.name}.plugin",
            class_name,
        )
    return targets


def test_facade_map_matches_builtin_manifests_in_both_directions():
    facade = importlib.import_module("waveform_analysis.plugins")
    expected = _manifest_plugin_targets()
    actual = {
        name: target
        for name, target in facade._LAZY_EXPORTS.items()
        if name.endswith("Plugin")
        and target[0].startswith("waveform_analysis.core.plugins.builtin.")
    }

    assert actual == expected
    for name, (module_name, attribute_name) in expected.items():
        canonical_module = importlib.import_module(module_name)
        value = getattr(facade, name)
        canonical = getattr(canonical_module, attribute_name)
        assert value is canonical
        assert value.__module__ == module_name


def test_facade_exports_preserve_canonical_identity_and_signatures():
    facade = importlib.import_module("waveform_analysis.plugins")

    assert facade.__all__ == list(facade._LAZY_EXPORTS)
    assert {name for name in dir(facade) if not name.startswith("_")} == set(facade.__all__)
    for name, (module_name, attribute_name) in facade._LAZY_EXPORTS.items():
        canonical_module = importlib.import_module(module_name)
        value = getattr(facade, name)
        canonical = (
            canonical_module
            if attribute_name is None
            else getattr(canonical_module, attribute_name)
        )
        assert value is canonical, name
        if attribute_name is not None and callable(value):
            assert inspect.signature(value) == inspect.signature(canonical), name


def test_facade_import_does_not_load_core_or_scientific_modules():
    code = """
import sys
import waveform_analysis
assert "plugins" not in vars(waveform_analysis)
import waveform_analysis.plugins as facade
assert "Plugin" not in vars(facade)
assert "BasicFeaturesPlugin" not in vars(facade)
assert "profiles" not in vars(facade)
assert "sets" not in vars(facade)
for prefix in (
    "waveform_analysis.core",
    "numpy",
    "scipy",
    "pandas",
    "numba",
    "jax",
    "yaml",
):
    assert not any(
        module == prefix or module.startswith(prefix + ".")
        for module in sys.modules
    ), prefix
assert not any(
    module.startswith("waveform_analysis.core.plugins.builtin")
    for module in sys.modules
)
"""
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )


def test_root_adds_only_lazy_plugins_namespace():
    root = importlib.import_module("waveform_analysis")
    assert root.__all__[-1] == "plugins"
    assert "plugins" in dir(root)

    code = """
import waveform_analysis
assert waveform_analysis.__all__[-1] == "plugins"
assert "plugins" in dir(waveform_analysis)
assert "plugins" not in vars(waveform_analysis)
"""
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )


def test_facade_profiles_and_sets_are_identity_aliases_in_both_orders():
    facade = importlib.import_module("waveform_analysis.plugins")
    profiles = importlib.import_module("waveform_analysis.core.plugins.profiles")
    sets = importlib.import_module("waveform_analysis.core.plugins.plugin_sets")
    assert facade.profiles is profiles
    assert facade.sets is sets

    for first, second in (
        (
            "waveform_analysis.plugins.profiles",
            "waveform_analysis.core.plugins.profiles",
        ),
        (
            "waveform_analysis.plugins.sets",
            "waveform_analysis.core.plugins.plugin_sets",
        ),
    ):
        for first_name, second_name in ((first, second), (second, first)):
            code = f"""
import importlib
first = importlib.import_module({first_name!r})
second = importlib.import_module({second_name!r})
assert first is second
"""
            subprocess.run(
                [sys.executable, "-c", code],
                check=True,
                capture_output=True,
                text=True,
            )


def test_lazy_export_helper_caches_and_propagates_target_errors():
    from waveform_analysis._lazy_exports import resolve_lazy_attribute

    namespace = {"__name__": "tests.contract", "__package__": ""}
    value = resolve_lazy_attribute(
        "LazyExport",
        {"LazyExport": ("waveform_analysis._lazy_exports", "LazyExport")},
        namespace,
    )
    assert namespace["LazyExport"] is value

    with pytest.raises(ModuleNotFoundError):
        resolve_lazy_attribute(
            "missing",
            {"missing": ("waveform_analysis._missing_lazy_target", "value")},
            namespace,
        )
    with pytest.raises(AttributeError):
        resolve_lazy_attribute(
            "missing",
            {"missing": ("waveform_analysis._lazy_exports", "_missing")},
            namespace,
        )
