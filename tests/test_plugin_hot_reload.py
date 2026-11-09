"""Behavioral regressions for reloading plugin source files."""

import importlib
import os
from pathlib import Path
import runpy
import sys
import textwrap

import numpy as np
import pytest

from waveform_analysis.core.plugins.core.hot_reload import PluginHotReloader


def _plugin_source(version="1.0.0", value=1):
    return textwrap.dedent(
        f"""\
        from waveform_analysis.core.plugins.core.base import Plugin

        class AUnrelatedPlugin(Plugin):
            provides = "unrelated"

            def compute(self, context, run_id):
                return -1

        class WatchedPlugin(Plugin):
            provides = "watched"
            version = "{version}"

            def compute(self, context, run_id):
                return {value}

        class AlternatePlugin(Plugin):
            provides = "watched"
            version = "{version}"

            def compute(self, context, run_id):
                return {value} + 10
        """
    )


@pytest.fixture
def plugin_module(tmp_path, monkeypatch):
    package_name = "_wa_hot_reload_test"
    package_dir = tmp_path / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("")
    (package_dir / "helper.py").write_text("OFFSET = 10\n")
    path = package_dir / "plugin.py"
    path.write_text(_plugin_source())
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module(f"{package_name}.plugin")
    yield module, path
    for name in list(sys.modules):
        loaded_path = getattr(sys.modules[name], "__file__", None)
        if name == package_name or name.startswith(f"{package_name}.") or loaded_path == str(path):
            del sys.modules[name]


def _watch(context, module, *, plugin_class=None):
    context.register(module.WatchedPlugin)
    reloader = PluginHotReloader(context)
    reloader.watch_plugin("watched", plugin_class=plugin_class)
    return reloader


def test_reload_registers_new_source_even_with_valid_old_bytecode(context, plugin_module):
    module, path = plugin_module
    reloader = _watch(context, module)
    old_plugin = context._plugins["watched"]
    initial_stat = path.stat()
    assert Path(module.__cached__).exists()

    # An unchanged timestamp and size leave the old timestamp-based .pyc valid.
    path.write_text(_plugin_source(version="2.0.0", value=2))
    assert path.stat().st_size == initial_stat.st_size
    os.utime(path, ns=(initial_stat.st_atime_ns, initial_stat.st_mtime_ns))
    assert reloader.check_updates() == ["watched"]

    reloader.reload_plugin("watched")

    new_plugin = context._plugins["watched"]
    assert new_plugin is not old_plugin
    assert new_plugin.__class__ is not old_plugin.__class__
    assert new_plugin.__class__.__module__ == module.__name__
    assert new_plugin.version == "2.0.0"
    assert new_plugin.compute(context, "run") == 2
    assert sys.modules[module.__name__].WatchedPlugin is new_plugin.__class__
    assert reloader.check_updates() == []

    path.write_text(_plugin_source(version="3.0.0", value=3))
    reloader.reload_plugin("watched")
    assert context._plugins["watched"].compute(context, "run") == 3
    assert reloader.check_updates() == []


def test_reload_honors_explicit_class_selection(context, plugin_module):
    module, path = plugin_module
    reloader = _watch(context, module, plugin_class=module.AlternatePlugin)
    path.write_text(_plugin_source(version="2.0.0", value=2))

    reloader.reload_plugin("watched")

    plugin = context._plugins["watched"]
    assert plugin.__class__.__name__ == "AlternatePlugin"
    assert plugin.version == "2.0.0"
    assert plugin.compute(context, "run") == 12
    assert "unrelated" not in context._plugins


def test_reload_changes_results_through_context_data_access(context, plugin_module):
    module, path = plugin_module
    path.write_text("import numpy as np\n" + _plugin_source(value="np.array([1])"))
    module = importlib.reload(module)
    reloader = _watch(context, module)
    np.testing.assert_array_equal(context.get_data("run", "watched"), [1])

    path.write_text("import numpy as np\n" + _plugin_source(version="2.0.0", value="np.array([2])"))
    reloader.reload_plugin("watched")

    np.testing.assert_array_equal(context.get_data("run", "watched"), [2])


def test_reload_preserves_package_imports_and_module_identity(context, plugin_module):
    module, path = plugin_module
    reloader = _watch(context, module)
    source = (
        "from .helper import OFFSET\n"
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Settings:\n"
        "    offset: int = OFFSET\n" + _plugin_source(value="Settings().offset + 2")
    )
    path.write_text(source)

    reloader.reload_plugin("watched")

    assert context._plugins["watched"].compute(context, "run") == 12
    assert context._plugins["watched"].__class__.__module__ == module.__name__


def test_reload_acknowledges_only_the_source_that_was_loaded(context, plugin_module, monkeypatch):
    module, path = plugin_module
    reloader = _watch(context, module)
    path.write_text(_plugin_source(version="2.0.0", value=2))
    register = context.register

    def register_then_edit(*args, **kwargs):
        register(*args, **kwargs)
        path.write_text(_plugin_source(version="3.0.0", value=3))

    monkeypatch.setattr(context, "register", register_then_edit)
    reloader.reload_plugin("watched")

    assert context._plugins["watched"].version == "2.0.0"
    assert context._plugins["watched"].compute(context, "run") == 2
    assert reloader.check_updates() == ["watched"]


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("invalid syntax !!!\n", SyntaxError),
        ("raise RuntimeError('module failed')\n", RuntimeError),
        (_plugin_source().replace("class WatchedPlugin", "class RenamedPlugin"), AttributeError),
        (_plugin_source() + "\nWatchedPlugin = 1\n", TypeError),
        (_plugin_source().replace('provides = "watched"', 'provides = "renamed"'), ValueError),
    ],
    ids=["syntax-error", "module-error", "missing-class", "invalid-class", "changed-provides"],
)
def test_failed_reload_retains_plugin_module_and_pending_update(
    context, plugin_module, source, error
):
    module, path = plugin_module
    reloader = _watch(context, module)
    old_plugin = context._plugins["watched"]
    old_info = reloader.watched_plugins["watched"].copy()
    path.write_text(source)

    with pytest.raises(error):
        reloader.reload_plugin("watched")

    assert context._plugins == {"watched": old_plugin}
    assert sys.modules[module.__name__] is module
    assert reloader.watched_plugins["watched"] == old_info
    assert reloader.check_updates() == ["watched"]


def test_registration_error_leaves_update_pending(context, plugin_module, monkeypatch):
    module, path = plugin_module
    reloader = _watch(context, module)
    old_plugin = context._plugins["watched"]
    old_info = reloader.watched_plugins["watched"].copy()
    path.write_text(_plugin_source(version="2.0.0", value=2))

    def reject_registration(*args, **kwargs):
        raise RuntimeError("registration failed")

    monkeypatch.setattr(context, "register", reject_registration)
    with pytest.raises(RuntimeError, match="registration failed"):
        reloader.reload_plugin("watched")

    assert context._plugins["watched"] is old_plugin
    assert sys.modules[module.__name__] is module
    assert reloader.watched_plugins["watched"] == old_info
    assert reloader.check_updates() == ["watched"]


@pytest.mark.parametrize("module_name", ["__main__", "__mp_main__"])
def test_watch_rejects_main_entrypoint_without_reexecuting_it(context, tmp_path, module_name):
    path = tmp_path / "main_plugin.py"
    marker = tmp_path / "main_calls.txt"
    path.write_text(
        _plugin_source()
        + textwrap.dedent(
            """\
            from pathlib import Path
            from waveform_analysis.core.plugins.core.hot_reload import PluginHotReloader

            if __name__ in {"__main__", "__mp_main__"}:
                with Path(marker).open("a") as calls:
                    calls.write("entered\\n")
                context.register(WatchedPlugin)
                reloader = PluginHotReloader(context)
                reloader.watch_plugin("watched")
                reloader.reload_plugin("watched")
            """
        )
    )
    previous_module = sys.modules.get(module_name)

    with pytest.raises(ValueError, match="requires an importable plugin module"):
        runpy.run_path(
            str(path), run_name=module_name, init_globals={"context": context, "marker": marker}
        )

    assert marker.read_text() == "entered\n"
    assert sys.modules.get(module_name) is previous_module
    assert context._plugins["watched"].compute(context, "run") == 1
