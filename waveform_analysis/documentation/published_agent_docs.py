"""Read verified, package-distributed AgentDocs without executing plugins."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import inspect
from pathlib import Path
from typing import Any, Literal

import yaml

PACKAGE_ROOT = Path(__file__).parent
PUBLISHED_AGENT_DOC_DIR = PACKAGE_ROOT / "agent_docs"
PUBLISHED_AGENT_DOC_SCHEMA_VERSION = 1
PUBLISHED_AGENT_DOC_TYPE = "published_agent_doc"


@dataclass(frozen=True)
class NarrativeDoc:
    """The authored fields shared by source metadata and published YAML."""

    overview: str = ""
    workflow_steps: tuple[str, ...] = ()
    behavior_notes: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    execution_notes: tuple[str, ...] = ()
    dependency_notes: dict[str, str] | None = None
    dependency_fields: dict[str, tuple[str, ...]] | None = None
    field_notes: dict[str, str] | None = None
    config_notes: dict[str, str] | None = None
    cluster_contract: tuple[str, ...] = ()
    downstream_consumers: tuple[str, ...] = ()
    downstream_notes: tuple[str, ...] = ()
    agent_change_notes: tuple[str, ...] = ()
    workflow_diagram: str = ""  # mermaid flowchart 源码（插件内部处理流程）

    @classmethod
    def from_source(cls, value: Any) -> NarrativeDoc:
        raw = value if isinstance(value, dict) else {}
        return cls(
            overview=_string(raw.get("overview")),
            workflow_steps=_strings(raw.get("workflow_steps")),
            behavior_notes=_strings(raw.get("behavior_notes")),
            failure_modes=_strings(raw.get("failure_modes")),
            execution_notes=_strings(raw.get("execution_notes")),
            dependency_notes=_string_map(raw.get("dependency_notes")),
            dependency_fields=_string_list_map(raw.get("dependency_fields")),
            field_notes=_string_map(raw.get("field_notes")),
            config_notes=_string_map(raw.get("config_notes")),
            cluster_contract=_strings(raw.get("cluster_contract")),
            downstream_consumers=_strings(raw.get("downstream_consumers")),
            downstream_notes=_strings(raw.get("downstream_notes")),
            agent_change_notes=_strings(raw.get("agent_change_notes")),
            workflow_diagram=_string(raw.get("workflow_diagram")),
        )

    def overlay(self, content: dict[str, Any]) -> NarrativeDoc:
        """Overlay only published keys; omitted keys retain authored source text."""
        updates: dict[str, Any] = {}
        mappings = {
            "summary": ("overview", _string),
            "overview": ("overview", _string),
            "steps": ("workflow_steps", _strings),
            "edge_cases": ("failure_modes", _strings),
            "operational_notes": ("behavior_notes", _strings),
        }
        for published_name, (field_name, convert) in mappings.items():
            if published_name in content:
                updates[field_name] = convert(content[published_name])
        return self if not updates else _replace_narrative(self, **updates)

    def as_generator_fields(self) -> dict[str, Any]:
        return {
            "overview": self.overview,
            "workflow_steps": list(self.workflow_steps),
            "behavior_notes": list(self.behavior_notes),
            "failure_modes": list(self.failure_modes),
            "execution_notes": list(self.execution_notes),
            "dependency_notes": dict(self.dependency_notes or {}),
            "dependency_fields": {
                key: list(value) for key, value in (self.dependency_fields or {}).items()
            },
            "field_notes": dict(self.field_notes or {}),
            "config_notes": dict(self.config_notes or {}),
            "cluster_contract": list(self.cluster_contract),
            "downstream_consumers": list(self.downstream_consumers),
            "downstream_notes": list(self.downstream_notes),
            "agent_change_notes": list(self.agent_change_notes),
            "workflow_diagram": self.workflow_diagram,
        }


@dataclass(frozen=True)
class DocumentationStatus:
    """Provenance of the narrative selected for one plugin."""

    source: Literal["published", "source", "source_fallback"]
    reason: str | None = None


@dataclass(frozen=True)
class PublishedAgentDocResolution:
    narrative: NarrativeDoc
    status: DocumentationStatus


def fingerprint_plugin_source(plugin_class: type) -> str | None:
    """Return the SHA-256 of the plugin's defining source file, if available."""
    source_file = inspect.getsourcefile(plugin_class)
    if source_file is None:
        return None
    try:
        return hashlib.sha256(Path(source_file).read_bytes()).hexdigest()
    except OSError:
        return None


class PublishedAgentDocRegistry:
    """Resolve current published narrative docs with source metadata as a fallback."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root is not None else PUBLISHED_AGENT_DOC_DIR

    def resolve_for_plugin(self, plugin_class: type, plugin: Any) -> PublishedAgentDocResolution:
        source = NarrativeDoc.from_source(getattr(plugin, "agent_doc", {}))
        provides = getattr(plugin, "provides", None)
        if not isinstance(provides, str) or not provides:
            return PublishedAgentDocResolution(source, DocumentationStatus("source"))
        path = self.root / f"{provides}.yaml"
        if not path.exists():
            return PublishedAgentDocResolution(source, DocumentationStatus("source"))
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return PublishedAgentDocResolution(
                source, DocumentationStatus("source_fallback", "published YAML is unreadable")
            )
        reason = self._rejection_reason(raw, plugin_class, plugin)
        if reason is not None:
            return PublishedAgentDocResolution(
                source, DocumentationStatus("source_fallback", reason)
            )
        return PublishedAgentDocResolution(
            source.overlay(raw["content"]), DocumentationStatus("published")
        )

    def load_for_plugin(self, plugin_class: type, plugin: Any) -> dict[str, Any] | None:
        """Compatibility API returning selected fields only for a valid publication."""
        resolution = self.resolve_for_plugin(plugin_class, plugin)
        if resolution.status.source != "published":
            return None
        return resolution.narrative.as_generator_fields()

    @staticmethod
    def _rejection_reason(raw: Any, plugin_class: type, plugin: Any) -> str | None:
        if not isinstance(raw, dict):
            return "published YAML is not a mapping"
        if raw.get("schema_version") != PUBLISHED_AGENT_DOC_SCHEMA_VERSION:
            return "published YAML schema version does not match"
        if raw.get("document_type") != PUBLISHED_AGENT_DOC_TYPE:
            return "published YAML document type does not match"
        if raw.get("plugin_name") != getattr(plugin, "provides", None):
            return "published YAML belongs to another plugin"
        if str(raw.get("plugin_version", "")) != str(getattr(plugin, "version", "")):
            return "published YAML plugin version does not match"
        fingerprint = fingerprint_plugin_source(plugin_class)
        if fingerprint is None or raw.get("source_fingerprint") != fingerprint:
            return "published YAML source fingerprint does not match"
        if not _is_valid_content(raw.get("content")):
            return "published YAML content does not match the schema"
        return None


def _replace_narrative(value: NarrativeDoc, **updates: Any) -> NarrativeDoc:
    fields = {name: getattr(value, name) for name in value.__dataclass_fields__}
    fields.update(updates)
    return NarrativeDoc(**fields)


def _is_valid_content(content: Any) -> bool:
    return (
        isinstance(content, dict)
        and isinstance(content.get("summary"), str)
        and isinstance(content.get("steps"), list)
        and isinstance(content.get("edge_cases"), list)
        and all(isinstance(item, str) for item in content["steps"])
        and all(isinstance(item, str) for item in content["edge_cases"])
    )


def _string(value: Any) -> str:
    return "" if value is None else str(value)


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return (str(value),)


def _string_map(value: Any) -> dict[str, str]:
    return {str(key): str(item) for key, item in value.items()} if isinstance(value, dict) else {}


def _string_list_map(value: Any) -> dict[str, tuple[str, ...]]:
    return (
        {str(key): _strings(item) for key, item in value.items()} if isinstance(value, dict) else {}
    )
