from pathlib import Path

import numpy as np
import yaml

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.documentation import PublishedAgentDocRegistry, fingerprint_plugin_source
from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator


class _PublishedNarrativePlugin(Plugin):
    provides = "published_narrative"
    description = "Source contract description."
    version = "1.2.3"
    output_dtype = np.dtype([("value", "f4")])
    agent_doc = {
        "overview": "Source overview fallback.",
        "workflow_steps": ["Source workflow fallback."],
        "failure_modes": ["Source edge-case fallback."],
        "field_notes": {"value": "Source field note."},
        "config_notes": {"source_option": "Source config note."},
        "downstream_consumers": ["source_consumer"],
    }

    def compute(self, context, run_id, **kwargs):
        return np.zeros(0, dtype=self.output_dtype)


def _write_published_doc(root: Path, **overrides):
    document = {
        "schema_version": 1,
        "document_type": "published_agent_doc",
        "plugin_name": "published_narrative",
        "plugin_version": "1.2.3",
        "source_fingerprint": fingerprint_plugin_source(_PublishedNarrativePlugin),
        "generator_version": "test",
        "content": {
            "summary": "Verified DAG summary.",
            "overview": "Verified DAG overview.",
            "steps": ["Verified DAG workflow step."],
            "edge_cases": ["Verified DAG edge case."],
            "operational_notes": ["Verified operational note."],
        },
    }
    document.update(overrides)
    root.mkdir(parents=True, exist_ok=True)
    (root / "published_narrative.yaml").write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def test_matching_published_agent_doc_overrides_source_narrative_across_renderers(
    tmp_path, monkeypatch, capsys
):
    _write_published_doc(tmp_path)
    registry = PublishedAgentDocRegistry(tmp_path)
    generator = PluginDocGenerator(published_agent_docs=registry)
    view = generator.extract_doc_info(_PublishedNarrativePlugin, _PublishedNarrativePlugin())

    assert view.overview == "Verified DAG overview."
    assert view.workflow_steps == ["Verified DAG workflow step."]
    assert view.failure_modes == ["Verified DAG edge case."]
    assert view.field_notes == {"value": "Source field note."}
    assert view.config_notes == {"source_option": "Source config note."}
    assert view.downstream_consumers == ["source_consumer"]
    assert view.documentation_status.source == "published"
    for rendered in (
        generator.render_plugin_page(view, profile="auto"),
        generator.render_plugin_page(view, profile="agent"),
        generator.render_plugin_html(view),
    ):
        assert "Verified DAG overview." in rendered
        assert "Verified DAG workflow step." in rendered
        assert "Source workflow fallback." not in rendered

    monkeypatch.setattr(
        "waveform_analysis.documentation.PublishedAgentDocRegistry", lambda: registry
    )
    context = Context(storage_dir=str(tmp_path / "cache"))
    context.register(_PublishedNarrativePlugin())
    help_document = context.help("published_narrative")
    capsys.readouterr()
    assert "Verified DAG overview." in help_document
    assert "Verified DAG workflow step." in help_document
    assert "Source workflow fallback." not in help_document


def test_invalid_or_stale_published_docs_fall_back_to_source_agent_doc(tmp_path):
    cases = [
        {"plugin_version": "9.9.9"},
        {"source_fingerprint": "outdated"},
        {"content": {"summary": "Missing required lists."}},
    ]
    for index, override in enumerate(cases):
        root = tmp_path / str(index)
        _write_published_doc(root, **override)
        generator = PluginDocGenerator(published_agent_docs=PublishedAgentDocRegistry(root))
        view = generator.extract_doc_info(_PublishedNarrativePlugin, _PublishedNarrativePlugin())
        assert view.overview == "Source overview fallback."
    assert view.workflow_steps == ["Source workflow fallback."]
    assert view.documentation_status.source == "source_fallback"
    assert view.documentation_status.reason

    corrupt_root = tmp_path / "corrupt"
    corrupt_root.mkdir()
    (corrupt_root / "published_narrative.yaml").write_text("content: [\n", encoding="utf-8")
    generator = PluginDocGenerator(published_agent_docs=PublishedAgentDocRegistry(corrupt_root))
    view = generator.extract_doc_info(_PublishedNarrativePlugin, _PublishedNarrativePlugin())
    assert view.overview == "Source overview fallback."


def test_help_shows_rejected_published_doc_reason_but_static_renderers_do_not(
    tmp_path, monkeypatch
):
    _write_published_doc(tmp_path, source_fingerprint="outdated")
    registry = PublishedAgentDocRegistry(tmp_path)
    generator = PluginDocGenerator(published_agent_docs=registry)
    view = generator.extract_doc_info(_PublishedNarrativePlugin, _PublishedNarrativePlugin())
    assert "documentation-note" not in generator.render_plugin_html(view)
    assert "source fingerprint does not match" not in generator.render_plugin_page(view)

    monkeypatch.setattr(
        "waveform_analysis.documentation.PublishedAgentDocRegistry", lambda: registry
    )
    context = Context(storage_dir=str(tmp_path / "cache"))
    context.register(_PublishedNarrativePlugin())
    help_document = context.help("published_narrative")
    assert "Documentation note: using source agent_doc" in help_document
    assert "source fingerprint does not match" in help_document
    assert "documentation-note" in help_document.html_fragment
