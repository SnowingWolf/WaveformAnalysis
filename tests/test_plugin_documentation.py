from functools import partial
from http.server import ThreadingHTTPServer
import inspect
import json
from threading import Thread
from urllib.request import urlopen

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.plugins.core.spec import FieldSpec, OutputSchema
from waveform_analysis.documentation.plugin_doc_generator import (
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
    assert "schema_version: 2" in auto
    assert 'profile: "auto"' in auto
    assert "| - | - | - | - | - |" in auto
    assert "| - | - | - | - | - | - | 此插件没有插件级配置。 |" in auto
    assert "## Operational Notes" not in auto
    assert "### Behavior" in agent
    assert "### Validation" in agent
    legacy = auto.replace("schema_version: 2", "schema_version: 1", 1)
    assert any(
        "schema_version" in error for error in check_plugin_document_structure(legacy, "auto")
    )


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


def test_lineage_payload_rejects_dangling_port_with_edge_id():
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
    plugins = generator._with_lineage_scores(
        generator.get_all_doc_info(), dependencies_by_provides=dependencies
    )
    detail = generator._build_detail_lineage_relations(plugins, dependencies)

    assert detail["target_rows"] == {
        "inputs": ["middle_rows"],
        "consumers": ["consumer_rows"],
    }


def test_documentation_completeness_excludes_inapplicable_sections_from_denominator():
    generator = PluginDocGenerator()
    view = generator.extract_doc_info(_EmptyPlugin, _EmptyPlugin())

    scored = generator._with_lineage_scores([view])[0]

    assert scored.documentation_completeness == 100
    assert scored.dag_impact == 0


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


def test_dynamic_lineage_endpoint_serves_context_payload(tmp_path):
    from waveform_analysis.documentation import cli as cli_docs

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

    try:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            partial(
                cli_docs._DocumentationRequestHandler,
                directory=str(site),
                lineage_payload_provider=provider,
            ),
        )
    except PermissionError as exc:
        pytest.skip(f"socket creation is unavailable in this environment: {exc}")
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

    from waveform_analysis.documentation import cli as cli_docs

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
    assert provider()["nodes"][0]["id"] == "factory_source"
    with pytest.raises(ValueError, match="package.module:function"):
        cli_docs._lineage_payload_provider("not-a-factory")


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
    from waveform_analysis.documentation.site_docs import CONTEXT_DOCUMENTATION_PAGE

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
