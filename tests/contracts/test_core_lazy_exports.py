"""Contracts for the lazy core-domain package initializers."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).parents[2]

AGGREGATORS = (
    "waveform_analysis",
    "waveform_analysis.core",
    "waveform_analysis.core.foundation",
    "waveform_analysis.core.hardware",
    "waveform_analysis.core.config",
    "waveform_analysis.core.execution",
    "waveform_analysis.core.data",
    "waveform_analysis.core.storage",
    "waveform_analysis.core.processing",
)


def _resolve_target(package, target):
    module_name, attribute_name = target
    module = importlib.import_module(module_name, package.__package__)
    return module if attribute_name is None else getattr(module, attribute_name)


def test_public_names_are_lazy_exports_in_stable_order():
    for module_name in AGGREGATORS:
        package = importlib.import_module(module_name)
        assert all(name in package._LAZY_EXPORTS for name in package.__all__), module_name
        if module_name != "waveform_analysis":
            assert [
                name for name in package._LAZY_EXPORTS if name in package.__all__
            ] == package.__all__, module_name
        assert all(name in dir(package) for name in package.__all__), module_name


def test_exports_resolve_to_canonical_leaf_identity_and_are_cached():
    for module_name in AGGREGATORS:
        package = importlib.import_module(module_name)
        for name in package.__all__:
            # Import the canonical module first to cover the order in which a
            # child initializer can otherwise shadow a package-level export.
            expected = _resolve_target(package, package._LAZY_EXPORTS[name])
            value = getattr(package, name)
            assert value is expected, (module_name, name)
            assert vars(package)[name] is value, (module_name, name)


def test_root_version_is_resolved_only_on_first_access():
    code = """
import importlib
import sys
import waveform_analysis

assert "__version__" not in vars(waveform_analysis)
assert "importlib.metadata" not in sys.modules
assert waveform_analysis.__author__ == "Your Name"

version = waveform_analysis.__version__
assert version == importlib.import_module("waveform_analysis._version").__version__
assert vars(waveform_analysis)["__version__"] == version
assert "importlib.metadata" in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True, cwd=REPO_ROOT)


@pytest.mark.parametrize("module_name", AGGREGATORS)
def test_fresh_aggregator_import_does_not_fan_out(module_name):
    code = f"""
import importlib
import sys

importlib.import_module({module_name!r})
for prefix in (
    "importlib.metadata",
    "numpy",
    "scipy",
    "pandas",
    "numba",
    "jax",
    "yaml",
):
    assert not any(
        name == prefix or name.startswith(prefix + ".")
        for name in sys.modules
    ), prefix
"""
    subprocess.run([sys.executable, "-c", code], check=True, cwd=REPO_ROOT)


@pytest.mark.parametrize(
    ("package_name", "leaf_name", "export_name"),
    (
        (
            "waveform_analysis.core.foundation",
            "waveform_analysis.core.foundation.exceptions",
            "PluginError",
        ),
        (
            "waveform_analysis.core.hardware",
            "waveform_analysis.core.hardware.channel",
            "HardwareChannel",
        ),
        (
            "waveform_analysis.core.config",
            "waveform_analysis.core.config.adapter_info",
            "AdapterInfo",
        ),
        (
            "waveform_analysis.core.execution",
            "waveform_analysis.core.execution.manager",
            "ExecutorManager",
        ),
        (
            "waveform_analysis.core.data",
            "waveform_analysis.core.data.records_view",
            "records_view",
        ),
        (
            "waveform_analysis.core.storage",
            "waveform_analysis.core.storage.cache",
            "CacheManager",
        ),
        (
            "waveform_analysis.core.processing",
            "waveform_analysis.core.processing.dtypes",
            "ST_WAVEFORM_DTYPE",
        ),
    ),
)
def test_package_and_leaf_import_orders_preserve_identity(package_name, leaf_name, export_name):
    for first, second in ((package_name, leaf_name), (leaf_name, package_name)):
        code = f"""
import importlib

importlib.import_module({first!r})
importlib.import_module({second!r})
package = importlib.import_module({package_name!r})
leaf = importlib.import_module({leaf_name!r})
assert getattr(package, {export_name!r}) is getattr(leaf, {export_name!r})
"""
        subprocess.run([sys.executable, "-c", code], check=True, cwd=REPO_ROOT)


def test_executor_timeout_config_and_storage_singletons_are_unchanged():
    execution = importlib.import_module("waveform_analysis.core.execution")
    manager = importlib.import_module("waveform_analysis.core.execution.manager")
    timeout = importlib.import_module("waveform_analysis.core.execution.timeout")
    config = importlib.import_module("waveform_analysis.core.execution.config")
    storage = importlib.import_module("waveform_analysis.core.storage")
    compression = importlib.import_module("waveform_analysis.core.storage.compression")
    integrity = importlib.import_module("waveform_analysis.core.storage.integrity")

    assert execution.get_executor_manager() is manager.get_executor_manager()
    assert execution.get_timeout_manager() is timeout.get_timeout_manager()
    assert execution.EXECUTOR_CONFIGS is config.EXECUTOR_CONFIGS
    assert storage.get_compression_manager() is compression.get_compression_manager()
    assert storage.get_integrity_checker() is integrity.get_integrity_checker()


def test_processing_waveform_compat_exports_use_canonical_leaf():
    processing = importlib.import_module("waveform_analysis.core.processing")
    canonical = importlib.import_module(
        "waveform_analysis.core.plugins.builtin.st_waveforms.plugin"
    )
    assert processing.WaveformStruct is canonical.WaveformStruct
    assert processing.WaveformStructConfig is canonical.WaveformStructConfig


@pytest.mark.parametrize("module_name", AGGREGATORS)
def test_unknown_attribute_message_is_preserved(module_name):
    package = importlib.import_module(module_name)
    missing_name = "__definitely_not_a_public_export__"
    with pytest.raises(AttributeError) as caught:
        getattr(package, missing_name)
    assert str(caught.value) == (f"module '{module_name}' has no attribute " f"'{missing_name}'")
