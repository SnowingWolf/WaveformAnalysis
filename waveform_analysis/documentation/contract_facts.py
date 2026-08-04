"""Extract source-backed contracts for deterministic AgentDoc validation."""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Any


def extract_plugin_contract(plugin_class: type, plugin: Any) -> dict[str, Any]:
    """Return serializable contract facts without executing the plugin."""
    options = getattr(plugin, "options", {}) or {}
    option_facts = [
        {"name": str(name), "default": str(option.default)} for name, option in options.items()
    ]
    option_names = {item["name"] for item in option_facts}
    output_schema = getattr(plugin, "output_schema", None)
    output_kind = getattr(output_schema, "kind", None) or "structured_array"
    return_annotation = inspect.signature(plugin_class.compute).return_annotation
    annotation = "" if return_annotation is inspect.Signature.empty else str(return_annotation)
    return {
        "output": {"kind": str(output_kind), "annotation": annotation},
        "options": option_facts,
        "dependencies": _dependency_names(getattr(plugin, "depends_on", []) or []),
        "calls": _returned_calls(plugin_class, option_names),
    }


def _dependency_names(dependencies: list[Any]) -> list[str]:
    return [str(item[0] if isinstance(item, tuple) else item) for item in dependencies]


def _returned_calls(plugin_class: type, option_names: set[str]) -> list[dict[str, Any]]:
    """Capture only direct return calls, the public operation documented in steps."""
    try:
        source = textwrap.dedent(inspect.getsource(plugin_class.compute))
        tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError):
        return []

    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Call):
            continue
        name = _call_name(node.value.func)
        if not name:
            continue
        keywords = [keyword.arg for keyword in node.value.keywords if keyword.arg]
        option_arguments = [
            keyword.arg
            for keyword in node.value.keywords
            if keyword.arg
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id in option_names
        ]
        calls.append(
            {
                "name": name,
                "keyword_arguments": keywords,
                "option_arguments": option_arguments,
            }
        )
    return calls


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""
