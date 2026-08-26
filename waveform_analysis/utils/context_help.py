"""Structured Context help for terminals and rich notebook display."""

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
    "performance": ("Performance", "docs/architecture/ARCHITECTURE.md#执行器管理框架"),
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
    dependency_lines = [
        f"- {detail.name}"
        f"{f' ({detail.version_constraint})' if detail.version_constraint else ''}: "
        f"{detail.description or 'No producer description available.'}"
        for detail in view.dependency_details
    ] or ["- -"]
    workflow_lines = [
        f"{index}. {step}" for index, step in enumerate(view.workflow_steps, start=1)
    ] or ["- -"]
    config_lines = [
        f"- {option.name} ({option.type}, default={option.default}): "
        f"{view.config_notes.get(option.name, option.doc or 'No description available.')}"
        for option in view.config_options
    ] or ["- -"]
    output_lines = [
        f"- {field.name} ({field.dtype}): "
        f"{field.doc or view.field_notes.get(field.name, 'No field description available.')}"
        for field in view.output_fields
    ] or [f"- {view.output_kind}: {view.output_summary}"]
    downstream = ", ".join(view.downstream_consumers) or "terminal output / no registered consumer"
    dependency_names = ", ".join(detail.name for detail in view.dependency_details) or "-"
    fallback = _fallback_plain(view)
    return (
        f"Plugin: {view.provides}\n"
        f"Class: {view.name}\n"
        f"Version: {view.version}\n"
        f"Module: {view.module_path}\n"
        f"Summary: {view.summary or '-'}\n"
        + (
            f"\nOverview:\n{'\n\n'.join(view.overview_paragraphs)}\n"
            if view.overview_paragraphs
            else (f"\nOverview:\n{view.overview}\n" if view.overview else "")
        )
        + f"\nDependencies ({dependency_mode}): {dependency_names}\n"
        "\nHow it works:\n"
        + "\n".join(workflow_lines)
        + "\nDependencies:\n"
        + "\n".join(dependency_lines)
        + "\n\nConfiguration and behavior:\n"
        + "\n".join(config_lines)
        + f"\n\nOutput ({view.output_kind}): {view.output_summary}\n"
        + "\n".join(output_lines)
        + f"\n\nDownstream consumers: {downstream}\n{fallback}"
    )


def _plugin_html(view: PluginDocumentationView, dependency_mode: str) -> str:
    workflow_items = (
        "".join(f"<li>{escape(step)}</li>" for step in view.workflow_steps) or "<li>-</li>"
    )
    dependencies = (
        "".join(
            "<tr>"
            f"<td><code>{escape(detail.name)}</code></td>"
            f"<td>{escape(detail.version_constraint or '-')}</td>"
            f"<td>{escape(detail.resolution)}</td>"
            f"<td>{escape(', '.join(detail.required_fields) or '-')}</td>"
            f"<td>{escape(detail.description or 'No producer description available.')}</td>"
            "</tr>"
            for detail in view.dependency_details
        )
        or '<tr><td colspan="5">-</td></tr>'
    )
    config_rows = (
        "".join(
            "<tr>"
            f"<td><code>{escape(option.name)}</code></td>"
            f"<td>{escape(option.type)}</td>"
            f"<td><code>{escape(str(option.default))}</code></td>"
            f"<td>{escape(view.config_notes.get(option.name, option.doc or 'No description available.'))}</td>"
            "</tr>"
            for option in view.config_options
        )
        or '<tr><td colspan="4">-</td></tr>'
    )
    output_rows = "".join(
        "<tr>"
        f"<td><code>{escape(field.name)}</code></td>"
        f"<td><code>{escape(field.dtype)}</code></td>"
        f"<td>{escape(field.doc or view.field_notes.get(field.name, 'No field description available.'))}</td>"
        "</tr>"
        for field in view.output_fields
    ) or (
        f"<tr><td>-</td><td><code>{escape(view.output_kind)}</code></td>"
        f"<td>{escape(view.summary or '-')}</td></tr>"
    )
    downstream = (
        "".join(f"<li><code>{escape(item)}</code></li>" for item in view.downstream_consumers)
        or "<li>Terminal output / no registered consumer</li>"
    )
    fallback = _fallback_html(view)
    return (
        '<article class="waveform-help">'
        f"<h2>{escape(view.provides)}</h2>"
        f"<p>{escape(view.description or '-')}</p>"
        + (
            (
                '<div class="plugin-overview">'
                + "".join(f"<p>{escape(p)}</p>" for p in view.overview_paragraphs)
                + "</div>"
            )
            if view.overview_paragraphs
            else (
                f'<div class="plugin-overview"><p>{escape(view.overview)}</p></div>'
                if view.overview
                else ""
            )
        )
        + "<table><tbody>"
        f"<tr><th>Class</th><td><code>{escape(view.name)}</code></td></tr>"
        f"<tr><th>Version</th><td><code>{escape(view.version)}</code></td></tr>"
        f"<tr><th>Module</th><td><code>{escape(view.module_path)}</code></td></tr>"
        "</tbody></table>"
        f"<h3>How it works</h3><ol>{workflow_items}</ol>"
        "<h3>Dependencies</h3><table><thead><tr><th>Dependency</th>"
        "<th>Version Constraint</th><th>Resolution</th><th>Required Fields</th>"
        f"<th>Description</th></tr></thead><tbody>{dependencies}</tbody></table>"
        "<h3>Configuration</h3><table><thead><tr><th>Name</th><th>Type</th>"
        f"<th>Default</th><th>Description</th></tr></thead><tbody>{config_rows}</tbody></table>"
        f"<h3>Output</h3><p>{escape(view.output_summary)}</p>"
        "<table><thead><tr><th>Field</th><th>DType</th>"
        f"<th>Meaning</th></tr></thead><tbody>{output_rows}</tbody></table>"
        f"<h3>Downstream consumers</h3><ul>{downstream}</ul>{fallback}"
        "</article>"
    )


def _fallback_plain(view: PluginDocumentationView) -> str:
    status = view.documentation_status
    if getattr(status, "source", None) != "source_fallback":
        return ""
    return f"\nDocumentation note: using source agent_doc because {status.reason}.\n"


def _fallback_html(view: PluginDocumentationView) -> str:
    status = view.documentation_status
    if getattr(status, "source", None) != "source_fallback":
        return ""
    return f'<p class="documentation-note">Using source agent_doc: {escape(status.reason or "published YAML was rejected")}.</p>'


def _plugin_view(
    context: Any, provides: str, run_id: str | None
) -> tuple[PluginDocumentationView, str]:
    plugin = context._plugins[provides]
    generator = PluginDocGenerator()
    available_views = [
        generator.extract_doc_info(type(registered), registered)
        for registered in context._plugins.values()
    ]
    available_views = generator.enrich_documentation_views(available_views)
    view = next(item for item in available_views if item.provides == provides)
    if run_id is None:
        return view, "declared"
    try:
        dependencies = context._plugin_domain.get_depends_on(plugin, run_id=run_id)
        return (
            generator.apply_dependency_resolution(
                view,
                list(dependencies),
                resolution="resolved",
                available_views=available_views,
            ),
            "resolved",
        )
    except Exception:
        dependencies = list(getattr(plugin, "depends_on", []) or [])
        return (
            generator.apply_dependency_resolution(
                view,
                dependencies,
                resolution="fallback",
                available_views=available_views,
            ),
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
