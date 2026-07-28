from dataclasses import replace
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import Thread
from urllib.parse import urljoin
from urllib.request import urlopen

import numpy as np
import pytest

from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.plugins.core.spec import FieldSpec, OutputSchema
from waveform_analysis.utils.plugin_doc_generator import (
    PluginDocGenerator,
    _DefaultDocumentationContext,
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
    assert 'class="site-index docs-page docs-plugin-index docs-page--lineage"' in index
    assert 'href="../assets/site.css"' in page
    assert "https://" not in index + page
    assert "http://" not in index + page
    assert "<tag>" not in page
    assert "&lt;tag&gt;" in page
    assert "<script>alert(1)</script>" not in page
    assert '<div class="plugin-overview"><p>Normal paragraph.</p>' in page
    assert "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p></div>" in page
    assert (tmp_path / "assets" / "site.css").is_file()
    assert (tmp_path / "assets" / "site.js").is_file()
    assert (tmp_path / "assets" / "search-index.js").is_file()
    assert (tmp_path / "assets" / "plotly.min.js").is_file()
    assert (tmp_path / "assets" / "lineage-details.json").is_file()
    assert (tmp_path / "assets" / "lineage-overviews.json").is_file()
    site_js = (tmp_path / "assets" / "site.js").read_text(encoding="utf-8")
    site_css = (tmp_path / "assets" / "site.css").read_text(encoding="utf-8")
    assert "data-lineage-relations" in site_js
    assert "renderRelations" in site_js
    assert 'workspace.classList.add("has-details")' in site_js
    assert 'workspace.classList.remove("has-details")' in site_js
    assert 'workspace.dataset.pluginPrefix ?? "plugins/"' in site_js
    assert "detailPanel.scrollLeft = 0" in site_js
    assert "new ResizeObserver(resizeOverview)" in site_js
    assert "--site-max-width: 1680px" in site_css
    assert "--content-max-width: 980px" in site_css
    assert "grid-template-columns: minmax(0, 1fr) 380px" in site_css
    assert "height: min(720px, calc(100vh - 180px))" in site_css
    assert ".lineage-workspace:not(.has-details)" in site_css


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
    assert "data-lineage-relations" in index
    assert "data-lineage-inputs" in index
    assert "data-lineage-consumers" in index
    assert "IN::" not in index
    assert "OUT::" not in index
    assert 'href="source_rows.html"' in detailed
    assert 'class="lineage-node-placeholder"' not in index
    assert "external_input" not in index
    assert 'href="plugins/external_input.html"' not in index
    assert 'data-lineage-view="core"' in index
    assert 'data-lineage-view="all"' in index
    assert 'href="plugins/unknown_output.html"' in index
    assert 'href="../index.html?focus=detailed_output"' in detailed
    assert 'class="page-location"' not in detailed
    assert '"scrollZoom": true' in index
    assert "plotly_click" not in index
    assert {"source_rows", "detailed_output", "unknown_output"} <= details.keys()
    assert details["detailed_output"] == {"inputs": ["source_rows"], "consumers": []}
    assert details["unknown_output"] == {"inputs": [], "consumers": []}

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
    assert dependencies["records"] == ["raw_files"]
    assert dependencies["wave_pool"] == ["raw_files"]
    assert dependencies["hit_threshold"] == ["records", "wave_pool", "records_asymmetry_mask"]

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
    assert {"plugin:records", "plugin:wave_pool"} <= node_ids
    edges = {(edge.source_id, edge.target_id) for edge in graph.edges}
    assert ("plugin:raw_files", "plugin:records") in edges
    assert ("plugin:raw_files", "plugin:wave_pool") in edges
    assert all("runtime-resolved inputs" not in node.label for node in graph.nodes)


def test_documentation_profile_precedence_is_plugin_shared_then_option_default():
    class ProfilePlugin(_EmptyPlugin):
        provides = "profile_output"
        options = {
            "wave_source": Option(default="st_waveforms", type=str),
            "use_filtered": Option(default=True, type=bool),
            "threshold": Option(default=7, type=int),
        }

    plugin = ProfilePlugin()
    context = _DefaultDocumentationContext(
        {plugin.provides: plugin},
        shared_profile={"wave_source": "records", "use_filtered": False},
        plugin_profile={"profile_output": {"use_filtered": True}},
    )
    assert context.get_config(plugin, "use_filtered") is True
    assert context.get_config(plugin, "wave_source") == "records"
    assert context.get_config(plugin, "threshold") == 7


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
    ]
    assert {plugin.provides for group in groups for plugin in group.plugins} == {
        plugin.provides
        for plugin in generator.get_all_doc_info()
        if plugin.provides != "cache_analysis"
    }
    assert 'data-plugin-set="io"' in index
    assert 'data-plugin-set="events"' in index
    assert 'data-plugin-set="standalone"' in index
    assert "Standalone Tools" in index
    assert index.index('data-plugin-set="io"') < index.index('data-plugin-set="waveform"')
    assert index.index('href="plugins/raw_files.html"') < index.index('data-plugin-set="waveform"')
    assert '"shape":"spline"' in index
    assert "plugin-overview-spline" in index
    assert '"type":"path"' not in index

    site_js = (tmp_path / "assets" / "site.js").read_text(encoding="utf-8")
    assert "pluginSet.hidden" in site_js
    assert 'window.addEventListener("popstate", () => restoreState())' in site_js
    assert 'url.searchParams.set("view", view)' in site_js
    assert "terminalOutputs.has(focus)" in site_js


def test_core_and_all_views_share_layout_and_keep_standalone_out_of_dag():
    generator = PluginDocGenerator()
    generator.load_builtin_plugins()
    dependencies = generator._default_dependency_map()
    plugins = generator._with_web_scores(generator.get_all_doc_info(), dependencies)
    views, terminals = generator._global_lineage_views(
        plugins, link_prefix="plugins/", dependencies_by_provides=dependencies
    )
    core = {n.node_id: (n.x, n.y) for n in views["core"].nodes}
    all_nodes = {n.node_id: (n.x, n.y) for n in views["all"].nodes}
    assert {"df_paired", "waveform_width_integral"} <= terminals
    assert "events" not in terminals
    assert "plugin:events" in core
    assert "plugin:df_paired" not in core
    assert "plugin:df_paired" in all_nodes
    assert core == {name: all_nodes[name] for name in core}
    assert "plugin:cache_analysis" not in all_nodes
    figure = generator._build_global_plotly_figure(views["all"])
    shapes = figure.layout.shapes
    assert figure.layout.xaxis.range[1] >= max(shape.x1 for shape in shapes)
    assert abs(figure.layout.yaxis.range[0]) >= max(shape.y1 for shape in shapes)


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
    assert "How It Works" in auto_md
    assert "How It Works" in agent_md
    assert "工作方式" in html
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

    monkeypatch.setattr(
        "sys.argv",
        ["waveform-docs", "generate", "site-web", "--plugin", "records"],
    )
    assert cli_docs.main() == 1
    assert "仅支持全量生成" in capsys.readouterr().out

    missing = tmp_path / "missing-site"
    monkeypatch.setattr(
        "sys.argv",
        ["waveform-docs", "serve", "--directory", str(missing)],
    )
    assert cli_docs.main() == 1
    assert not missing.exists()


def test_documentation_site_generates_exact_sections_routes_and_offline_assets(tmp_path):
    from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator

    result = DocumentationSiteGenerator().generate(tmp_path)

    assert result["SITE_INDEX"] == tmp_path / "index.html"
    assert result["INDEX"] == tmp_path / "plugins" / "index.html"
    assert result["ACCESSOR_INDEX"] == tmp_path / "accessors" / "index.html"
    assert result["CONTEXT_INDEX"] == tmp_path / "contexts" / "index.html"
    assert result["VISUALIZATION_INDEX"] == tmp_path / "visualizations" / "index.html"
    assert result["context:context"] == tmp_path / "contexts" / "context.html"
    assert {path.name for key, path in result.items() if key.startswith("visualization:")} == {
        "statistical-plots.html",
        "waveform-plots.html",
    }
    assert {path.name for key, path in result.items() if key.startswith("accessor:")} == {
        "peak-channel-accessor.html",
        "s1-s2-pair-accessor.html",
    }
    assert not (tmp_path / "plugins" / "plugins").exists()
    expected_assets = {
        "site.css",
        "site.js",
        "search-index.js",
        "plotly.min.js",
        "lineage-details.json",
        "lineage-overviews.json",
    }
    assert {path.name for path in (tmp_path / "assets").iterdir()} == expected_assets

    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    plugin_index = (tmp_path / "plugins" / "index.html").read_text(encoding="utf-8")
    plugin_page = result["records"].read_text(encoding="utf-8")
    accessor_index = (tmp_path / "accessors" / "index.html").read_text(encoding="utf-8")
    peak_accessor_page = result["accessor:peak-channel-accessor"].read_text(encoding="utf-8")
    pair_accessor_page = result["accessor:s1-s2-pair-accessor"].read_text(encoding="utf-8")
    context_page = result["context:context"].read_text(encoding="utf-8")
    statistical_plots_page = result["visualization:statistical-plots"].read_text(encoding="utf-8")
    waveform_plots_page = result["visualization:waveform-plots"].read_text(encoding="utf-8")
    site_css = (tmp_path / "assets" / "site.css").read_text(encoding="utf-8")
    site_js = (tmp_path / "assets" / "site.js").read_text(encoding="utf-8")
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")
    assert 'href="plugins/index.html"' in home
    assert 'href="accessors/index.html"' in home
    assert 'href="contexts/index.html"' in home
    assert 'href="visualizations/index.html"' in home
    assert 'id="context-and-plugin"' in home
    assert "Context 调度，Plugin 产出数据" in home
    assert 'id="minimal-workflow"' in home
    assert '<span class="n">register</span>' in home
    assert '<span class="n">get_data</span>' in home
    assert '<pre class="code-block language-python"><code><span class="kn">from</span>' in home
    assert "插件声明依赖并负责执行处理" in home
    assert "Accessor 不属于插件 DAG" in home
    assert "先由插件完成处理，再用 Accessor" in home
    assert 'class="site-brand" href="../index.html"' in plugin_index
    assert 'href="records.html"' in plugin_index
    assert 'data-lineage-details="../assets/lineage-details.json"' in plugin_index
    assert 'data-site-root-prefix="../"' in plugin_index
    assert 'href="index.html?focus=records"' in plugin_page
    assert 'href="../accessors/index.html"' in plugin_page
    assert 'href="../contexts/index.html"' in plugin_page
    assert 'href="../visualizations/index.html"' in plugin_page
    assert "框架架构" in plugin_page
    assert 'aria-controls="tree-architecture"' in plugin_page
    assert plugin_page.index("框架架构") < plugin_page.index("插件系统")
    assert "不保存隐式当前运行" in home
    assert "依赖、执行与 DAG" in context_page
    assert "plot_lineage" in context_page
    assert "labview" in context_page
    assert '<span class="k">class</span> <span class="nc">Context</span>' in context_page
    assert "corner_hist" in statistical_plots_page
    assert "plot_1d_cut_on_corner" in statistical_plots_page
    assert "plot_2d_cut_on_corner" in statistical_plots_page
    assert "plot_lineage" not in statistical_plots_page
    assert "plot_waveforms" in waveform_plots_page
    assert "create_peak_plotter" in waveform_plots_page
    assert "PeakChannelAccessor" in accessor_index
    assert "S1S2PairAccessor" in accessor_index
    assert "通过 peaks 对应的分通道信息" in accessor_index
    assert "查询 S1-S2 配对、关联 peak 的求和波形和位置重建结果" in accessor_index
    assert "整体介绍" in peak_accessor_page
    assert "构造器" in peak_accessor_page
    assert "返回值" in peak_accessor_page
    assert "使用注意" in peak_accessor_page
    assert 'class="site-tree" id="site-navigation"' in peak_accessor_page
    assert 'class="page-toc" aria-label="本页目录"' in peak_accessor_page
    assert 'href="../index.html">文档概览</a>' in peak_accessor_page
    assert "data-page-toc" in peak_accessor_page
    assert 'class="site-tree" id="site-navigation"' in plugin_page
    assert 'class="page-toc" aria-label="本页目录"' in plugin_page
    assert "data-page-toc" in plugin_page
    assert 'nav.classList.toggle("is-open", open)' in site_js
    assert "<code>peak_id</code>" in peak_accessor_page
    assert (
        '<h3><code>plot</code></h3><pre class="code-block member-signature language-python"><code><span class="k">def</span> <span class="nf">plot</span><span class="p">(</span>'
        in (peak_accessor_page)
    )
    assert '<pre class="code-block language-python"><code><span class="kn">from</span>' in (
        peak_accessor_page
    )
    assert "score_total_range" in pair_accessor_page
    assert "配对数据源与查询范围" in pair_accessor_page
    assert "筛选掩码的组合语义" in pair_accessor_page
    assert "波形、位置与缓存" in pair_accessor_page
    assert "s1_s2_pair_candidates" in pair_accessor_page
    assert "flags_none" in pair_accessor_page
    assert "release_layer()" in pair_accessor_page
    assert '<article class="member" id="mask"' in pair_accessor_page
    assert '<span class="nf">mask</span>' in pair_accessor_page
    assert (
        '<span class="o">-&gt;</span> <span class="n">np</span><span class="o">.</span><span class="n">ndarray</span>'
        in pair_accessor_page
    )
    assert "<code>peaklet_channels</code>" in peak_accessor_page
    assert "# 逐通道查看，并标注常用特征" in peak_accessor_page
    assert "sum-comparison" in peak_accessor_page
    assert ".language-python .k" in site_css
    assert ".language-python .s" in site_css
    assert "site-search-dialog" in home
    assert "site-search-dialog" in plugin_index
    assert "site-tree" in peak_accessor_page
    assert "page-toc" in peak_accessor_page
    assert "WAVEFORM_DOCS_SEARCH" in search_index
    assert '"url":"index.html#context-and-plugin"' in search_index
    assert '"url":"index.html#minimal-workflow"' in search_index
    assert '"url":"plugins/records.html#overview"' in search_index
    assert '"url":"accessors/peak-channel-accessor.html#overview"' in search_index
    assert '"url":"contexts/context.html#dag-and-execution"' in search_index
    assert '"url":"visualizations/statistical-plots.html#statistical-plots"' in search_index
    assert "data-doc-nav-open" in site_js
    assert "data-theme-toggle" in site_js
    assert "data-tree-toggle" in site_js
    assert "data-page-toc" in site_js
    assert "docs-page--lineage" in plugin_index
    assert "docs-main--wide" in plugin_index
    assert 'data-lineage-canvas="fit"' in plugin_index
    assert "fitOverview" in site_js
    assert "centerOverview" in site_js
    assert "new ResizeObserver(resizeOverview)" in site_js
    assert "data-site-search-input" in site_js
    html = "".join(path.read_text(encoding="utf-8") for path in tmp_path.rglob("*.html"))
    assert "https://" not in html
    assert "http://" not in html


def test_site_web_assets_are_available_over_http_for_root_and_nested_pages(tmp_path):
    from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator

    DocumentationSiteGenerator().generate(tmp_path)
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}/"
    try:
        pages = (
            "index.html",
            "plugins/index.html",
            "plugins/records.html",
            "accessors/index.html",
            "accessors/peak-channel-accessor.html",
            "accessors/s1-s2-pair-accessor.html",
            "contexts/index.html",
            "contexts/context.html",
            "visualizations/index.html",
            "visualizations/statistical-plots.html",
            "visualizations/waveform-plots.html",
        )
        for page in pages:
            with urlopen(urljoin(base_url, page)) as response:
                assert response.status == 200
                html = response.read().decode("utf-8")
            assets = re.findall(r'(?:href|src)="([^"]+)"', html)
            for asset in assets:
                if not asset.endswith((".css", ".js")):
                    continue
                with urlopen(urljoin(urljoin(base_url, page), asset)) as response:
                    assert response.status == 200
                    content_type = response.headers["Content-Type"]
                if asset.endswith(".css"):
                    assert content_type.startswith("text/css")
                else:
                    assert content_type.startswith(("text/javascript", "application/javascript"))
    finally:
        server.shutdown()
        thread.join()


def test_accessor_registry_uses_live_signatures_parameters_and_fails_for_invalid_specs():
    import inspect

    from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor
    from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor
    from waveform_analysis.utils.site_doc_generator import (
        ACCESSOR_DOCUMENTATION_REGISTRY,
        AccessorMemberSpec,
        AccessorParameterSpec,
        DocumentationSiteGenerator,
    )

    views = DocumentationSiteGenerator().build_accessor_views()
    assert [view.slug for view in views] == [
        "peak-channel-accessor",
        "s1-s2-pair-accessor",
    ]
    peak_view, pair_view = views
    assert peak_view.constructor_signature == str(inspect.signature(PeakChannelAccessor))
    assert pair_view.constructor_signature == str(inspect.signature(S1S2PairAccessor))
    assert len(peak_view.members) == 4
    assert len(pair_view.members) == 11
    assert [(member.name, member.kind) for member in pair_view.members][0] == (
        "pairs",
        "property",
    )
    assert all(not member.name.startswith("_") for view in views for member in view.members)
    get_pair = next(member for member in pair_view.members if member.name == "pair")
    assert get_pair.signature == str(inspect.signature(S1S2PairAccessor.pair))
    plot = next(member for member in peak_view.members if member.name == "plot")
    assert plot.signature.startswith("(\n    self,\n    peak_id: int,")
    assert "\n    show_merged_index: bool = True,\n) ->" in plot.signature
    assert [parameter.name for parameter in peak_view.constructor_parameters] == [
        parameter
        for parameter in inspect.signature(PeakChannelAccessor).parameters
        if parameter != "self"
    ]
    assert [parameter.name for parameter in get_pair.parameters] == ["pair_id"]

    broken = replace(
        ACCESSOR_DOCUMENTATION_REGISTRY[0],
        members=(AccessorMemberSpec("missing_member", "Missing."),),
    )
    with pytest.raises(ValueError, match="does not exist"):
        DocumentationSiteGenerator(accessor_registry=(broken,)).build_accessor_views()

    invalid_parameters = replace(
        ACCESSOR_DOCUMENTATION_REGISTRY[0],
        members=(
            AccessorMemberSpec(
                "get_channels",
                "Returns channels.",
                parameters=(AccessorParameterSpec("not_peak_id", "Invalid."),),
            ),
        ),
    )
    with pytest.raises(ValueError, match="parameter names"):
        DocumentationSiteGenerator(accessor_registry=(invalid_parameters,)).build_accessor_views()


def test_callable_documentation_registry_uses_live_signatures_and_explicit_help():
    from waveform_analysis.utils.site_doc_generator import (
        CONTEXT_DOCUMENTATION_PAGE,
        VISUALIZATION_DOCUMENTATION_PAGES,
        DocumentationSiteGenerator,
    )

    generator = DocumentationSiteGenerator()
    context_view = generator.build_callable_page_view(CONTEXT_DOCUMENTATION_PAGE)
    visualization_views = [
        generator.build_callable_page_view(spec) for spec in VISUALIZATION_DOCUMENTATION_PAGES
    ]

    context_members = {
        member.name: member for _, members in context_view.groups for member in members
    }
    assert context_members["Context"].kind == "class"
    assert context_members["get_data"].parameters[0].description.startswith("显式指定")
    assert context_members["plot_lineage"].returns
    assert context_members["plot_lineage"].example_html
    statistical_members = {
        member.name: member for _, members in visualization_views[0].groups for member in members
    }
    assert statistical_members["corner_hist"].example_html
    assert statistical_members["plot_2d_cut_on_corner"].notes


def test_accessor_html_escapes_dynamic_text_and_requires_pygments(tmp_path, monkeypatch):
    import sys

    from waveform_analysis.utils.site_doc_generator import (
        ACCESSOR_DOCUMENTATION_REGISTRY,
        DocumentationSiteGenerator,
        _highlight_python,
    )

    unsafe_registry = (
        replace(
            ACCESSOR_DOCUMENTATION_REGISTRY[0],
            summary="<script>alert('summary')</script>",
            introduction="<img src=x onerror=alert('introduction')>",
            example="value = '<script>alert(1)</script>'",
        ),
    )
    result = DocumentationSiteGenerator(accessor_registry=unsafe_registry).generate(tmp_path)
    content = result["accessor:peak-channel-accessor"].read_text(encoding="utf-8")
    assert "&lt;script&gt;alert" in content
    assert "&lt;img src=x onerror=alert" in content
    assert "&lt;script&gt;" in content
    assert "<script>alert('summary')</script>" not in content
    assert "<img src=x onerror=alert('introduction')>" not in content

    monkeypatch.setitem(sys.modules, "pygments", None)
    with pytest.raises(RuntimeError, match="Pygments"):
        _highlight_python("x = 1")


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
