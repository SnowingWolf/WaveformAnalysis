from dataclasses import replace
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import inspect
import json
from pathlib import Path
import re
from threading import Thread
from urllib.parse import urljoin
from urllib.request import urlopen

import numpy as np
import pytest

from waveform_analysis.core.context import Context
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
    assert 'class="site-index docs-page docs-plugin-index' in index
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
    assert (tmp_path / "assets" / "react" / "waveform-docs.js").is_file()
    assert (tmp_path / "assets" / "react" / "waveform-docs.css").is_file()
    assert (tmp_path / "assets" / "lineage-graph.json").is_file()
    site_css = (tmp_path / "assets" / "site.css").read_text(encoding="utf-8")
    react_bundle = (tmp_path / "assets" / "react" / "waveform-docs.js").read_text(encoding="utf-8")
    assert "ReactFlow" in react_bundle
    assert "elk.algorithm" in react_bundle
    assert "--site-max-width: 1680px" in site_css
    assert "--content-max-width: 980px" in site_css
    assert "site-tree" in site_css


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
    lineage = result["LINEAGE_INDEX"].read_text(encoding="utf-8")
    detailed = result["detailed_output"].read_text(encoding="utf-8")
    graph = json.loads((tmp_path / "assets" / "lineage-graph.json").read_text())
    assert "data-react-lineage" in lineage
    assert re.search(r'src="assets/react/waveform-docs\.js\?v=[0-9a-f]{12}"', lineage)
    assert 'href="source_rows.html"' in detailed
    assert 'class="lineage-node-placeholder"' not in lineage
    assert "external_input" not in graph["views"]
    assert {node["data"]["id"] for node in graph["nodes"]} >= {
        "source_rows",
        "detailed_output",
        "unknown_output",
    }
    assert 'href="../lineage.html?view=focus&amp;focus=detailed_output"' in detailed
    assert 'class="page-location"' not in detailed

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


def test_context_lineage_payload_reuses_port_level_web_contract():
    class SourcePlugin(_EmptyPlugin):
        provides = "context_source"

    class TargetPlugin(_DetailedPlugin):
        provides = "context_target"
        depends_on = ["context_source"]

    context = Context()
    context.register(SourcePlugin, TargetPlugin)
    payload = PluginDocGenerator().build_lineage_payload_for_context(context)

    nodes = {entry["data"]["id"]: entry["data"] for entry in payload["nodes"]}
    edge = next(entry["data"] for entry in payload["edges"])
    assert nodes["context_target"]["summary"] == TargetPlugin.description
    assert edge["source_node_id"] == "context_source"
    assert edge["target_node_id"] == "context_target"
    assert edge["source_port_id"] in {port["id"] for port in nodes["context_source"]["out_ports"]}
    assert edge["target_port_id"] in {port["id"] for port in nodes["context_target"]["in_ports"]}


def test_context_lineage_payload_marks_virtual_nodes():
    class SourcePlugin(_EmptyPlugin):
        provides = "context_source"

    class VirtualPlugin(_DetailedPlugin):
        provides = "context_virtual"
        depends_on = ["context_source"]
        lineage_virtual = True

    class TargetPlugin(_DetailedPlugin):
        provides = "context_target"
        depends_on = ["context_virtual"]

    context = Context()
    context.register(SourcePlugin, VirtualPlugin, TargetPlugin)
    payload = PluginDocGenerator().build_lineage_payload_for_context(context)
    nodes = {entry["data"]["id"]: entry["data"] for entry in payload["nodes"]}

    assert nodes["context_virtual"]["isLineageVirtual"] is True
    assert nodes["context_source"]["isLineageVirtual"] is False


def test_builtin_calculation_backtracking_plugins_are_lineage_virtual():
    from waveform_analysis.core.plugins.builtin.cpu.records import WavePoolPlugin
    from waveform_analysis.core.plugins.builtin.cpu.records_asymmetry import (
        RecordsAsymmetryMaskPlugin,
    )
    from waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates import (
        S1S2PairCandidatesPlugin,
    )
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import HitMergedComponentsPlugin
    from waveform_analysis.core.plugins.builtin.hit.hit_merged_features import (
        HitMergedFeaturesPlugin,
    )
    from waveform_analysis.core.plugins.builtin.peaks.peaklet_channels import (
        PeakletChannelsPlugin,
    )
    from waveform_analysis.core.plugins.builtin.peaks.peaklets import (
        PeakletComponentsPlugin,
        PeakletFeaturesPlugin,
        PeakletWaveformPlugin,
        PeakletWaveformPoolPlugin,
    )

    virtual_plugins = (
        WavePoolPlugin,
        HitMergedComponentsPlugin,
        HitMergedFeaturesPlugin,
        PeakletComponentsPlugin,
        PeakletChannelsPlugin,
        PeakletWaveformPoolPlugin,
        PeakletFeaturesPlugin,
        S1S2PairCandidatesPlugin,
    )
    assert all(plugin.lineage_virtual for plugin in virtual_plugins)
    assert not getattr(RecordsAsymmetryMaskPlugin, "lineage_virtual", False)
    assert not getattr(PeakletWaveformPlugin, "lineage_virtual", False)


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
    graph = json.loads((tmp_path / "assets" / "lineage-graph.json").read_text())
    assert any(edge["data"]["kind"] == "main" for edge in graph["edges"])

    site_js = (tmp_path / "assets" / "site.js").read_text(encoding="utf-8")
    assert "pluginSet.hidden" in site_js
    assert "pluginSet.hidden" in site_js


def test_core_and_all_views_share_layout_and_keep_standalone_out_of_dag():
    generator = PluginDocGenerator()
    generator.load_builtin_plugins()
    dependencies = generator._default_dependency_map()
    plugins = generator._with_web_scores(generator.get_all_doc_info(), dependencies)
    views, terminals = generator._global_lineage_views(
        plugins, link_prefix="plugins/", dependencies_by_provides=dependencies
    )
    overview = {n.node_id: (n.x, n.y) for n in views["overview"].nodes}
    full_nodes = {n.node_id: (n.x, n.y) for n in views["full"].nodes}
    assert {"df_paired", "waveform_width_integral"} <= terminals
    assert "events" not in terminals
    assert "plugin:events" in overview
    assert "plugin:df_paired" not in overview
    assert "plugin:df_paired" in full_nodes
    assert overview == {name: full_nodes[name] for name in overview}
    assert "plugin:cache_analysis" not in full_nodes


def test_global_lineage_exposes_react_flow_metadata():
    generator = PluginDocGenerator()
    generator.load_builtin_plugins()
    dependencies = generator._default_dependency_map()
    plugins = generator._with_web_scores(generator.get_all_doc_info(), dependencies)
    views, _ = generator._global_lineage_views(
        plugins, link_prefix="plugins/", dependencies_by_provides=dependencies
    )

    payload = generator._build_cytoscape_lineage_payload(
        plugins, dependencies, plugin_href_prefix="plugins/"
    )
    assert payload["focusDepth"] == 2
    assert {node["data"]["id"] for node in payload["nodes"]} >= {
        "peaklet_waveform_pool",
        "hit_merged_components",
    }
    nodes = {node["data"]["id"]: node["data"] for node in payload["nodes"]}
    ports = {
        port["id"]: (node_id, port["kind"])
        for node_id, node in nodes.items()
        for port in node["in_ports"] + node["out_ports"]
    }
    assert payload["edges"]
    for entry in payload["edges"]:
        edge = entry["data"]
        assert ports[edge["source_port_id"]] == (edge["source_node_id"], "out")
        assert ports[edge["target_port_id"]] == (edge["target_node_id"], "in")
        assert edge["dtype"]
        assert edge["category"]

    overview = set(payload["views"]["overview"])
    overview_edges = [
        entry["data"]
        for entry in payload["edges"]
        if entry["data"]["source_node_id"] in overview
        and entry["data"]["target_node_id"] in overview
    ]
    expected_pairs = {
        (source, target)
        for target in overview
        for source in dependencies.get(target, [])
        if source in overview
    }
    assert {
        (edge["source_node_id"], edge["target_node_id"]) for edge in overview_edges
    } == expected_pairs


def test_web_lineage_embedded_payload_escapes_script_terminators(tmp_path):
    class ScriptTitlePlugin(_EmptyPlugin):
        provides = "script_title"

    ScriptTitlePlugin.__name__ = "</script><script>alert(1)</script>"
    generator = PluginDocGenerator()
    generator.register_plugin(ScriptTitlePlugin)

    result = generator.generate_web(tmp_path)
    lineage = result["LINEAGE_INDEX"].read_text(encoding="utf-8")

    assert "</script><script>alert(1)</script>" not in lineage
    assert r"\u003c/script\u003e\u003cscript\u003ealert(1)" in lineage


def test_web_lineage_payload_rejects_dangling_port_with_edge_id():
    payload = {
        "nodes": [
            {
                "data": {
                    "id": "source",
                    "in_ports": [],
                    "out_ports": [
                        {"id": "OUT::source::0", "kind": "out"},
                    ],
                }
            },
            {
                "data": {
                    "id": "target",
                    "in_ports": [{"id": "IN::target::0", "kind": "in"}],
                    "out_ports": [],
                }
            },
        ],
        "edges": [
            {
                "data": {
                    "id": "broken-edge",
                    "source_node_id": "source",
                    "source_port_id": "OUT::missing::0",
                    "target_node_id": "target",
                    "target_port_id": "IN::target::0",
                }
            }
        ],
    }
    with pytest.raises(ValueError, match="broken-edge.*OUT::missing::0"):
        PluginDocGenerator._validate_lineage_payload(payload)


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


def test_dynamic_lineage_endpoint_serves_context_payload(tmp_path):
    from waveform_analysis.utils import cli_docs

    class SourcePlugin(_EmptyPlugin):
        provides = "api_source"

    class TargetPlugin(_DetailedPlugin):
        provides = "api_target"
        depends_on = ["api_source"]

    context = Context()
    context.register(SourcePlugin, TargetPlugin)
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("ok", encoding="utf-8")

    def provider() -> dict:
        return PluginDocGenerator().build_lineage_payload_for_context(context)

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(
            cli_docs._DocumentationRequestHandler,
            directory=str(site),
            lineage_payload_provider=provider,
        ),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/api/lineage") as response:
            payload = json.loads(response.read())
        assert response.headers["Cache-Control"] == "no-store, max-age=0"
        assert {node["data"]["id"] for node in payload["nodes"]} == {
            "api_source",
            "api_target",
        }
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_dynamic_lineage_factory_requires_a_callable_context_factory(monkeypatch):
    from types import SimpleNamespace

    from waveform_analysis.utils import cli_docs

    class SourcePlugin(_EmptyPlugin):
        provides = "factory_source"

    context = Context()
    context.register(SourcePlugin)
    monkeypatch.setattr(
        cli_docs.importlib,
        "import_module",
        lambda name: SimpleNamespace(create_context=lambda: context),
    )

    provider = cli_docs._lineage_payload_provider("trusted.docs:create_context")
    assert provider()["nodes"][0]["data"]["id"] == "factory_source"
    with pytest.raises(ValueError, match="package.module:function"):
        cli_docs._lineage_payload_provider("not-a-factory")


def test_documentation_site_generates_exact_sections_routes_and_offline_assets(tmp_path):
    from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator

    result = DocumentationSiteGenerator().generate(tmp_path)

    assert result["SITE_INDEX"] == tmp_path / "index.html"
    assert result["INDEX"] == tmp_path / "plugins" / "index.html"
    assert result["ROOT_LINEAGE"] == tmp_path / "lineage.html"
    assert result["ACCESSOR_INDEX"] == tmp_path / "accessors" / "index.html"
    assert result["CONTEXT_INDEX"] == tmp_path / "contexts" / "index.html"
    assert result["ADAPTER_INDEX"] == tmp_path / "adapters" / "index.html"
    assert result["VISUALIZATION_INDEX"] == tmp_path / "visualizations" / "index.html"
    assert "guide-index:guides" not in result
    assert result["guide-index:architecture"] == tmp_path / "architecture" / "index.html"
    assert "guide:docs/user-guide/QUICKSTART_GUIDE.md" not in result
    assert not (tmp_path / "guides").exists()
    assert result["asset:mermaid/mermaid.min.js"] == (
        tmp_path / "assets" / "mermaid" / "mermaid.min.js"
    )
    assert result["asset:mermaid/MERMAID-LICENSE.txt"].is_file()
    assert result["context:context"] == tmp_path / "contexts" / "context.html"
    assert result["adapter:adapter"] == tmp_path / "adapters" / "adapter.html"
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
        "lineage-graph.json",
        "mermaid",
        "react",
    }
    assert {path.name for path in (tmp_path / "assets").iterdir()} == expected_assets

    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    plugin_index = (tmp_path / "plugins" / "index.html").read_text(encoding="utf-8")
    lineage_page = result["LINEAGE_INDEX"].read_text(encoding="utf-8")
    root_lineage_page = result["ROOT_LINEAGE"].read_text(encoding="utf-8")
    plugin_page = result["records"].read_text(encoding="utf-8")
    accessor_index = (tmp_path / "accessors" / "index.html").read_text(encoding="utf-8")
    peak_accessor_page = result["accessor:peak-channel-accessor"].read_text(encoding="utf-8")
    pair_accessor_page = result["accessor:s1-s2-pair-accessor"].read_text(encoding="utf-8")
    context_page = result["context:context"].read_text(encoding="utf-8")
    context_index_page = result["CONTEXT_INDEX"].read_text(encoding="utf-8")
    adapter_index_page = result["ADAPTER_INDEX"].read_text(encoding="utf-8")
    adapter_page = result["adapter:adapter"].read_text(encoding="utf-8")
    statistical_plots_page = result["visualization:statistical-plots"].read_text(encoding="utf-8")
    waveform_plots_page = result["visualization:waveform-plots"].read_text(encoding="utf-8")
    site_css = (tmp_path / "assets" / "site.css").read_text(encoding="utf-8")
    site_js = (tmp_path / "assets" / "site.js").read_text(encoding="utf-8")
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")
    architecture_page = result["guide:docs/architecture/ARCHITECTURE.md"].read_text(
        encoding="utf-8"
    )
    assert 'href="plugins/index.html"' in home
    assert 'href="accessors/index.html"' in home
    assert 'href="contexts/context.html"' in home
    assert 'href="adapters/adapter.html"' in home
    assert 'href="visualizations/index.html"' in home
    assert "用户指南" not in home
    assert "系统架构与数据模型" in home
    assert 'href="guides/quickstart.html"' not in home
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
    assert 'data-site-root-prefix="../"' in plugin_index
    assert 'href="lineage.html?view=focus&amp;focus=records"' in plugin_page
    assert 'href="../accessors/index.html"' in plugin_page
    assert 'href="../contexts/context.html"' in plugin_page
    assert 'href="../visualizations/index.html"' in plugin_page
    assert 'href="../visualizations/statistical-plots.html"' in plugin_index
    assert 'href="../visualizations/waveform-plots.html"' in plugin_index
    assert 'href="../visualizations/statistical-plots.html"' in plugin_page
    assert 'href="../visualizations/waveform-plots.html"' in plugin_page
    assert "index.htmlstatistical-plots.html" not in plugin_index
    assert "index.htmlwaveform-plots.html" not in plugin_page
    assert "Context 与适配器" in plugin_page
    assert 'href="../contexts/index.html">Context 与适配器</a>' in plugin_page
    assert 'aria-controls="tree-architecture"' in plugin_page
    sidebar_tree = plugin_page.split('<ul class="site-tree-list">', 1)[1]
    assert sidebar_tree.index("Context 与适配器") < sidebar_tree.index("插件系统")
    assert "不保存隐式当前运行" in home
    assert "依赖、执行与 DAG" in context_page
    assert "Context 与适配器" in context_index_page
    assert 'href="context.html"' in context_index_page
    assert 'href="../adapters/adapter.html"' in context_index_page
    assert "Context 与适配器" in adapter_index_page
    assert 'href="../contexts/context.html"' in adapter_index_page
    assert 'href="adapter.html"' in adapter_index_page
    assert "架构职责与数据流" in adapter_index_page
    assert "协调 DAG、配置、lineage 与缓存" in adapter_index_page
    assert "raw_files" in adapter_index_page
    assert "records_view" in adapter_index_page
    assert "plot_lineage" in context_page
    assert "labview" in context_page
    assert re.search(
        r'<span class="k">class</span>\s*(?:<span class="w"> </span>\s*)?'
        r'<span class="nc">Context</span>',
        context_page,
    )
    assert "推荐使用流程" in adapter_page
    assert "Context.get_adapter_info" in adapter_page
    assert "Context.get_resolved_config" in adapter_page
    assert "显式插件配置优先于 adapter 推断" in adapter_page
    assert "缓存 lineage" in adapter_page
    assert "register_adapter" in adapter_page
    assert "my_adapter" in adapter_page
    assert 'href="../adapters/adapter.html"' in plugin_page
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
    assert 'class="page-toc" id="page-toc" aria-label="本页目录"' in peak_accessor_page
    assert 'href="../index.html">文档概览</a>' in peak_accessor_page
    assert "data-page-toc-toggle" in peak_accessor_page
    assert "data-page-toc-pin" in peak_accessor_page
    assert "data-page-toc-expand-all" in peak_accessor_page
    assert "data-page-toc-collapse-all" in peak_accessor_page
    assert "pin-icon--fixed" in peak_accessor_page
    assert 'class="site-tree" id="site-navigation"' in plugin_page
    assert 'class="page-toc" id="page-toc" aria-label="本页目录"' in plugin_page
    assert "data-page-toc-toggle" in plugin_page
    assert "data-page-toc-pin" in plugin_page
    assert "data-tree-visibility-toggle" in architecture_page
    assert "data-doc-nav-restore" in architecture_page
    assert 'aria-controls="tree-guide-architecture"' in architecture_page
    assert 'href="../plugins/overview.html">插件系统</a>' in architecture_page
    assert "data-page-toc-toggle" in home
    assert "data-page-toc-pin" in context_index_page
    assert "data-page-toc" not in lineage_page
    assert 'nav.classList.toggle("is-open", open)' in site_js
    assert "<code>peak_id</code>" in peak_accessor_page
    assert re.search(
        r'<h3><code>plot</code></h3><pre class="code-block member-signature language-python">'
        r'<code><span class="k">def</span>\s*(?:<span class="w"> </span>\s*)?'
        r'<span class="nf">plot</span><span class="p">\(</span>',
        peak_accessor_page,
    )
    assert '<pre class="code-block language-python"><code><span class="kn">from</span>' in (
        peak_accessor_page
    )
    assert "score_total_range" in pair_accessor_page
    assert "配对数据源与查询范围" in pair_accessor_page
    assert "筛选掩码的组合语义" in pair_accessor_page
    assert "波形与位置" in pair_accessor_page
    assert "缓存与释放" in pair_accessor_page
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
    assert '"url":"guides/quickstart.html"' not in search_index
    assert '"url":"guides/index.html"' not in search_index
    assert '"url":"architecture/system.html"' in search_index
    assert '"url":"architecture/plugin-dag-lineage-cache.html"' in search_index
    assert '"url":"architecture/data-products.html"' in search_index
    assert '"url":"architecture/accessor-analysis.html"' in search_index
    assert '"url":"architecture/records-wave-pool.html"' not in search_index
    assert '"url":"architecture/multi-run-processing.html"' not in search_index
    assert '"url":"architecture/data-access.html"' not in search_index
    assert "assets/mermaid/mermaid.min.js?v=" in architecture_page
    assert "data-mermaid-block" in architecture_page
    assert "data-doc-nav-open" in site_js
    assert "data-theme-toggle" in site_js
    assert "data-tree-toggle" in site_js
    assert "waveform-docs-navigation-hidden" in site_js
    assert "restoreNavigation" in site_js
    assert "data-page-toc" in site_js
    assert "page-toc-group-toggle" in site_js
    assert "setTocPinned" in site_js
    assert "data-page-toc-expand-all" in site_js
    assert "data-page-toc-collapse-all" in site_js
    assert ".doc-layout.is-navigation-hidden" in site_css
    assert ".doc-layout.is-navigation-hidden .docs-main" in site_css
    assert ".site-nav-restore" in site_css
    assert ".page-toc.is-open" in site_css
    assert "docs-page--lineage" in lineage_page
    assert "Context 与适配器" in root_lineage_page
    assert "Accessor 接口" in root_lineage_page
    # The DAG remains available from the plugin index, but is intentionally not
    # duplicated as a standalone sidebar item.
    assert 'href="lineage.html">独立查看</a>' in plugin_index
    assert 'href="lineage.html" aria-current="page"' not in root_lineage_page
    assert "docs-main--wide" in plugin_index
    lineage_page = result["LINEAGE_INDEX"].read_text(encoding="utf-8")
    assert "data-react-lineage" in lineage_page
    assert re.search(r'src="../assets/react/waveform-docs\.js\?v=[0-9a-f]{12}"', lineage_page)
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
            "adapters/index.html",
            "adapters/adapter.html",
            "visualizations/index.html",
            "visualizations/statistical-plots.html",
            "visualizations/waveform-plots.html",
            "architecture/index.html",
            "architecture/system.html",
            "architecture/plugin-dag-lineage-cache.html",
            "architecture/data-products.html",
            "architecture/accessor-analysis.html",
        )
        for page in pages:
            with urlopen(urljoin(base_url, page)) as response:
                assert response.status == 200
                html = response.read().decode("utf-8")
            for navigation_label in (
                "文档概览",
                "Context 与适配器",
                "Context",
                "DAQ 适配器",
                "插件系统",
                "插件系统",
                "Accessor 接口",
                "PeakChannelAccessor",
                "S1S2PairAccessor",
                "可视化",
                "统计图",
                "波形图",
                "系统架构与数据模型",
            ):
                assert navigation_label in html
            assert "index.htmlstatistical-plots.html" not in html
            assert "index.htmlwaveform-plots.html" not in html
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


def test_context_page_covers_all_public_methods():
    """Context 文档页必须覆盖 Context 的所有公开方法（不含 _ 开头和 dunder）。"""
    from waveform_analysis.utils.site_doc_generator import CONTEXT_DOCUMENTATION_PAGE

    public_methods = {
        name
        for name, _ in inspect.getmembers(Context, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    documented = {
        member.name for group in CONTEXT_DOCUMENTATION_PAGE.groups for member in group.members
    }
    missing = public_methods - documented
    assert not missing, f"未收录的公开方法: {sorted(missing)}"
