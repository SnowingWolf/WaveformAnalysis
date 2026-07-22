import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.utils.context_help import HelpDocument


class _HelpPlugin(Plugin):
    provides = "help_data"
    depends_on = ["declared_input"]
    description = "Safe <script>alert('x')</script> summary"
    version = "1.0.0"
    output_dtype = np.dtype([("value", "f4")])

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
    assert "<script>" not in declared.html_fragment
    assert "&lt;script&gt;" in declared.html_fragment


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
