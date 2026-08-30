"""Machine-executable, evidence-backed plugin documentation workflows."""

from importlib import import_module

from .artifact_store import FileArtifactStore
from .contract_facts import extract_plugin_contract
from .orchestrator import DocumentationOrchestrator, load_plugin_documentation_dag
from .published_agent_docs import (
    DocumentationStatus,
    NarrativeDoc,
    PublishedAgentDocRegistry,
    fingerprint_plugin_source,
)
from .types import NodeExecutionRequest, NodeExecutionResult

__all__ = [
    "DocumentationOrchestrator",
    "DocumentationSiteGenerator",
    "DocumentationStatus",
    "FileArtifactStore",
    "extract_plugin_contract",
    "NarrativeDoc",
    "NodeExecutionRequest",
    "NodeExecutionResult",
    "PluginDocGenerator",
    "PublishedAgentDocRegistry",
    "fingerprint_plugin_source",
    "load_plugin_documentation_dag",
]

_LAZY_ATTRS = {
    "DocumentationSiteGenerator": (".site_doc_generator", "DocumentationSiteGenerator"),
    "PluginDocGenerator": (".plugin_doc_generator", "PluginDocGenerator"),
}


def __getattr__(name: str):
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        value = getattr(import_module(module_name, __name__), attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(_LAZY_ATTRS))
