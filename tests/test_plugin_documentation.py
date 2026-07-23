from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from waveform_analysis.core.plugins.core.base import Option, Plugin
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
    agent_doc = {"overview": "Normal paragraph.\n\n<script>alert(1)</script>"}

    def compute(self, context, run_id, **kwargs):
        return {}


class _DetailedPlugin(Plugin):
    provides = "detailed_output"
    depends_on = ["source_rows"]
    description = "Transform source rows into documented output."
    version = "2.0.0"
    output_dtype = np.dtype([("value", "f4")])
    options = {
        "threshold": Option(
            default=3.0,
            type=float,
            help="Select values above the configured threshold.",
        )
    }
    agent_doc = {
        "workflow_steps": [
            "Load <source-marker> rows in timestamp order.",
            "Keep rows above threshold and calculate the output value.",
        ],
        "dependency_notes": {"source_rows": "Timestamp-ordered input rows."},
        "dependency_fields": {"source_rows": ["timestamp", "signal"]},
        "config_notes": {"threshold": "Changes which source rows reach the output."},
        "field_notes": {"value": "Calculated value for each selected row."},
        "execution_notes": ["Row ordering is preserved after selection."],
        "failure_modes": ["Input rows without signal cannot be evaluated."],
    }

    def compute(self, context, run_id, **kwargs):
        return np.zeros(0, dtype=self.output_dtype)


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
    assert "<script>" not in page
    assert '<div class="plugin-overview"><p>Normal paragraph.</p>' in page
    assert "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p></div>" in page
    assert (tmp_path / "assets" / "site.css").is_file()
    assert (tmp_path / "assets" / "site.js").is_file()
    assert (tmp_path / "assets" / "plotly.min.js").is_file()
    assert (tmp_path / "assets" / "lineage-details.json").is_file()


def test_web_lineage_omits_unknown_inputs_and_lists_isolated_plugins(tmp_path):
    class SourcePlugin(_EmptyPlugin):
        provides = "source_rows"
        description = "Rows produced for downstream transformations."

    class UnknownInputPlugin(_DetailedPlugin):
        provides = "unknown_output"
        depends_on = ["external_input"]
        agent_doc = {
            **_DetailedPlugin.agent_doc,
            "dependency_notes": {"external_input": "Input supplied outside this reference."},
        }

    generator = PluginDocGenerator()
    generator.register_plugin(SourcePlugin)
    generator.register_plugin(_DetailedPlugin)
    generator.register_plugin(UnknownInputPlugin)

    result = generator.generate_web(tmp_path)
    index = result["INDEX"].read_text(encoding="utf-8")
    detailed = result["detailed_output"].read_text(encoding="utf-8")
    details = json.loads((tmp_path / "assets" / "lineage-details.json").read_text())
    assert 'src="assets/plotly.min.js"' in index
    assert 'id="plugin-global-lineage"' in index
    assert 'data-lineage-details="assets/lineage-details.json"' in index
    assert "data-lineage-detail-plot" in index
    assert "IN::" not in index
    assert "OUT::" not in index
    assert 'href="source_rows.html"' in detailed
    assert 'class="lineage-node-placeholder"' not in index
    assert "external_input" not in index
    assert 'href="plugins/external_input.html"' not in index
    assert "isolated plugins (under defaults)" in index
    assert 'href="plugins/unknown_output.html"' in index
    assert 'href="../index.html?focus=detailed_output"' in detailed
    assert '"scrollZoom": true' in index
    assert "plotly_click" not in index
    assert {"source_rows", "detailed_output", "unknown_output"} <= details.keys()
    assert any(
        trace.get("name") == "node_detailed_output" for trace in details["detailed_output"]["data"]
    )

    dynamic_view = replace(
        generator.extract_doc_info(_EmptyPlugin, _EmptyPlugin()),
        provides="dynamic_output",
        has_dynamic_dependencies=True,
    )
    dynamic_graph = generator._build_web_lineage_graph(
        generator._with_web_scores([dynamic_view]), link_prefix="plugins/"
    )
    assert dynamic_graph.nodes == []
    assert [node.label for node in dynamic_graph.isolated_nodes] == ["dynamic_output"]


def test_web_lineage_resolves_dynamic_dependencies_from_plugin_defaults():
    generator = PluginDocGenerator()
    generator.load_builtin_plugins()

    dependencies = generator._default_dependency_map()
    assert dependencies["st_waveforms"] == ["raw_files"]

    plugins = generator._with_web_scores(
        generator.get_all_doc_info(), dependencies_by_provides=dependencies
    )
    graph = generator._build_web_lineage_graph(
        plugins,
        link_prefix="plugins/",
        dependencies_by_provides=dependencies,
    )
    node_ids = {node.node_id for node in graph.nodes}
    assert "plugin:raw_files" in node_ids
    assert "plugin:st_waveforms" in node_ids
    assert ("plugin:raw_files", "plugin:st_waveforms") in {
        (edge.source_id, edge.target_id) for edge in graph.edges
    }


def test_web_cards_group_by_canonical_plugin_sets_and_global_edges_are_curved(tmp_path):
    generator = PluginDocGenerator()
    generator.load_builtin_plugins()

    result = generator.generate_web(tmp_path)
    index = result["INDEX"].read_text(encoding="utf-8")
    groups = generator._web_plugin_sets(generator.get_all_doc_info())

    assert [group.name for group in groups] == [
        "io",
        "waveform",
        "hit",
        "peaks",
        "basic_features",
        "tabular",
        "events",
        "other",
    ]
    assert {plugin.provides for group in groups for plugin in group.plugins} == {
        plugin.provides for plugin in generator.get_all_doc_info()
    }
    assert 'data-plugin-set="io"' in index
    assert 'data-plugin-set="events"' in index
    assert 'data-plugin-set="other"' in index
    assert index.index('data-plugin-set="io"') < index.index('data-plugin-set="waveform"')
    assert index.index('href="plugins/raw_files.html"') < index.index('data-plugin-set="waveform"')
    assert '"type":"path"' in index
    assert "plugin-overview-edges" not in index

    site_js = (tmp_path / "assets" / "site.js").read_text(encoding="utf-8")
    assert "pluginSet.hidden" in site_js


def test_detail_lineage_contains_direct_neighbors_not_transitive_plugins():
    class SourcePlugin(_EmptyPlugin):
        provides = "source_rows"

    class MiddlePlugin(_DetailedPlugin):
        provides = "middle_rows"
        depends_on = ["source_rows"]

    class TargetPlugin(_DetailedPlugin):
        provides = "target_rows"
        depends_on = ["middle_rows"]

    class ConsumerPlugin(_DetailedPlugin):
        provides = "consumer_rows"
        depends_on = ["target_rows"]

    generator = PluginDocGenerator()
    for plugin in (SourcePlugin, MiddlePlugin, TargetPlugin, ConsumerPlugin):
        generator.register_plugin(plugin)
    dependencies = generator._default_dependency_map()
    plugins = generator._with_web_scores(
        generator.get_all_doc_info(), dependencies_by_provides=dependencies
    )
    model = generator._build_default_lineage_model(plugins, dependencies)
    detail = generator._direct_lineage_model(model, "target_rows")

    assert set(detail.nodes) == {"middle_rows", "target_rows", "consumer_rows"}
    assert {(edge.source_node_id, edge.target_node_id) for edge in detail.edges} == {
        ("middle_rows", "target_rows"),
        ("target_rows", "consumer_rows"),
    }


def test_documentation_completeness_excludes_inapplicable_sections_from_denominator():
    generator = PluginDocGenerator()
    view = generator.extract_doc_info(_EmptyPlugin, _EmptyPlugin())

    scored = generator._with_web_scores([view])[0]

    assert scored.documentation_completeness == 53
    assert scored.dag_impact == 0


def test_detailed_content_is_shared_by_markdown_and_web_renderers():
    generator = PluginDocGenerator()
    view = generator.extract_doc_info(_DetailedPlugin, _DetailedPlugin())
    auto = generator.render_plugin_page(view, profile="auto")
    agent = generator.render_plugin_page(view, profile="agent")
    html = generator.render_plugin_html(view)

    for rendered in (auto, agent, html):
        assert "Keep rows above threshold" in rendered
        assert "Changes which source rows reach the output" in rendered
        assert "Calculated value for each selected row" in rendered
        assert "source_rows" in rendered
        assert "timestamp, signal" in rendered
    assert "Row ordering is preserved" in agent
    assert "Row ordering is preserved" in html
    assert "<source-marker>" in auto
    assert "<source-marker>" in agent
    assert "<source-marker>" not in html
    assert "&lt;source-marker&gt;" in html
    assert check_plugin_document_structure(auto, "auto") == []
    assert check_plugin_document_structure(agent, "agent") == []


def test_plugin_graph_enriches_dependency_descriptions_and_consumers():
    class SourcePlugin(_EmptyPlugin):
        provides = "source_rows"
        description = "Rows produced for downstream transformations."

    generator = PluginDocGenerator()
    views = generator.enrich_documentation_views(
        [
            generator.extract_doc_info(SourcePlugin, SourcePlugin()),
            generator.extract_doc_info(_DetailedPlugin, _DetailedPlugin()),
        ]
    )
    source = next(view for view in views if view.provides == "source_rows")
    detailed = next(view for view in views if view.provides == "detailed_output")
    assert source.downstream_consumers == ["detailed_output"]
    assert detailed.dependency_details[0].description == ("Timestamp-ordered input rows.")
    assert detailed.execution_chain == ["source_rows", "detailed_output"]


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


def test_hit_merged_has_overview_and_workflow_steps():
    """hit_merged must have Chinese overview text and 6 concrete workflow steps."""
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import HitMergePlugin

    agent_doc = HitMergePlugin.agent_doc
    assert isinstance(agent_doc["overview"], str) and len(agent_doc["overview"]) > 50
    assert "HitMergePlugin" in agent_doc["overview"]
    assert "板" in agent_doc["overview"]  # Contains Chinese description
    steps = agent_doc["workflow_steps"]
    assert len(steps) == 6, f"Expected 6 workflow_steps, got {len(steps)}"
    # Each step must contain Chinese and its identifier
    expected_identifiers = [
        "识别可合并",
        "保持通道",
        "按时间连接",
        "限制链式",
        "选择代表",
        "记录窗口",
    ]
    for idx, (step, ident) in enumerate(zip(steps, expected_identifiers, strict=False)):
        assert ident in step, f"Step {idx}: expected identifier '{ident}' not found in '{step}'"


def test_hit_merged_cross_renderer_content():
    """hit_merged overview and workflow steps appear in all four renderers."""
    generator = PluginDocGenerator()
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import HitMergePlugin

    view = generator.extract_doc_info(HitMergePlugin, HitMergePlugin())
    auto_md = generator.render_plugin_page(view, profile="auto")
    agent_md = generator.render_plugin_page(view, profile="agent")
    html = generator.render_plugin_html(view)

    # Overview must appear in all four renderers
    for rendered in (auto_md, agent_md, html):
        assert (
            "HitMergePlugin 是波形分析中最核心的后处理插件之一" in rendered
        ), f"Overview not found in rendered content (first 200): {rendered[:200]}"
        assert "识别可合并" in rendered
        assert "按时间连接" in rendered
        assert "选择代表" in rendered
        # How It Works section must be present in all
        assert "How It Works" in rendered
    # auto profile should NOT have Operational Notes or Maintenance
    assert "## Operational Notes" not in auto_md
    # agent profile SHOULD have Operational Notes and Maintenance
    assert "## Operational Notes" in agent_md
    assert "## Maintenance" in agent_md
    # Verify structure check passes
    assert check_plugin_document_structure(auto_md, "auto") == []
    assert check_plugin_document_structure(agent_md, "agent") == []


def test_hit_merged_no_execution_chain_in_how_it_works():
    """How It Works section only shows explicit workflow_steps, NOT execution chain."""
    generator = PluginDocGenerator()
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import HitMergePlugin

    view = generator.extract_doc_info(HitMergePlugin, HitMergePlugin())
    auto_md = generator.render_plugin_page(view, profile="auto")
    agent_md = generator.render_plugin_page(view, profile="agent")

    for rendered in (auto_md, agent_md):
        # No generic "Read dependency data" or "Return output" or "Resolve input dependencies"
        assert "Read dependency data" not in rendered
        assert "Return output" not in rendered
        assert "Resolve input dependencies" not in rendered
        assert "Inspect and run" not in rendered
        assert "Inspect The Execution" not in rendered
        # No standalone "Execution Chain" section
        assert "Execution Chain" not in rendered


def test_single_plugin_generation_hit_merged(tmp_path):
    """Generate only hit_merged docs to avoid touching all 35 plugins."""
    generator = PluginDocGenerator()
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import HitMergePlugin

    generator.register_plugin(HitMergePlugin)
    generator.register_plugin(HitMergePlugin, HitMergePlugin())

    auto_path = tmp_path / "auto" / "hit_merged.md"
    agent_path = tmp_path / "agent" / "hit_merged.md"
    generator.generate_single("HitMergePlugin", auto_path, profile="auto")
    generator.generate_single("HitMergePlugin", agent_path, profile="agent")

    auto_content = auto_path.read_text(encoding="utf-8")
    agent_content = agent_path.read_text(encoding="utf-8")

    assert "HitMergePlugin 是波形分析中最核心的后处理插件之一" in auto_content
    assert "HitMergePlugin 是波形分析中最核心的后处理插件之一" in agent_content
    assert "识别可合并" in auto_content
    assert "按时间连接" in auto_content
    assert "选择代表" in auto_content
    assert "按时间连接" in agent_content
    assert "选择代表" in agent_content

    assert check_plugin_document_structure(auto_content, "auto") == []
    assert check_plugin_document_structure(agent_content, "agent") == []


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


def test_overview_paragraphs_fallback_from_overview_string():
    """When overview_paragraphs is absent, split overview by \\n\\n."""

    class _FallbackPlugin(Plugin):
        provides = "fallback_ov"
        description = "Fallback test plugin."
        version = "0.0.1"
        agent_doc = {
            "overview": "Para one.\n\nPara two.\n\nPara three.",
        }

        def compute(self, context, run_id, **kwargs):
            return {}

    generator = PluginDocGenerator()
    view = generator.extract_doc_info(_FallbackPlugin, _FallbackPlugin())
    assert view.overview_paragraphs == ["Para one.", "Para two.", "Para three."]
    assert view.overview == "Para one.\n\nPara two.\n\nPara three."

    class _EmptyOverviewPlugin(Plugin):
        provides = "empty_ov"
        description = "Empty overview test."
        version = "0.0.1"
        agent_doc = {"overview": ""}

        def compute(self, context, run_id, **kwargs):
            return {}

    view2 = generator.extract_doc_info(_EmptyOverviewPlugin, _EmptyOverviewPlugin())
    assert view2.overview_paragraphs == []
    assert view2.overview == ""
