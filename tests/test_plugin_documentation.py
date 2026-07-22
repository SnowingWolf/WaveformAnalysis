from pathlib import Path

import numpy as np
import pytest

from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.core.plugins.core.spec import FieldSpec, OutputSchema
from waveform_analysis.utils.plugin_doc_generator import (
    PluginDocGenerator,
    check_plugin_document_structure,
)


class _EmptyPlugin(Plugin):
    provides = "special_chars"
    description = 'Summary with : colon, <tag>, and "quotes".'
    version = "1.2.3"
    output_schema = OutputSchema(kind="dict")

    def compute(self, context, run_id, **kwargs):
        return {}


def test_markdown_profiles_have_exact_sections_tables_and_frontmatter():
    generator = PluginDocGenerator()
    view = generator.extract_doc_info(_EmptyPlugin, _EmptyPlugin())
    auto = generator.render_plugin_page(view, profile="auto")
    agent = generator.render_plugin_page(view, profile="agent")
    assert check_plugin_document_structure(auto, "auto") == []
    assert check_plugin_document_structure(agent, "agent") == []
    assert "schema_version: 1" in auto
    assert 'profile: "auto"' in auto
    assert "| - | - | - | - | - |" in auto
    assert "| - | - | - | - | - | - | - |" in auto
    assert "## Operational Notes" not in auto
    assert "### Behavior" in agent
    assert "### Validation" in agent


def test_structure_checker_rejects_duplicate_or_extra_sections():
    generator = PluginDocGenerator()
    view = generator.extract_doc_info(_EmptyPlugin, _EmptyPlugin())
    content = generator.render_plugin_page(view, profile="auto")
    assert check_plugin_document_structure(content + "\n## Extra\n", "auto")
    assert check_plugin_document_structure(content + "\n## Output\n", "auto")


def test_markdown_table_metadata_escapes_pipe_characters():
    class PipePlugin(_EmptyPlugin):
        provides = "special|chars"

    generator = PluginDocGenerator()
    view = generator.extract_doc_info(PipePlugin, PipePlugin())
    content = generator.render_plugin_page(view, profile="auto")
    assert "`special\\|chars`" in content


def test_web_generation_is_offline_relative_and_escaped(tmp_path):
    generator = PluginDocGenerator()
    generator.register_plugin(_EmptyPlugin)
    result = generator.generate_web(tmp_path)
    index = result["INDEX"].read_text(encoding="utf-8")
    page = result["special_chars"].read_text(encoding="utf-8")
    assert 'href="plugins/special_chars.html"' in index
    assert 'href="../assets/site.css"' in page
    assert "https://" not in index + page
    assert "http://" not in index + page
    assert "<tag>" not in page
    assert "&lt;tag&gt;" in page
    assert (tmp_path / "assets" / "site.css").is_file()
    assert (tmp_path / "assets" / "site.js").is_file()


def test_explicit_output_schema_precedes_dtype_in_plugin_spec():
    plugin = _EmptyPlugin()
    from waveform_analysis.core.plugins.core.spec import PluginSpec

    assert PluginSpec.from_plugin(plugin).output_schema.kind == "dict"


def test_output_schema_participates_in_context_lineage(tmp_path):
    from waveform_analysis.core.context import Context

    context = Context(storage_dir=str(tmp_path))
    context.register(_EmptyPlugin())
    lineage = context.get_lineage("special_chars")
    assert lineage["output_schema"]["kind"] == "dict"


def test_output_schema_conflicts_with_dtype_fail_explicitly():
    class ConflictingPlugin(Plugin):
        provides = "conflict"
        output_dtype = np.dtype([("value", "f4")])
        output_schema = OutputSchema(kind="structured_array", fields=(FieldSpec("other", "f4"),))

        def compute(self, context, run_id, **kwargs):
            return np.zeros(0, dtype=self.output_dtype)

    with pytest.raises(ValueError, match="output_schema fields conflict"):
        ConflictingPlugin().validate()


def test_web_templates_and_assets_are_source_package_data():
    template_root = Path(__file__).parents[1] / "waveform_analysis" / "utils" / "templates" / "web"
    assert (template_root / "index.html.j2").is_file()
    assert (template_root / "plugin.html.j2").is_file()
    assert (template_root / "assets" / "site.css").is_file()


def test_cli_web_rejects_single_plugin_and_serve_requires_existing_directory(
    tmp_path, monkeypatch, capsys
):
    from waveform_analysis.utils import cli_docs

    monkeypatch.setattr(
        "sys.argv",
        ["waveform-docs", "generate", "plugins-web", "--plugin", "records"],
    )
    assert cli_docs.main() == 1
    assert "full-site generation" in capsys.readouterr().out

    missing = tmp_path / "missing-site"
    monkeypatch.setattr(
        "sys.argv",
        ["waveform-docs", "serve", "--directory", str(missing)],
    )
    assert cli_docs.main() == 1
    assert not missing.exists()
