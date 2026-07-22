"""Structured Context help for terminals and rich notebook display."""

from dataclasses import replace
from html import escape
from typing import Any

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.utils.plugin_doc_generator import (
    PluginDocGenerator,
    PluginDocumentationView,
)

export, __all__ = exporter()


@export
class HelpDocument(str):
    """Plain-text help with a read-only HTML representation for Jupyter."""

    def __new__(cls, text: str, html_fragment: str):
        instance = super().__new__(cls, text)
        object.__setattr__(instance, "_html_fragment", html_fragment)
        return instance

    @property
    def html_fragment(self) -> str:
        return self._html_fragment

    def _repr_html_(self) -> str:
        return self._html_fragment


STATIC_TOPICS = {
    "config": ("Configuration", "docs/features/context/CONFIGURATION.md"),
    "performance": ("Performance", "docs/features/advanced/EXECUTOR_MANAGER_GUIDE.md"),
    "examples": ("Examples", "docs/user-guide/EXAMPLES_GUIDE.md"),
}


def _is_jupyter() -> bool:
    try:
        from IPython import get_ipython

        shell = get_ipython()
    except (ImportError, NameError):
        return False
    if shell is None:
        return False
    return shell.__class__.__name__ == "ZMQInteractiveShell" or hasattr(shell, "kernel")


def _plugin_plain(view: PluginDocumentationView, dependency_mode: str) -> str:
    dependencies = []
    for dep in view.depends_on:
        if isinstance(dep, tuple):
            dependencies.append(f"{dep[0]} ({dep[1]})")
        else:
            dependencies.append(str(dep))
    configs = ", ".join(option.name for option in view.config_options) or "-"
    fields = ", ".join(field.name for field in view.output_fields) or "-"
    return (
        f"Plugin: {view.provides}\n"
        f"Class: {view.name}\n"
        f"Version: {view.version}\n"
        f"Module: {view.module_path}\n"
        f"Summary: {view.summary or '-'}\n"
        f"Dependencies ({dependency_mode}): {', '.join(dependencies) or '-'}\n"
        f"Configuration: {configs}\n"
        f"Output: {view.output_kind} ({fields})"
    )


def _plugin_html(view: PluginDocumentationView, dependency_mode: str) -> str:
    dependencies = (
        "".join(
            f"<li><code>{escape(str(dep[0] if isinstance(dep, tuple) else dep))}</code></li>"
            for dep in view.depends_on
        )
        or "<li>-</li>"
    )
    config_rows = (
        "".join(
            "<tr>"
            f"<td><code>{escape(option.name)}</code></td>"
            f"<td>{escape(option.type)}</td>"
            f"<td><code>{escape(str(option.default))}</code></td>"
            f"<td>{escape(option.doc or '-')}</td>"
            "</tr>"
            for option in view.config_options
        )
        or '<tr><td colspan="4">-</td></tr>'
    )
    output_rows = "".join(
        "<tr>"
        f"<td><code>{escape(field.name)}</code></td>"
        f"<td><code>{escape(field.dtype)}</code></td>"
        f"<td>{escape(field.doc or '-')}</td>"
        "</tr>"
        for field in view.output_fields
    ) or (
        f"<tr><td>-</td><td><code>{escape(view.output_kind)}</code></td>"
        f"<td>{escape(view.summary or '-')}</td></tr>"
    )
    return (
        '<article class="waveform-help">'
        f"<h2>{escape(view.provides)}</h2>"
        f"<p>{escape(view.description or '-')}</p>"
        "<table><tbody>"
        f"<tr><th>Class</th><td><code>{escape(view.name)}</code></td></tr>"
        f"<tr><th>Version</th><td><code>{escape(view.version)}</code></td></tr>"
        f"<tr><th>Module</th><td><code>{escape(view.module_path)}</code></td></tr>"
        "</tbody></table>"
        f"<h3>Dependencies ({escape(dependency_mode)})</h3><ul>{dependencies}</ul>"
        "<h3>Configuration</h3><table><thead><tr><th>Name</th><th>Type</th>"
        f"<th>Default</th><th>Description</th></tr></thead><tbody>{config_rows}</tbody></table>"
        "<h3>Output</h3><table><thead><tr><th>Field</th><th>DType</th>"
        f"<th>Meaning</th></tr></thead><tbody>{output_rows}</tbody></table>"
        "</article>"
    )


def _plugin_view(
    context: Any, provides: str, run_id: str | None
) -> tuple[PluginDocumentationView, str]:
    plugin = context._plugins[provides]
    view = PluginDocGenerator().extract_doc_info(type(plugin), plugin)
    if run_id is None:
        return view, "declared"
    try:
        dependencies = context._plugin_domain.get_depends_on(plugin, run_id=run_id)
        return replace(view, depends_on=list(dependencies)), "resolved"
    except Exception:
        return (
            replace(view, depends_on=list(getattr(plugin, "depends_on", []) or [])),
            "declared fallback",
        )


@export
def build_context_help(
    context: Any,
    topic: str | None = None,
    *,
    run_id: str | None = None,
) -> HelpDocument:
    """Build Context help without executing plugin data or mutating the Context."""
    plugin_topic = topic[7:] if topic and topic.startswith("plugin:") else None
    if plugin_topic in context._plugins:
        view, dependency_mode = _plugin_view(context, plugin_topic, run_id)
        return HelpDocument(
            _plugin_plain(view, dependency_mode), _plugin_html(view, dependency_mode)
        )

    if topic == "plugins":
        names = sorted(context._plugins)
        text = "Registered plugins:\n" + "\n".join(f"- {name}" for name in names)
        items = "".join(f"<li><code>{escape(name)}</code></li>" for name in names) or "<li>-</li>"
        return HelpDocument(text, f"<h2>Registered plugins</h2><ul>{items}</ul>")

    if topic in STATIC_TOPICS:
        title, path = STATIC_TOPICS[topic]
        text = f"{title}\nDocumentation: {path}"
        html = f"<h2>{escape(title)}</h2><p>Documentation: <code>{escape(path)}</code></p>"
        return HelpDocument(text, html)

    if topic in context._plugins:
        view, dependency_mode = _plugin_view(context, topic, run_id)
        return HelpDocument(
            _plugin_plain(view, dependency_mode), _plugin_html(view, dependency_mode)
        )

    if topic is not None:
        available = ", ".join([*STATIC_TOPICS, "plugins", "plugin:<provides>"])
        text = f"Unknown help topic: {topic!r}\nAvailable topics: {available}"
        html = (
            f"<h2>Unknown help topic</h2><p><code>{escape(topic)}</code></p>"
            f"<p>Available topics: {escape(available)}</p>"
        )
        return HelpDocument(text, html)

    text = (
        "WaveformAnalysis help\n"
        "Topics: config, plugins, performance, examples\n"
        "Use ctx.help('<provides>') or ctx.help('plugin:<provides>') for a registered plugin."
    )
    html = (
        "<h2>WaveformAnalysis help</h2>"
        "<p>Topics: <code>config</code>, <code>plugins</code>, <code>performance</code>, "
        "<code>examples</code></p>"
        "<p>Use <code>ctx.help('&lt;provides&gt;')</code> for a registered plugin.</p>"
    )
    return HelpDocument(text, html)


@export
def show_context_help(document: HelpDocument) -> HelpDocument:
    """Print in terminals; leave rich display to Jupyter's displayhook."""
    if not _is_jupyter():
        print(document)
    return document
