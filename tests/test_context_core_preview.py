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


def test_context_preview_execution_shows_global_execution_config(tmp_path, capsys):
    ctx = Context(
        storage_dir=str(tmp_path),
        config={"enable_plugin_parallelism": True, "max_parallel_workers": 4},
    )
    ctx.register(MockPlugin)

    result = ctx.preview_execution("run1", "mock_data", show_config=True)
    out = capsys.readouterr().out

    assert result["global_execution_config"] == {
        "enable_plugin_parallelism": True,
        "max_parallel_workers": 4,
    }
    assert "全局执行配置" in out
    assert "enable_plugin_parallelism = True" in out
    assert "max_parallel_workers = 4" in out


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


def test_plot_lineage_can_hide_virtual_plugins_without_changing_default(tmp_path, monkeypatch):
    ctx = Context(storage_dir=str(tmp_path))

    class SourcePlugin(Plugin):
        provides = "source"

        def compute(self, context, run_id):
            return np.array([1])

    class VirtualPlugin(Plugin):
        provides = "virtual"
        depends_on = ("source",)
        lineage_virtual = True

        def compute(self, source):
            return source

    class TargetPlugin(Plugin):
        provides = "target"
        depends_on = ("virtual",)

        def compute(self, virtual):
            return virtual

    ctx.register(SourcePlugin, VirtualPlugin, TargetPlugin)
    default_mermaid = ctx.plot_lineage("target", kind="mermaid")
    filtered_mermaid = ctx.plot_lineage("target", kind="mermaid", show_virtual_plugins=False)

    assert "VirtualPlugin<br/>" in default_mermaid
    assert "VirtualPlugin<br/>" not in filtered_mermaid
    assert "SourcePlugin<br/>" in filtered_mermaid
    assert "TargetPlugin<br/>" in filtered_mermaid

    import plotly.graph_objects as go

    monkeypatch.setattr(go.Figure, "show", lambda self: None)
    default_plotly_figure = ctx.plot_lineage("target", kind="plotly")
    plotly_figure = ctx.plot_lineage("target", kind="plotly", show_virtual_plugins=False)
    default_labview_figure = ctx.plot_lineage("target", kind="labview")
    labview_figure = ctx.plot_lineage("target", kind="labview", show_virtual_plugins=False)

    assert len(plotly_figure.layout.shapes) < len(default_plotly_figure.layout.shapes)
    assert len(labview_figure.axes[0].patches) < len(default_labview_figure.axes[0].patches)
