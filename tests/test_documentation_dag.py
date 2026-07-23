from importlib.resources import files
from pathlib import Path

import pytest
import yaml

from waveform_analysis.documentation import DocumentationOrchestrator, FileArtifactStore
from waveform_analysis.documentation.types import NodeExecutionResult


def _result(node_id: str, status: str, artifact_type: str | None, artifact: dict | None):
    return NodeExecutionResult(
        dag_name="plugin_documentation",
        dag_version=1,
        node_id=node_id,
        node_status=status,
        artifact_type=artifact_type,
        artifact=artifact,
        issues=[],
        requested_evidence=[],
        confidence="high",
    )


def test_discovery_result_is_validated_persisted_and_routed(tmp_path: Path):
    store = FileArtifactStore(tmp_path / "artifacts")
    orchestrator = DocumentationOrchestrator(artifact_store=store)
    state = orchestrator.new_state("hit_merged", tmp_path)

    request = orchestrator.build_request(state)
    assert request.node_id == "discover_plugin"
    assert request.executor == "deterministic"
    assert request.input_artifacts["plugin_name"] == {"value": "hit_merged"}

    state = orchestrator.accept_result(
        state,
        _result(
            "discover_plugin",
            "success",
            "PluginManifest",
            {
                "plugin_name": "hit_merged",
                "class_name": "HitMergePlugin",
                "source_file": "waveform_analysis/core/plugins/builtin/hit/hit_merge.py",
            },
        ),
    )
    assert state.current_node == "collect_context"
    assert store.load_artifact("hit_merged", "plugin_manifest") is not None
    assert store.load_state("hit_merged")["current_node"] == "collect_context"


def test_agent_request_is_node_scoped_and_contains_only_declared_artifacts(tmp_path: Path):
    orchestrator = DocumentationOrchestrator()
    state = orchestrator.new_state("hit_merged", tmp_path)
    state.current_node = "recover_semantics"
    state.artifacts = {
        "plugin_context": {"plugin_name": "hit_merged", "evidence": []},
        "plugin_facts": {
            "identity": {"plugin_name": "hit_merged"},
            "configuration": {},
            "output_fields": [],
        },
        "agent_doc": {"unexpected": True},
    }

    request = orchestrator.build_request(state)
    assert request.role == "semantic_analyzer"
    assert set(request.input_artifacts) == {"plugin_context", "plugin_facts"}
    assert "You must not write final user-facing documentation" in request.prompt
    assert "<plugin_context>" in request.prompt
    assert "unexpected" not in request.prompt


def test_missing_evidence_routes_back_to_context_collection(tmp_path: Path):
    orchestrator = DocumentationOrchestrator()
    state = orchestrator.new_state("hit_merged", tmp_path)
    state.current_node = "recover_semantics"
    state.artifacts = {
        "plugin_context": {"plugin_name": "hit_merged", "evidence": []},
        "plugin_facts": {"identity": {}, "configuration": {}, "output_fields": []},
    }
    result = _result("recover_semantics", "missing_evidence", "PluginSemanticSpec", None)
    result = NodeExecutionResult(
        **{**result.__dict__, "requested_evidence": [{"type": "input_dtype"}]}
    )

    state = orchestrator.accept_result(state, result)
    assert state.current_node == "collect_context"
    assert "semantic_spec" not in state.artifacts


def test_successful_semantics_result_requires_declared_schema_fields(tmp_path: Path):
    orchestrator = DocumentationOrchestrator()
    state = orchestrator.new_state("hit_merged", tmp_path)
    state.current_node = "recover_semantics"
    state.artifacts = {
        "plugin_context": {"plugin_name": "hit_merged", "evidence": []},
        "plugin_facts": {"identity": {}, "configuration": {}, "output_fields": []},
    }

    with pytest.raises(ValueError, match="Missing required artifact field: processing_unit"):
        orchestrator.accept_result(
            state,
            _result(
                "recover_semantics", "success", "PluginSemanticSpec", {"plugin_name": "hit_merged"}
            ),
        )


def test_semantic_result_requires_evidence_and_origin_separation(tmp_path: Path):
    orchestrator = DocumentationOrchestrator()
    state = orchestrator.new_state("hit_merged", tmp_path)
    state.current_node = "recover_semantics"
    state.artifacts = {
        "plugin_context": {"plugin_name": "hit_merged", "evidence": []},
        "plugin_facts": {"identity": {}, "configuration": {}, "output_fields": []},
    }
    semantic_spec = {
        "plugin_name": "hit_merged",
        "processing_unit": {"description": "Per-channel ordered hits."},
        "processing_steps": [{"description": "Merge candidates."}],
        "invariants": ["One hit belongs to one cluster."],
        "field_origins": {"cluster_derived": ["time_start"]},
        "decision_rules": [{"condition": "gap <= merge_gap", "evidence": []}],
    }

    with pytest.raises(ValueError) as exc_info:
        orchestrator.accept_result(
            state, _result("recover_semantics", "success", "PluginSemanticSpec", semantic_spec)
        )
    message = str(exc_info.value)
    assert "decision_rules[0] must include non-empty evidence" in message
    assert "processing_steps[0] must include non-empty evidence" in message
    assert "field_origins.anchor_copied must be an array" in message


def test_passing_verification_requires_zero_failure_counts(tmp_path: Path):
    orchestrator = DocumentationOrchestrator()
    state = orchestrator.new_state("hit_merged", tmp_path)
    state.current_node = "verify_agent_doc"
    state.artifacts = {
        "plugin_context": {"plugin_name": "hit_merged", "evidence": []},
        "plugin_facts": {"identity": {}, "configuration": {}, "output_fields": []},
        "semantic_spec": {"plugin_name": "hit_merged"},
        "agent_doc": {
            "plugin_name": "hit_merged",
            "summary": "Merge nearby hits.",
            "steps": [],
            "edge_cases": [],
        },
    }
    report = {
        "plugin_name": "hit_merged",
        "passed": True,
        "claims": [],
        "contradicted_claims": 1,
        "unsupported_critical_claims": 0,
        "blocking_ambiguities": 0,
    }

    with pytest.raises(ValueError, match="contradicted_claims == 0"):
        orchestrator.accept_result(
            state, _result("verify_agent_doc", "passed", "VerificationReport", report)
        )


def test_agent_doc_generation_is_blocked_by_prior_blocking_ambiguity(tmp_path: Path):
    orchestrator = DocumentationOrchestrator()
    state = orchestrator.new_state("hit_merged", tmp_path)
    state.current_node = "generate_agent_doc"
    state.artifacts = {
        "plugin_facts": {"identity": {}, "configuration": {}, "output_fields": []},
        "semantic_spec": {"plugin_name": "hit_merged"},
        "ambiguity_report": {
            "plugin_name": "hit_merged",
            "ambiguities": [],
            "blocking_ambiguities": [{"topic": "dt_unit"}],
        },
    }
    agent_doc = {
        "plugin_name": "hit_merged",
        "summary": "Merge nearby hits.",
        "steps": [],
        "edge_cases": [],
    }

    with pytest.raises(ValueError, match="blocking ambiguities"):
        orchestrator.accept_result(
            state, _result("generate_agent_doc", "success", "AgentDoc", agent_doc)
        )


def test_deterministic_runner_executes_one_declared_node(tmp_path: Path):
    orchestrator = DocumentationOrchestrator()
    state = orchestrator.new_state("hit_merged", tmp_path)

    state = orchestrator.execute_deterministic_node(
        state,
        lambda request: _result(
            request.node_id,
            "success",
            "PluginManifest",
            {
                "plugin_name": "hit_merged",
                "class_name": "HitMergePlugin",
                "source_file": "waveform_analysis/core/plugins/builtin/hit/hit_merge.py",
            },
        ),
    )
    assert state.current_node == "collect_context"


def test_publish_requires_passing_verification_and_writes_atomically(tmp_path: Path):
    orchestrator = DocumentationOrchestrator()
    state = orchestrator.new_state("hit_merged", tmp_path)
    source_file = tmp_path / "plugin.py"
    source_file.write_text("class HitMergePlugin: pass\n", encoding="utf-8")
    state.artifacts["plugin_manifest"] = {
        "plugin_name": "hit_merged",
        "class_name": "HitMergePlugin",
        "source_file": "plugin.py",
    }
    state.artifacts["plugin_facts"] = {"identity": {"version": "2.1.0"}}
    state.artifacts["agent_doc"] = {
        "plugin_name": "hit_merged",
        "summary": "Merge nearby threshold-hit fragments.",
        "steps": ["Keep one channel separate."],
        "edge_cases": [],
        "plugin_version": "2.1.0",
    }
    state.artifacts["verification_report"] = {"passed": False}
    with pytest.raises(ValueError, match="verification_report.passed"):
        orchestrator.publish(state, tmp_path / "published")

    state.artifacts["verification_report"] = {"passed": True}
    output = orchestrator.publish(state, tmp_path / "published")
    assert output == tmp_path / "published" / "hit_merged.yaml"
    published = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert published["plugin_name"] == "hit_merged"
    assert published["plugin_version"] == "2.1.0"
    assert published["document_type"] == "published_agent_doc"
    assert published["content"]["summary"] == "Merge nearby threshold-hit fragments."
    assert len(published["source_fingerprint"]) == 64
    assert not output.with_suffix(".yaml.tmp").exists()


def test_human_review_request_allows_unavailable_optional_artifacts(tmp_path: Path):
    orchestrator = DocumentationOrchestrator()
    state = orchestrator.new_state("missing_plugin", tmp_path)
    state.current_node = "human_review"
    request = orchestrator.build_request(state)
    assert request.executor == "human"
    assert request.input_artifacts == {}


def test_bundled_dag_resources_are_available_from_the_package():
    root = files("waveform_analysis.documentation")
    assert root.joinpath("dags/plugin_documentation.yaml").is_file()
    assert root.joinpath("schemas/PluginSemanticSpec.schema.json").is_file()
    assert root.joinpath("prompts/recover_semantics.md").is_file()
