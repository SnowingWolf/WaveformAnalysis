import numpy as np
import pytest

from tests.utils import MockPlugin
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin


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


@pytest.mark.parametrize("kind", ["labview", "mermaid", "plotly"])
@pytest.mark.parametrize(
    "keyword",
    [
        "analysis_result",
        "highlight_critical_path",
        "highlight_bottlenecks",
        "highlight_parallel_groups",
    ],
)
def test_context_plot_lineage_rejects_retired_analysis_keywords(tmp_path, kind, keyword):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MockPlugin)

    with pytest.raises(TypeError, match=keyword):
        ctx.plot_lineage("mock_data", kind=kind, **{keyword: True})


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
