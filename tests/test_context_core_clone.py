import numpy as np
import pytest

from tests.utils import MockPlugin
from waveform_analysis.core.context import Context


def test_context_clone_basic(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)
    ctx.set_config({"test_key": "test_value"})

    cloned = ctx.clone()

    assert "mock_data" in cloned._plugins
    assert cloned.config.get("test_key") == "test_value"
    assert cloned.storage_dir == ctx.storage_dir


def test_context_clone_config_independence(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)
    ctx.set_config({"shared_key": "original"})

    cloned = ctx.clone()
    cloned.set_config({"shared_key": "modified"})

    assert ctx.config.get("shared_key") == "original"
    assert cloned.config.get("shared_key") == "modified"


def test_context_clone_empty_results(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)

    ctx.get_data("run1", "mock_data")
    assert ("run1", "mock_data") in ctx._results

    cloned = ctx.clone()

    assert ("run1", "mock_data") not in cloned._results


def test_context_get_plugin_valid(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)

    plugin = ctx.get_plugin("mock_data")

    assert plugin is not None
    assert plugin.provides == "mock_data"
    assert isinstance(plugin, MockPlugin)


def test_context_get_plugin_invalid(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)

    with pytest.raises(KeyError, match="Plugin 'nonexistent' is not registered"):
        ctx.get_plugin("nonexistent")


def test_context_get_plugin_modify_attributes(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)

    plugin = ctx.get_plugin("mock_data")
    plugin.save_when = "always"

    assert ctx._plugins["mock_data"].save_when == "always"
