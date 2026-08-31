"""Machine-readable import and public-surface contracts for the pre-facade tree.

The snapshot intentionally records public names, signatures, and compatibility
identity.  It does not record the current eager module side effects: those are
implementation details that later lazy-import stages are allowed to improve.
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest

CONTRACT_PATH = Path(__file__).with_name("import_topology_contract.json")

pytestmark = pytest.mark.contract


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _fresh_surface(module_name: str) -> dict:
    code = f"""
import importlib
import json
module = importlib.import_module({module_name!r})
print(json.dumps({{
    "all": getattr(module, "__all__", None),
    "dir_public": sorted(name for name in dir(module) if not name.startswith("_")),
}}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_root_core_plugin_utils_and_cli_surfaces_match_snapshot():
    contract = _contract()
    for module_name, expected in contract["surfaces"].items():
        observed = _fresh_surface(module_name)
        expected_all = expected["all"]
        additions = expected.get("allowed_additions_after_facade", [])
        expected_dir = set(
            expected["dir_contains"] if "dir_contains" in expected else expected["dir_public"]
        )
        if additions and observed["all"] == expected_all + additions:
            expected_dir.update(additions)
        else:
            assert observed["all"] == expected_all, module_name

        assert expected_dir <= set(observed["dir_public"]), module_name


def test_selected_public_signatures_match_snapshot():
    observed = {}
    for qualified_name in _contract()["signatures"]:
        module_name, attribute = qualified_name.rsplit(".", 1)
        value = getattr(importlib.import_module(module_name), attribute)
        observed[qualified_name] = str(inspect.signature(value))
    assert observed == _contract()["signatures"]


def test_exception_types_and_messages_match_snapshot(tmp_path):
    contract = _contract()["exceptions"]

    from waveform_analysis.acquisition.io import parse_and_stack_files
    from waveform_analysis.analysis.sampling import adaptive_sample_count
    from waveform_analysis.core.plugins.plugin_sets import get_plugin_set
    from waveform_analysis.core.plugins.profiles import get_profile

    fixture = tmp_path / "RUN_CH0_0.CSV"
    fixture.write_text("meta\nheader\n0;0;100;0;0;0;0;1;2\n", encoding="utf-8")
    calls = {
        "adaptive_sample_count_negative": lambda: adaptive_sample_count(-1),
        "parse_and_stack_files_invalid_engine": lambda: parse_and_stack_files(
            [str(fixture)], engine="invalid"
        ),
        "get_profile_unknown": lambda: get_profile("missing"),
        "get_plugin_set_unknown": lambda: get_plugin_set("missing"),
    }
    for name, call in calls.items():
        with pytest.raises(Exception) as caught:
            call()
        assert type(caught.value).__name__ == contract[name]["type"]
        assert str(caught.value) == contract[name]["message"]


def test_legacy_registries_and_objects_are_identity_preserving():
    contract = _contract()
    for left_name, right_name, attribute in contract["identity_pairs"]:
        left = importlib.import_module(left_name)
        right = importlib.import_module(right_name)
        assert left is right, (left_name, right_name)
        assert getattr(left, attribute) is getattr(right, attribute), attribute

    for left_name, right_name, attribute in contract["registry_identity_pairs"]:
        left = importlib.import_module(left_name)
        right = importlib.import_module(right_name)
        assert getattr(left, attribute) is getattr(right, attribute), attribute


def test_profiles_plugin_sets_and_standard_plugins_are_stable():
    contract = _contract()
    from waveform_analysis.core.plugins import builtin, plugin_sets, profiles

    expected_profiles = contract["profiles"]
    assert list(profiles.PROFILES) == expected_profiles["registry_keys"]
    assert profiles.PROFILES["cpu"] is profiles.cpu_default
    assert profiles.PROFILES["cpu_default"] is profiles.cpu_default
    assert profiles.PROFILES["streaming"] is profiles.streaming_default
    assert profiles.PROFILES["streaming_default"] is profiles.streaming_default
    assert profiles.PROFILES["jax"] is profiles.jax_accel
    assert profiles.PROFILES["jax_accel"] is profiles.jax_accel
    for alias, target in expected_profiles["aliases"].items():
        assert profiles.PROFILES[alias] is profiles.PROFILES[target]

    expected_sets = contract["plugin_sets"]
    assert list(plugin_sets.PLUGIN_SETS) == expected_sets["registry_keys"]
    assert expected_sets["factory_names"] == [
        f"plugins_{name}"
        for name in ("io", "waveform", "hit", "peaks", "basic_features", "tabular", "events")
    ]
    for name in expected_sets["registry_keys"]:
        factory_name = f"plugins_{name}"
        assert plugin_sets.PLUGIN_SETS[name] is getattr(plugin_sets, factory_name)

    expected_provides = contract["standard_plugins_provides"]
    provides = [plugin.provides for plugin in builtin.standard_plugins]
    assert provides == expected_provides
    assert (
        builtin.standard_plugins
        is importlib.import_module("waveform_analysis.core.plugins.builtin.cpu").standard_plugins
    )


def test_lazy_names_are_cached_and_unknown_names_raise():
    for module_name, name, canonical_module_name, canonical_name in _contract()["lazy"]:
        module = importlib.import_module(module_name)
        assert name not in vars(module)
        assert name in dir(module)
        value = getattr(module, name)
        canonical = getattr(importlib.import_module(canonical_module_name), canonical_name)
        assert value is canonical
        assert vars(module)[name] is value

    for module_name in (
        "waveform_analysis",
        "waveform_analysis.core.plugins",
        "waveform_analysis.utils",
    ):
        module = importlib.import_module(module_name)
        unknown_name = "__definitely_not_a_public_export__"
        with pytest.raises(AttributeError):
            getattr(module, unknown_name)


def test_cli_monkeypatch_points_remain_available(monkeypatch):
    cli = importlib.import_module("waveform_analysis.cli")
    for name in _contract()["cli_patch_points"]:
        marker = object()
        monkeypatch.setattr(cli, name, marker)
        assert getattr(cli, name) is marker


def test_canonical_and_legacy_imports_work_in_both_orders():
    for legacy_name, canonical_name, attribute in _contract()["import_order_pairs"]:
        for first, second in ((legacy_name, canonical_name), (canonical_name, legacy_name)):
            code = f"""
import importlib
first = importlib.import_module({first!r})
second = importlib.import_module({second!r})
assert first is second
assert getattr(first, {attribute!r}) is getattr(second, {attribute!r})
"""
            subprocess.run(
                [sys.executable, "-c", code],
                check=True,
                capture_output=True,
                text=True,
            )
