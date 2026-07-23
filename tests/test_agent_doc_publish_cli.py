from pathlib import Path

import yaml

from waveform_analysis.documentation import DocumentationOrchestrator, FileArtifactStore
from waveform_analysis.documentation.types import DAGState
from waveform_analysis.utils.cli_docs import main


def _state(tmp_path: Path, *, current_node: str = "publish_agent_doc") -> FileArtifactStore:
    store = FileArtifactStore(tmp_path / "artifacts")
    source = tmp_path / "plugin.py"
    source.write_text("class Plugin: pass\n", encoding="utf-8")
    state = DAGState(
        plugin_name="example",
        repository_root=str(tmp_path),
        current_node=current_node,
        history=[
            {
                "node_id": "verify_agent_doc",
                "status": "passed",
                "next_node": "publish_agent_doc",
            }
        ],
        artifacts={
            "plugin_manifest": {"source_file": "plugin.py"},
            "plugin_facts": {"identity": {"version": "1.0.0"}},
            "agent_doc": {
                "plugin_name": "example",
                "summary": "Verified summary.",
                "steps": ["Verified step."],
                "edge_cases": [],
            },
            "verification_report": {"passed": True},
        },
    )
    store.save_state("example", state.__dict__)
    for name, artifact in state.artifacts.items():
        store.save_artifact("example", name, artifact)
    return store


def test_agent_doc_publish_cli_writes_atomically_and_marks_terminal(tmp_path: Path, monkeypatch):
    store = _state(tmp_path)
    output = tmp_path / "published"
    monkeypatch.setattr(
        "sys.argv",
        [
            "waveform-docs",
            "agent-doc",
            "publish",
            "--plugin",
            "example",
            "--artifact-store",
            str(store.root),
            "--output",
            str(output),
        ],
    )

    assert main() == 0
    document = yaml.safe_load((output / "example.yaml").read_text(encoding="utf-8"))
    assert document["content"]["summary"] == "Verified summary."
    assert store.load_state("example")["current_node"] == "terminal"


def test_agent_doc_publish_cli_rejects_non_publish_state_without_replacing_file(
    tmp_path: Path, monkeypatch
):
    store = _state(tmp_path, current_node="verify_agent_doc")
    output = tmp_path / "published"
    output.mkdir()
    existing = output / "example.yaml"
    existing.write_text("old: document\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "waveform-docs",
            "agent-doc",
            "publish",
            "--plugin",
            "example",
            "--artifact-store",
            str(store.root),
            "--output",
            str(output),
        ],
    )

    assert main() == 1
    assert existing.read_text(encoding="utf-8") == "old: document\n"


def test_agent_doc_publish_cli_rejects_missing_verification_history(tmp_path: Path, monkeypatch):
    store = _state(tmp_path)
    state = store.load_state("example")
    state["history"] = []
    store.save_state("example", state)
    monkeypatch.setattr(
        "sys.argv",
        [
            "waveform-docs",
            "agent-doc",
            "publish",
            "--plugin",
            "example",
            "--artifact-store",
            str(store.root),
            "--output",
            str(tmp_path / "published"),
        ],
    )
    assert main() == 1
    assert not (tmp_path / "published" / "example.yaml").exists()
