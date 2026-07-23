import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.utils.context_help import HelpDocument


class _HelpPlugin(Plugin):
    provides = "help_data"
    depends_on = ["declared_input"]
    description = "Safe <script>alert('x')</script> summary"
    version = "1.0.0"
    output_dtype = np.dtype([("value", "f4")])
    options = {
        "scale": Option(
            default=2.0,
            type=float,
            help="Scale each input value before writing the output.",
        )
    }
    agent_doc = {
        "overview": "First overview paragraph.\n\n<script>alert('overview')</script>",
        "workflow_steps": [
            "Read the selected input rows.",
            "Apply the configured <scale> to every value.",
        ],
        "dependency_notes": {
            "declared_input": "Rows consumed by the help workflow.",
            "resolved_input": "Run-specific rows selected by resolve_depends_on().",
        },
        "config_notes": {"scale": "Controls the multiplication applied to each input value."},
        "field_notes": {"value": "Scaled floating-point result."},
        "execution_notes": ["The help path describes this logic without calling compute()."],
    }

    def resolve_depends_on(self, context, run_id=None):
        if run_id == "broken":
            raise RuntimeError("cannot resolve")
        return ["resolved_input"]

    def compute(self, context, run_id, **kwargs):
        return np.zeros(1, dtype=self.output_dtype)


class _QuickstartPlugin(Plugin):
    provides = "quickstart"
    version = "1.0.0"
    output_dtype = np.dtype([("value", "i4")])

    def compute(self, context, run_id, **kwargs):
        return np.array([(1,)], dtype=self.output_dtype)


def test_help_document_is_str_with_read_only_html():
    document = HelpDocument("plain", "<strong>rich</strong>")
    assert isinstance(document, str)
    assert document == "plain"
    assert document._repr_html_() == "<strong>rich</strong>"
    with pytest.raises(AttributeError):
        document.html_fragment = "changed"


def test_terminal_help_prints_once_and_returns_document(tmp_path, capsys):
    ctx = Context(storage_dir=str(tmp_path))
    document = ctx.help("config")
    captured = capsys.readouterr()
    assert isinstance(document, HelpDocument)
    assert captured.out.count("Documentation:") == 1
    assert str(document) in captured.out


def test_jupyter_help_does_not_print(tmp_path, capsys, monkeypatch):
    ctx = Context(storage_dir=str(tmp_path))
    monkeypatch.setattr("waveform_analysis.utils.context_help._is_jupyter", lambda: True)
    document = ctx.help("examples")
    assert capsys.readouterr().out == ""
    assert "<h2>Examples</h2>" in document._repr_html_()


def test_plugin_help_uses_declared_then_resolved_dependencies(tmp_path, capsys):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(_HelpPlugin())
    declared = ctx.help("help_data")
    resolved = ctx.help("plugin:help_data", run_id="run_001")
    fallback = ctx.help("help_data", run_id="broken")
    capsys.readouterr()
    assert "Dependencies (declared): declared_input" in declared
    assert "Dependencies (resolved): resolved_input" in resolved
    assert "Dependencies (declared fallback): declared_input" in fallback
    assert "Apply the configured <scale>" in declared
    assert "Controls the multiplication" in declared
    assert "Scaled floating-point result" in declared
    assert "<script>" not in declared.html_fragment
    assert "&lt;script&gt;" in declared.html_fragment
    assert "<script>alert('overview')</script>" not in declared.html_fragment
    assert (
        "<p>&lt;script&gt;alert(&#x27;overview&#x27;)&lt;/script&gt;</p>" in declared.html_fragment
    )
    assert "<scale>" not in declared.html_fragment
    assert "&lt;scale&gt;" in declared.html_fragment


def test_quickstart_api_and_topic_are_removed_but_name_can_be_plugin(tmp_path, capsys):
    ctx = Context(storage_dir=str(tmp_path))
    assert not hasattr(ctx, "quickstart")
    unknown = ctx.help("quickstart")
    assert "Unknown help topic" in unknown
    ctx.register(_QuickstartPlugin())
    plugin_help = ctx.help("quickstart")
    capsys.readouterr()
    assert "Plugin: quickstart" in plugin_help
    assert ctx.get_data("run_001", "quickstart")[0]["value"] == 1


def test_plugins_topic_only_lists_registered_plugins(tmp_path, capsys):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(_HelpPlugin())
    document = ctx.help("plugins")
    capsys.readouterr()
    assert "help_data" in document
    assert "raw_files" not in document


def test_static_topics_win_bare_name_and_plugin_prefix_disambiguates(tmp_path, capsys):
    class ConfigPlugin(_QuickstartPlugin):
        provides = "config"

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(ConfigPlugin())
    static = ctx.help("config")
    plugin = ctx.help("plugin:config")
    capsys.readouterr()
    assert static.startswith("Configuration")
    assert plugin.startswith("Plugin: config")


def test_hit_merged_context_help_shows_overview_and_workflow(tmp_path, capsys):
    """Context help for hit_merged must include overview text and 6-step workflow."""
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import HitMergePlugin

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(HitMergePlugin())
    doc = ctx.help("hit_merged")
    capsys.readouterr()

    assert "HitMergePlugin 是波形分析中最核心的后处理插件之一" in doc
    assert "识别可合并" in doc
    assert "保持通道" in doc
    assert "按时间连接" in doc
    assert "限制链式" in doc
    assert "选择代表" in doc
    assert "记录窗口" in doc

    html = doc.html_fragment
    assert "HitMergePlugin 是波形分析中最核心的后处理插件之一" in html
    assert "识别可合并" in html
    assert "按时间连接" in html
    assert "How it works" in html
    assert "Downstream consumers" in html
