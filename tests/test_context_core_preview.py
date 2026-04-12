import numpy as np
import pytest

from tests.utils import DependentPlugin, MockPlugin
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin


def test_context_preview_execution_basic(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)
    ctx.register(DependentPlugin)

    result = ctx.preview_execution("run1", "dependent_data")

    assert result["target"] == "dependent_data"
    assert result["run_id"] == "run1"
    assert "execution_plan" in result
    assert "mock_data" in result["execution_plan"]
    assert "dependent_data" in result["execution_plan"]


def test_context_preview_execution_cache_status(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)

    result = ctx.preview_execution("run1", "mock_data", show_cache=True)
    assert result["cache_status"]["mock_data"]["needs_compute"] is True

    ctx.get_data("run1", "mock_data")
    result = ctx.preview_execution("run1", "mock_data", show_cache=True)
    assert result["cache_status"]["mock_data"]["in_memory"] is True


def test_context_preview_execution_invalid_data(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)

    with pytest.raises(ValueError, match="数据类型 'nonexistent' 未注册"):
        ctx.preview_execution("run1", "nonexistent")


def test_context_preview_execution_verbose_levels(tmp_path, capsys):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)
    ctx.register(DependentPlugin)

    ctx.preview_execution("run1", "dependent_data", verbose=0)
    out0 = capsys.readouterr().out

    ctx.preview_execution("run1", "dependent_data", verbose=2)
    out2 = capsys.readouterr().out

    assert len(out2) >= len(out0)


def test_context_visualization_smoke(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))

    class SimplePlugin(Plugin):
        provides = "data"

        def compute(self, context, run_id):
            return np.array([1])

    ctx.register(SimplePlugin)
    ctx.show_config()
    ctx.plot_lineage("data", kind="labview")
    ctx.plot_lineage("data", kind="mermaid")
