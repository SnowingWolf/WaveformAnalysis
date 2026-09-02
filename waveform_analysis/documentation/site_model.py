"""Build the versioned, HTML-free input model for the documentation site.

The Python documentation package remains the source of truth for facts which are
shown by the static site.  This module deliberately stops at plain JSON data:
it does not import a template environment, render Markdown, or write HTML.  The
Next application consumes the resulting ``v1`` model during its static export.

Keeping this boundary explicit is useful for both source checkouts and wheels:
the source checkout can rebuild the model from the live plugin/context APIs,
while an installed wheel can use a prebuilt site without importing Node-only
code or silently falling back to the removed Jinja renderer.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass
import hashlib
import inspect
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

import numpy as np

from .plugin_doc_generator import PluginDocGenerator
from .site_docs.catalog import (
    ACCESSOR_DOCUMENTATION_REGISTRY,
    ACCESSOR_SELECTION_GUIDE,
    ADAPTER_DOCUMENTATION_PAGE,
    CONTEXT_DOCUMENTATION_PAGE,
    RECORDS_VIEW_DOCUMENTATION_PAGE,
    VISUALIZATION_DOCUMENTATION_PAGES,
)
from .site_guides import GuidePageSpec, load_guide_manifest

SITE_MODEL_VERSION = "site-model/v1"
SITE_MODEL_SCHEMA_VERSION = SITE_MODEL_VERSION
SITE_MODEL_KIND = "waveform-analysis-site"
SITE_MODEL_FILENAME = "site-model.v1.json"
SITE_MODEL_SCHEMA_FILENAME = "SiteModel.schema.json"
SITE_MODEL_SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / SITE_MODEL_SCHEMA_FILENAME

# The app receives a path through all three names during the migration.  The
# first name is canonical; the aliases make the contract easy to consume from
# Next config, tests, and a future non-Next static frontend without changing the
# JSON shape.
SITE_MODEL_ENV = "WAVEFORM_DOCS_SITE_MODEL"
SITE_MODEL_ENV_ALIASES = (SITE_MODEL_ENV, "WAVEFORM_SITE_MODEL_PATH", "WAVEFORM_DOCS_MODEL_PATH")
SITE_MODEL_EXPORT_ENV = "WAVEFORM_SITE_EXPORT_DIR"

_ROUTE_ID = re.compile(r"^[A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)*$")
_HEADING = re.compile(r"^(?P<indent>\s{0,3})(?P<marks>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_SETEXT = re.compile(r"^\s*(=+|-+)\s*$")
_FENCE = re.compile(r"^\s*(?P<marks>`{3,}|~{3,})(?P<language>.*)$")
_ORDERED_LIST = re.compile(r"^\s*\d+[.)]\s+(?P<item>.+?)\s*$")
_UNORDERED_LIST = re.compile(r"^\s*[-+*]\s+(?P<item>.+?)\s*$")
_INLINE_TOKEN = re.compile(
    r"(?P<image>!\[(?P<image_label>[^\]]*)\]\((?P<image_href>[^)\s]+)(?:\s+[^)]*)?\))"
    r"|(?P<link>\[(?P<link_label>[^\]]+)\]\((?P<link_href>[^)\s]+)(?:\s+[^)]*)?\))"
    r"|(?P<code>`(?P<code_text>[^`\n]+)`)",
)
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.DOTALL)
_ALLOWED_GUIDE_TAGS = {"markdown", "reflect", "plugin-provider"}


class SiteModelError(ValueError):
    """Raised when site facts cannot satisfy the versioned site contract."""


def canonical_route(value: str, *, field: str = "route") -> str:
    """Return one safe, extensionless public route.

    The route registry stores leading-slash URLs, while the physical Next
    export may use ``index.html`` files underneath route directories. Legacy
    ``.html`` values are rejected: historical spellings belong only in the
    migration map and are never accepted by the live model.
    """

    if not isinstance(value, str) or not value.strip():
        raise SiteModelError(f"{field} must be a non-empty string")
    raw = value.strip().replace("\\", "/")
    if raw.startswith("/"):
        raw = raw[1:]
    if raw.endswith(".html"):
        raise SiteModelError(f"{field} must be extensionless: {value!r}")
    if raw.endswith("/") and raw != "/":
        raw = raw.rstrip("/")
    if raw in {"", "."}:
        return "/"
    if raw.startswith(".") or ".." in PurePosixPath(raw).parts or not _ROUTE_ID.fullmatch(raw):
        raise SiteModelError(f"{field} must be a safe relative extensionless route: {value!r}")
    # Next is configured with trailingSlash=true.  The slash is part of the
    # canonical URL, while ``index.html`` remains only an export detail.
    return f"/{raw}/"


def route_without_leading_slash(route: str) -> str:
    """Return the filesystem-relative spelling of a canonical route."""

    value = canonical_route(route)
    return value[1:].rstrip("/")


def _json_value(value: Any) -> Any:
    """Convert documentation dataclasses and scientific scalars to JSON data."""

    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_json_value(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    # Markup and enum-like values are intentionally represented by their text.
    return str(value)


def _plain(value: Any) -> str:
    return " ".join(str(value or "").split())


def _summary_text(value: Any) -> str:
    """Return compact prose without Markdown footnote reference markers."""

    return re.sub(r"\[\^[^\]]+\]", "", _plain(value)).strip()


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("waveform-analysis")
    except Exception:
        return "0.0.0+source"


def _source_relative(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        # A custom manifest may point to a docs tree outside cwd.  Do not put an
        # absolute host path into a reproducible model; keep a stable label.
        return path.name


def _heading_slug(title: str, counts: dict[str, int]) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.casefold(), flags=re.UNICODE)
    slug = re.sub(r"[\s-]+", "-", slug).strip("-") or "section"
    count = counts.get(slug, 0)
    counts[slug] = count + 1
    return slug if count == 0 else f"{slug}-{count + 1}"


def _markdown_facts(source: Path) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    """Read Markdown metadata without rendering it to HTML."""

    text = source.read_text(encoding="utf-8")
    frontmatter: dict[str, Any] = {}
    body = text
    match = _FRONTMATTER.match(text)
    if match:
        # YAML is already a project dependency and is used by the guide
        # manifest.  Import lazily so plugin-only Markdown generation remains
        # usable in a minimal environment.
        import yaml

        parsed = yaml.safe_load(match.group(1))
        if parsed is None:
            parsed = {}
        if not isinstance(parsed, dict):
            raise SiteModelError(f"Markdown frontmatter must be a mapping: {source}")
        frontmatter = parsed
        body = text[match.end() :]

    headings: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    lines = body.splitlines()
    for index, line in enumerate(lines):
        heading_match = _HEADING.match(line)
        if heading_match:
            title = _plain(heading_match.group("title"))
            level = len(heading_match.group("marks"))
        elif index + 1 < len(lines) and line.strip() and _SETEXT.match(lines[index + 1]):
            title = _plain(line)
            level = 1 if lines[index + 1].strip().startswith("=") else 2
        else:
            continue
        if title:
            headings.append(
                {"level": level, "title": title, "anchor": _heading_slug(title, counts)}
            )

    title = _plain(frontmatter.get("title"))
    if not title:
        title = next((item["title"] for item in headings if item["level"] == 1), "")
    if not title:
        title = source.stem.replace("_", " ").replace("-", " ").strip()

    summary = _summary_text(frontmatter.get("summary"))
    if not summary:
        for line in body.splitlines():
            candidate = _summary_text(line)
            if not candidate or candidate.startswith("#") or candidate.startswith("```"):
                continue
            if candidate.startswith(("---", "* ", "- ", ">", "![", "[")):
                continue
            summary = candidate
            break
    return {str(key): _json_value(value) for key, value in frontmatter.items()}, body, headings


def _serialize_content_block(block: Any) -> dict[str, Any]:
    result = _json_value(block)
    if not isinstance(result, dict):
        raise SiteModelError(f"Content block is not serializable: {block!r}")
    # Markup fields are intentionally not accepted in the model.  The curated
    # specs contain source text and code, and Next performs the presentation.
    for key in tuple(result):
        if key.endswith("_html"):
            result.pop(key, None)
    return result


def _serialize_parameters(parameters: Iterable[Any]) -> list[dict[str, str]]:
    return [
        {"name": str(parameter.name), "description": str(parameter.description)}
        for parameter in parameters
    ]


def _serialize_accessor_spec(spec: Any) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    for member in spec.members:
        try:
            raw = inspect.getattr_static(spec.accessor_class, member.name)
        except AttributeError as exc:
            raise SiteModelError(
                f"Registered member {spec.accessor_class.__name__}.{member.name} does not exist"
            ) from exc
        is_property = isinstance(raw, property)
        if is_property != (member.kind == "property"):
            raise SiteModelError(
                f"Registered member kind mismatch for {spec.accessor_class.__name__}.{member.name}"
            )
        target = raw.fget if is_property else raw
        if target is None or not callable(target):
            raise SiteModelError(
                f"Registered member {spec.accessor_class.__name__}.{member.name} is not callable"
            )
        signature = str(inspect.signature(target))
        live_names = tuple(name for name in inspect.signature(target).parameters if name != "self")
        documented_names = tuple(parameter.name for parameter in member.parameters)
        if live_names != documented_names:
            raise SiteModelError(
                f"Registered parameter names for {spec.accessor_class.__name__}.{member.name} "
                f"do not match signature: expected {live_names}, got {documented_names}"
            )
        members.append(
            {
                "name": member.name,
                "kind": member.kind,
                "signature": signature,
                "description": member.description,
                "parameters": _serialize_parameters(member.parameters),
                "returns": member.returns,
                "notes": list(member.notes),
                "example": member.example,
            }
        )
    constructor_signature = str(inspect.signature(spec.accessor_class))
    live_names = tuple(
        name for name in inspect.signature(spec.accessor_class).parameters if name != "self"
    )
    documented_names = tuple(parameter.name for parameter in spec.constructor_parameters)
    if live_names != documented_names:
        raise SiteModelError(
            f"Registered constructor parameters for {spec.accessor_class.__name__} do not match "
            f"signature: expected {live_names}, got {documented_names}"
        )
    return {
        "name": spec.accessor_class.__name__,
        "slug": spec.slug,
        "route": canonical_route(f"/accessors/{spec.slug}"),
        "module_path": spec.accessor_class.__module__,
        "summary": spec.summary,
        "introduction": spec.introduction,
        "purpose": spec.purpose,
        "example": spec.example,
        "constructor_signature": constructor_signature,
        "constructor_parameters": _serialize_parameters(spec.constructor_parameters),
        "members": members,
        "narrative_sections": [
            {
                "anchor": section.anchor,
                "title": section.title,
                "blocks": [_serialize_content_block(block) for block in section.blocks],
            }
            for section in spec.narrative_sections
        ],
        "overview_title": spec.overview_title,
        "overview_blocks": [_serialize_content_block(block) for block in spec.overview_blocks],
    }


def _serialize_callable_spec(spec: Any, *, section: str) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    for group in spec.groups:
        members: list[dict[str, Any]] = []
        for member in group.members:
            signature = str(inspect.signature(member.callable))
            live_names = tuple(
                name
                for name in inspect.signature(member.callable).parameters
                if name not in {"self", "cls"}
            )
            documented_names = tuple(parameter.name for parameter in member.parameters)
            if live_names != documented_names:
                raise SiteModelError(
                    f"Registered parameter names for {member.name} do not match signature: "
                    f"expected {live_names}, got {documented_names}"
                )
            members.append(
                {
                    "name": member.name,
                    "kind": member.kind,
                    "signature": signature,
                    "description": member.description,
                    "parameters": _serialize_parameters(member.parameters),
                    "returns": member.returns,
                    "notes": list(member.notes),
                    "example": member.example,
                }
            )
        groups.append(
            {
                "anchor": group.anchor,
                "title": group.title,
                "description": group.description,
                "members": members,
            }
        )
    return {
        "slug": spec.slug,
        "route": canonical_route(f"/{section}/{spec.slug}"),
        "title": spec.title,
        "eyebrow": spec.eyebrow,
        "summary": spec.summary,
        "introduction": spec.introduction,
        "groups": groups,
        "narrative_sections": [
            {
                "anchor": narrative.anchor,
                "title": narrative.title,
                "blocks": [_serialize_content_block(block) for block in narrative.blocks],
            }
            for narrative in spec.narrative_sections
        ],
    }


def _paragraph(text: Any) -> dict[str, Any]:
    return {"kind": "paragraph", "text": str(text)}


def _heading(text: Any, level: int = 3) -> dict[str, Any]:
    return {"kind": "heading", "text": str(text), "heading_level": level}


def _code(code: Any, language: str = "python") -> dict[str, Any]:
    return {"kind": "code", "code": str(code), "language": language}


def _items(items: Iterable[Any], *, ordered: bool = False) -> dict[str, Any]:
    return {"kind": "list", "items": [str(item) for item in items], "ordered": ordered}


def _table(headers: Iterable[Any], rows: Iterable[Iterable[Any]]) -> dict[str, Any]:
    return {
        "kind": "table",
        "table_headers": [str(header) for header in headers],
        "table_rows": [[str(cell) for cell in row] for row in rows],
    }


def _member_blocks(member: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project one reflected API member without dropping its public contract."""

    blocks: list[dict[str, Any]] = [
        _heading(member["name"]),
        _code(member["signature"]),
        _paragraph(member["description"]),
    ]
    parameters = list(member.get("parameters", []))
    if parameters:
        blocks.extend(
            [
                _heading("参数", 4),
                _table(
                    ("参数", "说明"),
                    ((parameter["name"], parameter["description"]) for parameter in parameters),
                ),
            ]
        )
    if member.get("returns"):
        blocks.extend([_heading("返回值", 4), _paragraph(member["returns"])])
    if member.get("notes"):
        blocks.extend([_heading("使用注意", 4), _items(member["notes"])])
    if member.get("example"):
        blocks.extend([_heading("示例", 4), _code(member["example"])])
    return blocks


def _accessor_sections(rich: Mapping[str, Any]) -> list[dict[str, Any]]:
    overview = [_paragraph(rich["introduction"]), *rich["overview_blocks"]]
    if not rich["overview_blocks"] and rich.get("purpose"):
        overview.extend([_heading("适用场景"), _paragraph(rich["purpose"])])
    sections: list[dict[str, Any]] = [
        {"id": "overview", "title": rich["overview_title"], "blocks": overview},
        {"id": "quickstart", "title": "快速开始", "blocks": [_code(rich["example"])]},
        {
            "id": "constructor",
            "title": "构造器",
            "blocks": [
                _code(f"{rich['name']}{rich['constructor_signature']}"),
                *(
                    [
                        _table(
                            ("参数", "说明"),
                            (
                                (parameter["name"], parameter["description"])
                                for parameter in rich["constructor_parameters"]
                            ),
                        )
                    ]
                    if rich["constructor_parameters"]
                    else []
                ),
            ],
        },
    ]
    sections.extend(
        {
            "id": narrative["anchor"],
            "title": narrative["title"],
            "blocks": narrative["blocks"],
        }
        for narrative in rich["narrative_sections"]
    )
    member_blocks: list[dict[str, Any]] = []
    for member in rich["members"]:
        member_blocks.extend(_member_blocks(member))
    sections.append({"id": "members", "title": "公开成员", "blocks": member_blocks})
    return sections


def _callable_sections(rich: Mapping[str, Any]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = [
        {"id": "overview", "title": "整体介绍", "blocks": [_paragraph(rich["introduction"])]}
    ]
    sections.extend(
        {
            "id": narrative["anchor"],
            "title": narrative["title"],
            "blocks": narrative["blocks"],
        }
        for narrative in rich["narrative_sections"]
    )
    for group in rich["groups"]:
        blocks: list[dict[str, Any]] = []
        if group.get("description"):
            blocks.append(_paragraph(group["description"]))
        for member in group["members"]:
            blocks.extend(_member_blocks(member))
        sections.append({"id": group["anchor"], "title": group["title"], "blocks": blocks})
    return sections


def _accessor_contract(spec: Any) -> dict[str, Any]:
    """Build list facts plus the complete curated Accessor reference."""

    rich = _serialize_accessor_spec(spec)
    return {
        **rich,
        "pageKind": "class",
        "inputs": [str(parameter.name) for parameter in spec.constructor_parameters],
        "methods": [str(member.name) for member in spec.members],
        "sections": _accessor_sections(rich),
        "provenance": "generated",
    }


def _callable_contract(spec: Any, *, section: str) -> dict[str, Any]:
    rich = _serialize_callable_spec(spec, section=section)
    members = [member for group in rich["groups"] for member in group["members"]]
    parameters = list(
        dict.fromkeys(parameter["name"] for member in members for parameter in member["parameters"])
    )
    result = {
        **rich,
        "name": rich["title"],
        "profiles": [group["title"] for group in rich["groups"]],
        "examples": [member["example"] for member in members if member.get("example")],
        "sections": _callable_sections(rich),
        "provenance": "generated",
    }
    if section == "accessors":
        result.update(
            {
                "pageKind": "callable",
                "inputs": parameters,
                "methods": [member["name"] for member in members],
            }
        )
    return result


def _visualization_contract(spec: Any) -> dict[str, Any]:
    result = _callable_contract(spec, section="visualizations")
    result["outputs"] = [
        member["returns"]
        for group in result["groups"]
        for member in group["members"]
        if member.get("returns")
    ]
    return result


def _plugin_sections(view: Any) -> list[dict[str, Any]]:
    overview_blocks: list[dict[str, Any]] = []
    overview = list(getattr(view, "overview_paragraphs", ()) or ())
    if not overview and getattr(view, "overview", ""):
        overview = [view.overview]
    overview_blocks.extend(_paragraph(item) for item in overview)
    status = getattr(view, "documentation_status", None)
    overview_blocks.append(
        _table(
            ("项目", "值"),
            (
                ("插件类", getattr(view, "name", "")),
                ("模块", getattr(view, "module_path", "")),
                ("版本", getattr(view, "version", "")),
                ("输出容器", getattr(view, "output_kind", "")),
                ("执行模式", getattr(view, "execution_kind", "")),
                ("保存策略", getattr(view, "save_when", "")),
                ("运行配置", "yes" if getattr(view, "uses_run_config", False) else "no"),
                ("超时", getattr(view, "timeout", None) or "none"),
                ("副作用", "yes" if getattr(view, "is_side_effect", False) else "no"),
                ("叙述来源", getattr(status, "source", "unknown") if status else "unknown"),
                ("源码 fingerprint", getattr(view, "source_fingerprint", None) or "unavailable"),
            ),
        )
    )
    overview_blocks.extend(
        [
            _heading("依赖"),
            _paragraph(f"默认画像：{getattr(view, 'dependency_profile', '') or 'default'}。"),
        ]
    )
    dependencies = list(getattr(view, "resolved_dependency_details", ()) or ())
    if dependencies:
        overview_blocks.append(
            _table(
                ("依赖", "版本约束", "解析方式", "必需字段", "说明"),
                (
                    (
                        dependency.name,
                        dependency.version_constraint or "-",
                        dependency.resolution,
                        ", ".join(dependency.required_fields) or "-",
                        dependency.description or "暂无生产者说明。",
                    )
                    for dependency in dependencies
                ),
            )
        )
    overview_blocks.append(_heading("工作方式"))
    workflow_steps = list(getattr(view, "workflow_steps", ()) or ())
    if workflow_steps:
        overview_blocks.append(_items(workflow_steps, ordered=True))
    workflow_diagram = str(getattr(view, "workflow_diagram", "") or "")
    if workflow_diagram:
        overview_blocks.extend(
            [
                _heading("处理流程图"),
                {"kind": "mermaid", "mermaid": workflow_diagram},
            ]
        )

    config_rows = [
        (
            option.name,
            option.type,
            option.default,
            option.units or "-",
            "是" if option.tracked else "否",
            "是" if option.deprecated else "否",
            getattr(view, "config_notes", {}).get(option.name, option.doc or "暂无说明。"),
        )
        for option in getattr(view, "config_options", ())
    ]
    config_blocks = (
        [_table(("名称", "类型", "默认值", "单位", "跟踪", "弃用", "说明"), config_rows)]
        if config_rows
        else [_paragraph("此插件没有插件级配置。")]
    )
    fields = list(getattr(view, "output_fields", ()) or ())
    output_blocks: list[dict[str, Any]] = []
    if getattr(view, "output_summary", ""):
        output_blocks.append(_paragraph(view.output_summary))
    output_blocks.append(
        _table(
            ("字段", "DType", "单位", "含义"),
            (
                (
                    (
                        field.name,
                        field.dtype,
                        field.units or "-",
                        field.doc
                        or getattr(view, "field_notes", {}).get(field.name, "暂无字段说明。"),
                    )
                    for field in fields
                )
                if fields
                else (
                    (
                        "容器",
                        getattr(view, "output_kind", ""),
                        "-",
                        getattr(view, "output_summary", ""),
                    ),
                )
            ),
        )
    )
    usage_blocks: list[dict[str, Any]] = []
    if getattr(view, "usage_example", ""):
        usage_blocks.append(_code(view.usage_example))
    notes = [
        *list(getattr(view, "behavior_notes", ()) or ()),
        *list(getattr(view, "execution_notes", ()) or ()),
    ]
    if notes:
        usage_blocks.extend([_heading("行为与运行影响"), _items(notes)])
    failure_modes = list(getattr(view, "failure_modes", ()) or ())
    if failure_modes:
        usage_blocks.extend([_heading("失败模式", 4), _items(failure_modes)])
    consumers = list(getattr(view, "downstream_consumers", ()) or ())
    usage_blocks.extend(
        [
            _heading("下游消费者", 4),
            _items(consumers) if consumers else _paragraph("终端输出，没有声明直接的内置消费者。"),
        ]
    )
    return [
        {"id": "overview", "title": "概览", "blocks": overview_blocks},
        {"id": "configuration", "title": "配置", "blocks": config_blocks},
        {"id": "output", "title": "输出", "blocks": output_blocks},
        {"id": "usage", "title": "使用", "blocks": usage_blocks},
    ]


def _plugin_record(view: Any) -> dict[str, Any]:
    """Project the rich plugin view into the small frontend contract."""

    provides = str(getattr(view, "provides", ""))
    if not provides:
        raise SiteModelError("Plugin documentation is missing provides")
    execution_kind = str(getattr(view, "execution_kind", "unknown"))
    if execution_kind == "stream":
        execution_kind = "streaming"
    elif execution_kind not in {"static", "streaming"}:
        execution_kind = "unknown"

    def dependency_name(value: Any) -> str:
        return str(value[0] if isinstance(value, tuple) else value)

    config = [
        {
            "name": str(option.name),
            "value": str(option.default),
            "description": _plain(option.doc) or str(option.name),
        }
        for option in getattr(view, "config_options", ())
    ]
    fields = [
        {
            "name": str(field.name),
            "dtype": str(field.dtype),
            "unit": str(field.units or "-"),
            "description": _plain(field.doc) or str(field.name),
        }
        for field in getattr(view, "output_fields", ())
    ]
    description = _plain(getattr(view, "description", ""))
    return {
        "provides": provides,
        "pluginClass": str(getattr(view, "name", provides)),
        "version": str(getattr(view, "version", "")) or None,
        "executionKind": execution_kind,
        "outputKind": str(getattr(view, "output_kind", "structured_array")),
        "category": str(getattr(view, "category", "other")),
        "summary": description or provides,
        "dependsOn": [dependency_name(item) for item in getattr(view, "resolved_depends_on", ())],
        "config": config,
        "fields": fields,
        "usage": str(getattr(view, "usage_example", "") or ""),
        "sections": _plugin_sections(view),
        "route": canonical_route(f"/plugins/{provides}"),
        "provenance": "generated",
    }


def _guide_page_record(page: GuidePageSpec, project_root: Path) -> dict[str, Any]:
    route = canonical_route(page.route, field=f"guide page route {page.source_label}")
    source: str | None = None
    source_sha256: str | None = None
    body = ""
    headings: list[dict[str, Any]] = []
    frontmatter: dict[str, Any] = {}
    if page.source is not None:
        source_path = Path(page.source)
        source = _source_relative(source_path, project_root)
        source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        frontmatter, body, headings = _markdown_facts(source_path)
    title = _plain(page.title_override) or _plain(frontmatter.get("title"))
    if not title:
        title = next((item["title"] for item in headings if item["level"] == 1), "")
    if not title:
        title = Path(page.source_label).stem.replace("_", " ").replace("-", " ")
    summary = _summary_text(page.summary_override) or _summary_text(frontmatter.get("summary"))
    if not summary:
        for line in body.splitlines():
            candidate = _summary_text(line)
            if candidate and not candidate.startswith(
                ("#", "---", "```", "- ", "* ", ">", "[", "![", "**导航**", "**Navigation**")
            ):
                summary = candidate
                break
    tag = str(page.tag or frontmatter.get("tag", "markdown"))
    if tag not in _ALLOWED_GUIDE_TAGS:
        raise SiteModelError(f"Unsupported guide tag {tag!r}: {page.source_label}")
    return {
        "route": route,
        "title": title,
        "summary": summary,
        "tag": tag,
        "source": source,
        "source_sha256": source_sha256,
        "body": body if tag == "markdown" else "",
        "headings": headings,
        "nav_weight": int(page.nav_weight),
    }


def _resolve_markdown_href(
    href: str,
    *,
    source_path: Path | None,
    project_root: Path | None,
    source_routes: Mapping[str, str] | None,
) -> str:
    """Resolve known Markdown targets to canonical static routes.

    The content model stores links as data instead of HTML.  Links which point
    at a published Markdown source are translated through the manifest route
    map; external URLs and unknown targets remain untouched so that parsing is
    lossless and does not invent routes for unpublished material.
    """

    value = href.strip().strip("<>")
    if not value or value.startswith("#") or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        return value
    path_part, separator, suffix = value.partition("#")
    fragment = f"#{suffix}" if separator else ""
    query_path, query_separator, query = path_part.partition("?")
    if query_separator:
        # Internal docs links should not carry query strings into a static
        # route.  Retain the source spelling when no route is known instead.
        path_part = query_path
    else:
        path_part = query_path

    candidate: str | None = None
    if source_path is not None and project_root is not None:
        target = Path(path_part)
        if not target.is_absolute():
            target = (source_path.parent / target).resolve()
        try:
            candidate = target.relative_to(project_root.resolve()).as_posix()
        except ValueError:
            candidate = None
    if candidate is None:
        candidate = path_part.lstrip("/")

    routes = source_routes or {}
    route = routes.get(candidate)
    if route is None:
        route = routes.get(path_part)
    if route is not None:
        return f"{route}{fragment}"

    # Existing repository files which are intentionally outside the public
    # site remain clickable without creating a second static-asset tree.  A
    # missing target is deliberately left unchanged so export validation still
    # catches stale or misspelled links.
    if (
        source_path is not None
        and project_root is not None
        and candidate
        and target.exists()
        and target.is_relative_to(project_root.resolve())
    ):
        github_kind = "tree" if target.is_dir() else "blob"
        return (
            "https://github.com/SnowingWolf/WaveformAnalysis/"
            f"{github_kind}/main/{candidate}{fragment}"
        )

    # A direct canonical route is already safe; normalize a legacy direct HTML
    # spelling only when it is clearly a route rather than an unknown source.
    if path_part.startswith("/") and ".html" in path_part:
        raw_route = path_part.rsplit(".html", 1)[0]
        try:
            return f"{canonical_route(raw_route)}{fragment}"
        except SiteModelError:
            return value
    if path_part.startswith("/") and path_part.endswith("/"):
        try:
            return f"{canonical_route(path_part)}{fragment}"
        except SiteModelError:
            return value
    return value


def _inline_content(
    text: str,
    *,
    source_path: Path | None,
    project_root: Path | None,
    source_routes: Mapping[str, str] | None,
) -> list[dict[str, str]]:
    """Tokenize inline code and links without interpreting arbitrary HTML."""

    parts: list[dict[str, str]] = []

    def append(kind: str, value: str, **extra: str) -> None:
        if not value:
            return
        if kind == "text" and parts and parts[-1]["kind"] == "text":
            parts[-1]["text"] += value
            return
        parts.append({"kind": kind, "text": value, **extra})

    cursor = 0
    for match in _INLINE_TOKEN.finditer(text):
        append("text", text[cursor : match.start()])
        if match.group("image"):
            append(
                "image",
                match.group("image_label") or "image",
                href=_resolve_markdown_href(
                    match.group("image_href"),
                    source_path=source_path,
                    project_root=project_root,
                    source_routes=source_routes,
                ),
            )
        elif match.group("link"):
            append(
                "link",
                match.group("link_label"),
                href=_resolve_markdown_href(
                    match.group("link_href"),
                    source_path=source_path,
                    project_root=project_root,
                    source_routes=source_routes,
                ),
            )
        else:
            append("code", match.group("code_text"))
        cursor = match.end()
    append("text", text[cursor:])
    return parts or [{"kind": "text", "text": text}]


def _guide_text_block(
    kind: str,
    text: str,
    *,
    source_path: Path | None,
    project_root: Path | None,
    source_routes: Mapping[str, str] | None,
    **extra: Any,
) -> dict[str, Any]:
    block: dict[str, Any] = {"kind": kind, "text": text, **extra}
    block["inlines"] = _inline_content(
        text,
        source_path=source_path,
        project_root=project_root,
        source_routes=source_routes,
    )
    return block


def _guide_list_block(
    items: list[str],
    *,
    ordered: bool,
    source_path: Path | None,
    project_root: Path | None,
    source_routes: Mapping[str, str] | None,
) -> dict[str, Any]:
    return {
        "kind": "list",
        "items": items,
        "ordered": ordered,
        "item_inlines": [
            _inline_content(
                item,
                source_path=source_path,
                project_root=project_root,
                source_routes=source_routes,
            )
            for item in items
        ],
    }


def _split_table_lines(lines: list[str]) -> tuple[list[str], list[list[str]]] | None:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    if len(rows) < 2 or not rows[0]:
        return None
    header = rows[0]
    data_rows = rows[1:]
    if data_rows and all(set(cell) <= {"-", ":", " "} for cell in data_rows[0]):
        data_rows = data_rows[1:]
    if not data_rows or not all(len(row) == len(header) for row in data_rows):
        return None
    return header, data_rows


def _guide_table_block(
    lines: list[str],
    *,
    source_path: Path | None,
    project_root: Path | None,
    source_routes: Mapping[str, str] | None,
) -> dict[str, Any] | None:
    parsed = _split_table_lines(lines)
    if parsed is None:
        return None
    headers, rows = parsed
    return {
        "kind": "table",
        "table_headers": headers,
        "table_rows": rows,
        "table_inlines": [
            [
                _inline_content(
                    cell,
                    source_path=source_path,
                    project_root=project_root,
                    source_routes=source_routes,
                )
                for cell in row
            ]
            for row in [headers, *rows]
        ],
    }


def _guide_section_compat(section: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the pre-S1 fields for old search consumers during migration."""

    result = dict(section)
    blocks = list(section.get("blocks", ()))
    paragraphs = [
        str(block.get("text", "")) for block in blocks if block.get("kind") == "paragraph"
    ]
    lists = [block for block in blocks if block.get("kind") == "list"]
    tables = [block for block in blocks if block.get("kind") == "table"]
    codes = [str(block.get("code", "")) for block in blocks if block.get("kind") == "code"]
    result["paragraphs"] = paragraphs
    if lists:
        # The legacy projection represented only unordered list items.  Keep
        # ordered content discoverable as well; the typed blocks are canonical.
        result["bullets"] = [str(item) for block in lists for item in block.get("items", ())]
    if codes:
        result["code"] = "\n\n".join(codes)
    if tables:
        table = tables[0]
        result["table"] = {
            "headers": list(table.get("table_headers", ())),
            "rows": [list(row) for row in table.get("table_rows", ())],
        }
    return result


def _guide_content_counts(sections: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for section in sections:
        for block in section.get("blocks", ()):
            kind = str(block.get("kind", ""))
            if kind:
                counts[kind] += 1
            for inline in block.get("inlines", ()):
                if inline.get("kind") == "link":
                    counts["link"] += 1
            for row in block.get("item_inlines", ()):
                for inline in row:
                    if inline.get("kind") == "link":
                        counts["link"] += 1
            for row in block.get("table_inlines", ()):
                for cell in row:
                    for inline in cell:
                        if inline.get("kind") == "link":
                            counts["link"] += 1
    for kind in ("paragraph", "link", "code", "table", "list"):
        counts.setdefault(kind, 0)
    return dict(counts)


def _guide_block_types(sections: Iterable[Mapping[str, Any]]) -> list[str]:
    return [
        str(block["kind"])
        for section in sections
        for block in section.get("blocks", ())
        if block.get("kind")
    ]


def _guide_model_fingerprint(sections: Iterable[Mapping[str, Any]]) -> str:
    payload = [
        {
            "id": section.get("id"),
            "title": section.get("title"),
            "blocks": section.get("blocks", []),
        }
        for section in sections
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _markdown_sections(
    body: str,
    *,
    fallback_title: str,
    source_path: Path | None = None,
    project_root: Path | None = None,
    source_routes: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Project Markdown into ordered, typed, HTML-free content blocks."""

    lines = body.splitlines()
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    paragraph_lines: list[str] = []
    list_items: list[str] = []
    list_ordered: bool | None = None
    table_lines: list[str] = []
    code_lines: list[str] = []
    code_language = "text"
    fence_mark: str | None = None
    skip_line = False

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if current is not None and paragraph_lines:
            text = " ".join(item.strip() for item in paragraph_lines if item.strip()).strip()
            if text:
                current["blocks"].append(
                    _guide_text_block(
                        "paragraph",
                        text,
                        source_path=source_path,
                        project_root=project_root,
                        source_routes=source_routes,
                    )
                )
        paragraph_lines = []

    def flush_list() -> None:
        nonlocal list_items, list_ordered
        if current is not None and list_items and list_ordered is not None:
            current["blocks"].append(
                _guide_list_block(
                    list_items,
                    ordered=list_ordered,
                    source_path=source_path,
                    project_root=project_root,
                    source_routes=source_routes,
                )
            )
        list_items = []
        list_ordered = None

    def flush_table() -> None:
        nonlocal table_lines
        if current is not None and table_lines:
            table = _guide_table_block(
                table_lines,
                source_path=source_path,
                project_root=project_root,
                source_routes=source_routes,
            )
            if table is not None:
                current["blocks"].append(table)
            else:
                paragraph_lines.extend(table_lines)
                flush_paragraph()
        table_lines = []

    def flush_pending() -> None:
        flush_paragraph()
        flush_list()
        flush_table()

    def finish_current(*, force: bool = False) -> None:
        nonlocal current
        if current is None:
            return
        flush_pending()
        if force or current["blocks"]:
            sections.append(_guide_section_compat(current))
        current = None

    def start(title: str, anchor: str, level: int | None = None) -> None:
        nonlocal current
        finish_current()
        block_list: list[dict[str, Any]] = []
        if level is not None:
            block_list.append(
                {
                    "kind": "heading",
                    "text": title,
                    "heading_level": level,
                    "inlines": _inline_content(
                        title,
                        source_path=source_path,
                        project_root=project_root,
                        source_routes=source_routes,
                    ),
                }
            )
        current = {"id": anchor, "title": title, "blocks": block_list}

    counts: dict[str, int] = {}
    start(fallback_title, _heading_slug(fallback_title, counts))
    for index, raw_line in enumerate(lines):
        if skip_line:
            skip_line = False
            continue
        line = raw_line.rstrip()
        fence_match = _FENCE.match(line)
        if fence_match:
            marks = fence_match.group("marks")
            if fence_mark is None:
                flush_pending()
                fence_mark = marks[0]
                language_tokens = fence_match.group("language").strip().split(maxsplit=1)
                code_language = language_tokens[0] if language_tokens else "text"
                code_lines = []
            elif marks[0] == fence_mark:
                if current is not None:
                    current["blocks"].append(
                        {
                            "kind": "code",
                            "code": "\n".join(code_lines).rstrip("\n"),
                            "language": code_language,
                        }
                    )
                fence_mark = None
                code_lines = []
                code_language = "text"
            else:
                code_lines.append(line)
            continue
        if fence_mark is not None:
            code_lines.append(line)
            continue

        heading_match = _HEADING.match(line)
        if heading_match:
            title = _plain(heading_match.group("title"))
            level = len(heading_match.group("marks"))
            if title and level >= 2:
                start(title, _heading_slug(title, counts), level)
                continue
            if title:
                flush_pending()
                continue
        if index + 1 < len(lines) and line.strip() and _SETEXT.match(lines[index + 1]):
            level = 1 if lines[index + 1].strip().startswith("=") else 2
            if level >= 2:
                title = _plain(line)
                start(title, _heading_slug(title, counts), level)
                skip_line = True
                continue

        stripped = line.strip()
        if not stripped:
            flush_pending()
            continue
        if stripped.startswith("<!--") or stripped.startswith("-->"):
            continue

        ordered_match = _ORDERED_LIST.match(line)
        unordered_match = _UNORDERED_LIST.match(line)
        if ordered_match or unordered_match:
            flush_paragraph()
            flush_table()
            ordered = ordered_match is not None
            if list_ordered is not None and list_ordered != ordered:
                flush_list()
            list_ordered = ordered
            list_items.append((ordered_match or unordered_match).group("item"))
            continue
        if list_items and line[:1].isspace():
            list_items[-1] = f"{list_items[-1]} {stripped}"
            continue
        if list_items:
            flush_list()

        if stripped.startswith("|") and "|" in stripped[1:]:
            flush_paragraph()
            table_lines.append(stripped)
            continue
        if table_lines:
            flush_table()

        if stripped.startswith(">"):
            quote = re.sub(r"^>\s?", "", stripped)
            if not quote:
                continue
            current["blocks"].append(
                _guide_text_block(
                    "note",
                    quote,
                    source_path=source_path,
                    project_root=project_root,
                    source_routes=source_routes,
                    tone="note",
                )
            )
            continue

        image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)", stripped)
        if image_match:
            current["blocks"].append(
                {
                    "kind": "image",
                    "image_src": _resolve_markdown_href(
                        image_match.group(2),
                        source_path=source_path,
                        project_root=project_root,
                        source_routes=source_routes,
                    ),
                    "image_alt": image_match.group(1),
                }
            )
            continue
        paragraph_lines.append(stripped)

    if fence_mark is not None and current is not None:
        current["blocks"].append(
            {"kind": "code", "code": "\n".join(code_lines).rstrip("\n"), "language": code_language}
        )
    finish_current(force=not sections)
    return sections or [{"id": "overview", "title": fallback_title, "blocks": [], "paragraphs": []}]


def build_guide_facts(
    manifest_path: Path | None = None, *, project_root: Path | None = None
) -> list[dict[str, Any]]:
    """Load guide navigation and Markdown source facts without HTML rendering."""

    if manifest_path is None:
        root = Path(project_root or Path.cwd()).resolve()
        manifest_path = root / "docs" / "site-guides.yaml"
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.is_file():
        return []
    manifest = load_guide_manifest(manifest_path)
    root = Path(project_root or manifest.project_root).resolve()
    sections: list[dict[str, Any]] = []
    for section in manifest.sections:
        pages = [
            _guide_page_record(page, root)
            for page in sorted(section.pages, key=lambda item: (item.nav_weight, item.route))
        ]
        sections.append(
            {
                "id": section.section_id,
                "title": section.title,
                "route": canonical_route(section.index_route),
                "pages": pages,
                "source_indexes": [_source_relative(path, root) for path in section.source_indexes],
                "nav_weight": int(section.nav_weight),
            }
        )
    sections.sort(key=lambda item: (item["nav_weight"], item["id"]))
    return sections


def _guide_source_routes(
    sections: Iterable[Mapping[str, Any]],
    project_root: Path,
    plugins: Iterable[Mapping[str, Any]] = (),
) -> dict[str, str]:
    """Build the source-to-route map used by Markdown inline links."""

    routes: dict[str, str] = {"docs/README.md": "/"}
    for section in sections:
        section_route = str(section["route"])
        for source in section.get("source_indexes", ()):
            routes[str(source)] = section_route
        for page in section.get("pages", ()):
            source = page.get("source")
            if source:
                routes[str(source)] = str(page["route"])
    for plugin in plugins:
        provides = str(plugin.get("provides", ""))
        route = str(plugin.get("route", ""))
        if not provides or not route:
            continue
        routes[f"docs/plugins/reference/agent/{provides}.md"] = route
        routes[f"docs/plugins/reference/builtin/auto/{provides}.md"] = route
    return routes


def _markdown_summary(frontmatter: Mapping[str, Any], body: str, fallback: str) -> str:
    summary = _summary_text(frontmatter.get("summary"))
    if summary:
        return summary
    for line in body.splitlines():
        candidate = _summary_text(line)
        if candidate and not candidate.startswith(
            ("#", "---", "```", "- ", "* ", ">", "[", "![", "**导航**", "**Navigation**")
        ):
            return candidate
    return fallback


def _source_index_model(
    source: str,
    *,
    section: Mapping[str, Any],
    project_root: Path,
    source_routes: Mapping[str, str],
) -> dict[str, Any]:
    source_path = (project_root / source).resolve()
    frontmatter, body, headings = _markdown_facts(source_path)
    title = _plain(frontmatter.get("title")) or next(
        (item["title"] for item in headings if item["level"] == 1),
        str(section["title"]),
    )
    parsed_sections = _markdown_sections(
        body,
        fallback_title=title,
        source_path=source_path,
        project_root=project_root,
        source_routes=source_routes,
    )
    return {
        "section_id": str(section["id"]),
        "route": str(section["route"]),
        "source": source,
        "title": title,
        "summary": _markdown_summary(frontmatter, body, title),
        "sections": parsed_sections,
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "model_fingerprint": _guide_model_fingerprint(parsed_sections),
        "block_types": _guide_block_types(parsed_sections),
        "content_counts": _guide_content_counts(parsed_sections),
        "provenance": "generated",
    }


def _directory_guide_section(
    section: Mapping[str, Any],
    *,
    project_root: Path,
    source_routes: Mapping[str, str],
) -> dict[str, Any]:
    items = [f"[{page['title']}]({page['route']})" for page in section.get("pages", ())]
    blocks: list[dict[str, Any]] = [
        _guide_text_block(
            "paragraph",
            "选择下列主题继续阅读。",
            source_path=None,
            project_root=project_root,
            source_routes=source_routes,
        )
    ]
    if items:
        blocks.append(
            _guide_list_block(
                items,
                ordered=False,
                source_path=None,
                project_root=project_root,
                source_routes=source_routes,
            )
        )
    return _guide_section_compat({"id": "pages", "title": "本节文档", "blocks": blocks})


def _guide_models_from_sections(
    sections: list[dict[str, Any]],
    *,
    project_root: Path,
    source_routes: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    guides: list[dict[str, Any]] = []
    source_indexes: list[dict[str, Any]] = []
    special_index_routes = {"/plugins/", "/contexts/", "/accessors/", "/visualizations/"}
    for section in sections:
        indexes = [
            _source_index_model(
                source,
                section=section,
                project_root=project_root,
                source_routes=source_routes,
            )
            for source in section.get("source_indexes", ())
        ]
        source_indexes.extend(indexes)
        if section["route"] not in special_index_routes:
            index_sections = [item for index in indexes for item in index["sections"]]
            if not index_sections:
                index_sections = [
                    _directory_guide_section(
                        section,
                        project_root=project_root,
                        source_routes=source_routes,
                    )
                ]
            elif section.get("pages"):
                index_sections.append(
                    _directory_guide_section(
                        section,
                        project_root=project_root,
                        source_routes=source_routes,
                    )
                )
            guides.append(
                {
                    "slug": section["route"].strip("/").replace("/", "-") or "guide",
                    "title": section["title"],
                    "section": section["title"],
                    "summary": (
                        indexes[0]["summary"] if indexes else f"{section['title']}文档索引。"
                    ),
                    "sections": index_sections,
                    "route": section["route"],
                    "source_indexes": [
                        {
                            key: index[key]
                            for key in (
                                "section_id",
                                "route",
                                "source",
                                "title",
                                "summary",
                                "source_sha256",
                                "model_fingerprint",
                                "block_types",
                                "content_counts",
                            )
                        }
                        for index in indexes
                    ],
                    "model_fingerprint": _guide_model_fingerprint(index_sections),
                    "block_types": _guide_block_types(index_sections),
                    "content_counts": _guide_content_counts(index_sections),
                    "provenance": "generated",
                }
            )
        for page in section["pages"]:
            # Reflected pages are represented by their catalog facts.  They do
            # not have Markdown source sections and are added by the typed
            # collections below.
            if page["tag"] != "markdown":
                continue
            source = str(page["source"])
            source_path = (project_root / source).resolve()
            guide_sections = _markdown_sections(
                page.get("body", ""),
                fallback_title=page["title"],
                source_path=source_path,
                project_root=project_root,
                source_routes=source_routes,
            )
            guides.append(
                {
                    "slug": page["route"].strip("/").replace("/", "-") or "guide",
                    "title": page["title"],
                    "section": section["title"],
                    "summary": page["summary"] or page["title"],
                    "sections": guide_sections,
                    "route": page["route"],
                    "source": source,
                    "source_sha256": page.get("source_sha256"),
                    "model_fingerprint": _guide_model_fingerprint(guide_sections),
                    "block_types": _guide_block_types(guide_sections),
                    "content_counts": _guide_content_counts(guide_sections),
                    "provenance": "generated",
                }
            )
    return guides, source_indexes


_LINEAGE_KIND_BY_PLUGIN_SET = {
    "io": "raw",
    "waveform": "record",
    "basic_features": "record",
    "hit": "signal",
    "peaks": "peak",
    "events": "event",
    "tabular": "event",
}

_LINEAGE_KIND_BY_VISUAL_CATEGORY = {
    "raw_data": "raw",
    "structured_array": "record",
    "dataframe": "event",
    "grouped": "event",
    "side_effect": "event",
    "intermediate": "record",
}


def _lineage_node_kind(data: Mapping[str, Any]) -> str:
    """Translate canonical lineage metadata into the Next domain palette."""

    if bool(data.get("isLineageVirtual")):
        return "virtual"
    plugin_set = str(data.get("pluginSet", ""))
    if plugin_set in _LINEAGE_KIND_BY_PLUGIN_SET:
        return _LINEAGE_KIND_BY_PLUGIN_SET[plugin_set]
    source_kind = str(data.get("kind", ""))
    if source_kind in {"raw", "record", "signal", "peak", "event"}:
        return source_kind
    return _LINEAGE_KIND_BY_VISUAL_CATEGORY.get(source_kind, "record")


def _lineage_payload(
    plugin_generator: PluginDocGenerator,
    plugins: list[Any],
    dependencies: dict[str, list[str]],
) -> dict[str, Any]:
    # The existing lineage facts builder is independent from HTML and remains
    # the single source for plugin ports, dtypes, edges, relations, and views.
    payload = plugin_generator._build_cytoscape_lineage_payload(
        plugins, dependencies, plugin_href_prefix="/plugins/"
    )
    result = _json_value(payload)
    if not isinstance(result, dict):
        raise SiteModelError("Lineage payload is not serializable")
    by_provides = {str(getattr(plugin, "provides", "")): plugin for plugin in plugins}
    nodes: list[dict[str, Any]] = []
    for entry in result.get("nodes", []):
        data = entry.get("data", {}) if isinstance(entry, dict) else {}
        if not isinstance(data, dict):
            continue
        node_id = str(data.get("id", ""))
        plugin = by_provides.get(node_id)

        def ports(key: str, side: str) -> list[dict[str, str]]:
            values = data.get(key, [])
            return [
                {
                    "id": str(port.get("id", "")),
                    "name": str(port.get("name", port.get("id", ""))),
                    "dtype": str(port.get("dtype", "Unknown")),
                    "side": side,
                }
                for port in values
                if isinstance(port, dict)
            ]

        kind = _lineage_node_kind(data)
        nodes.append(
            {
                "id": node_id,
                "label": str(data.get("label", node_id)),
                "pluginClass": str(data.get("pluginClass", getattr(plugin, "name", node_id))),
                "kind": kind,
                "summary": _plain(data.get("summary") or getattr(plugin, "summary", "") or node_id),
                "version": str(getattr(plugin, "version", "")) or None,
                "inputs": ports("in_ports", "input"),
                "outputs": ports("out_ports", "output"),
            }
        )
    node_ids = {node["id"] for node in nodes}
    for node_id, plugin in sorted(by_provides.items()):
        if not node_id or node_id in node_ids:
            continue
        record = _plugin_record(plugin)
        nodes.append(
            {
                "id": node_id,
                "label": str(getattr(plugin, "name", node_id)),
                "pluginClass": str(getattr(plugin, "name", node_id)),
                "kind": "virtual",
                "summary": record["summary"],
                "version": record["version"],
                "inputs": [],
                "outputs": [
                    {
                        "id": f"{node_id}:output",
                        "name": node_id,
                        "dtype": record["outputKind"],
                        "side": "output",
                    }
                ],
            }
        )
        node_ids.add(node_id)
    edges: list[dict[str, Any]] = []
    for index, entry in enumerate(result.get("edges", [])):
        data = entry.get("data", {}) if isinstance(entry, dict) else {}
        if not isinstance(data, dict):
            continue
        source = str(data.get("source_node_id", ""))
        target = str(data.get("target_node_id", ""))
        if source not in node_ids or target not in node_ids:
            raise SiteModelError(f"lineage edge references an unknown node: {source} -> {target}")
        kind = str(data.get("kind", "main"))
        if kind not in {"main", "branch", "virtual"}:
            kind = "main"
        edges.append(
            {
                "id": str(data.get("id", f"edge-{index}")),
                "source": source,
                "sourcePort": str(data.get("source_port_id", "")),
                "target": target,
                "targetPort": str(data.get("target_port_id", "")),
                "dtype": str(data.get("dtype", "Unknown")),
                "kind": kind,
            }
        )
    overview = [str(value) for value in result.get("views", {}).get("overview", [])]
    full = [str(value) for value in result.get("views", {}).get("full", [])]
    full.extend(sorted(node_ids - set(full)))
    return {
        "nodes": nodes,
        "edges": edges,
        "views": {
            "overview": overview,
            "full": full,
        },
    }


def build_lineage_facts(
    plugin_generator: PluginDocGenerator | None = None,
    *,
    context: Any | None = None,
) -> dict[str, Any]:
    """Build static default or dynamic Context lineage facts.

    ``context`` is optional.  When supplied, only ``Context.get_lineage`` is
    consulted for dependency resolution; no plugin ``compute`` call and no data
    access is performed.
    """

    generator = plugin_generator or PluginDocGenerator()
    if context is not None:
        context_plugins = getattr(context, "_plugins", None)
        if not isinstance(context_plugins, dict) or not context_plugins:
            raise SiteModelError("Context must contain registered plugins")
        generator._plugins = [
            (plugin.__class__, plugin) for _, plugin in sorted(context_plugins.items())
        ]
        dependencies: dict[str, list[str]] = {}
        for provides in sorted(context_plugins):
            lineage = context.get_lineage(provides)
            direct = (lineage or {}).get("depends_on", {})
            dependencies[provides] = [str(name) for name in direct]
    else:
        if not getattr(generator, "_plugins", None):
            generator.load_builtin_plugins()
        dependencies = generator._default_dependency_map()
    plugins = generator._with_lineage_scores(
        generator.get_all_doc_info(), dependencies_by_provides=dependencies
    )
    return _lineage_payload(generator, plugins, dependencies)


def _route_record(route: str, kind: str, title: str, source: str | None = None) -> dict[str, Any]:
    return {"route": canonical_route(route), "kind": kind, "title": title, "source": source}


def _search_entry(
    title: str, summary: str, kind: str, url: str, keywords: str = ""
) -> dict[str, str]:
    route = canonical_route(url.split("#", 1)[0])
    fragment = f"#{url.split('#', 1)[1]}" if "#" in url else ""
    return {
        "title": _plain(title),
        "summary": _plain(summary),
        "kind": _plain(kind),
        "url": route + fragment,
        "keywords": _plain(keywords),
    }


def _register_route(routes: dict[str, dict[str, Any]], record: dict[str, Any]) -> None:
    route = record["route"]
    previous = routes.get(route)
    if previous is None:
        routes[route] = record
        return
    # The manifest intentionally describes a reflected index page which is also
    # a generated collection index.  It is one public route, not a conflict.
    if route in {
        "/contexts/index/",
        "/contexts/",
        "/contexts/context/",
        "/adapters/adapter/",
        "/accessors/index/",
        "/accessors/",
        "/accessors/peak-channel-accessor/",
        "/accessors/s1-s2-pair-accessor/",
        "/accessors/records-view/",
        "/visualizations/index/",
        "/visualizations/",
        "/plugins/",
        "/visualizations/statistical-plots/",
        "/visualizations/waveform-plots/",
        "/visualizations/position-dashboard/",
    }:
        return
    raise SiteModelError(
        f"Duplicate site route {route!r}: {previous.get('source') or previous.get('kind')} and "
        f"{record.get('source') or record.get('kind')}"
    )


def build_site_model(
    project_root: Path | None = None,
    *,
    guide_manifest_path: Path | None = None,
    plugin_generator: PluginDocGenerator | None = None,
) -> dict[str, Any]:
    """Build and validate the complete ``site-model/v1`` JSON object."""

    root = Path(project_root or Path.cwd()).resolve()
    generator = plugin_generator or PluginDocGenerator()
    if not getattr(generator, "_plugins", None):
        generator.load_builtin_plugins()
    plugin_views = generator._with_lineage_scores(
        generator.get_all_doc_info(), dependencies_by_provides=generator._default_dependency_map()
    )
    plugins = [_plugin_record(view) for view in plugin_views]

    guide_sections = build_guide_facts(guide_manifest_path, project_root=root)
    routes: dict[str, dict[str, Any]] = {}
    _register_route(routes, _route_record("/", "home", "WaveformAnalysis"))
    _register_route(routes, _route_record("/plugins", "plugin", "插件参考"))
    _register_route(routes, _route_record("/lineage", "lineage", "插件谱系"))
    _register_route(routes, _route_record("/accessors", "accessor", "Accessor 接口"))
    _register_route(routes, _route_record("/contexts", "context", "Context 与适配器"))
    _register_route(routes, _route_record("/adapters", "context", "DAQ 适配器"))
    _register_route(routes, _route_record("/visualizations", "visualization", "可视化"))
    for plugin in plugins:
        _register_route(
            routes,
            _route_record(plugin["route"], "plugin", plugin["pluginClass"], plugin["provides"]),
        )

    accessors = [_accessor_contract(spec) for spec in ACCESSOR_DOCUMENTATION_REGISTRY]
    accessors.append(_callable_contract(RECORDS_VIEW_DOCUMENTATION_PAGE, section="accessors"))
    selection_by_slug = {
        item.slug: {
            "entry": item.entry,
            "question": item.question,
            "scenario": item.scenario,
        }
        for item in ACCESSOR_SELECTION_GUIDE
    }
    for accessor in accessors:
        try:
            accessor["selection"] = selection_by_slug[accessor["slug"]]
        except KeyError as exc:
            raise SiteModelError(
                f"Accessor selection guide is missing {accessor['slug']!r}"
            ) from exc
    for accessor in accessors:
        _register_route(routes, _route_record(accessor["route"], "accessor", accessor["name"]))
    context_specs = [(CONTEXT_DOCUMENTATION_PAGE, "contexts")]
    context_pages = [_callable_contract(spec, section=section) for spec, section in context_specs]
    adapter_pages = [_callable_contract(ADAPTER_DOCUMENTATION_PAGE, section="adapters")]
    visualization_pages = [
        _visualization_contract(spec) for spec in VISUALIZATION_DOCUMENTATION_PAGES
    ]
    for page in [*context_pages, *adapter_pages, *visualization_pages]:
        kind = "visualization" if page in visualization_pages else "context"
        _register_route(routes, _route_record(page["route"], kind, page["name"]))

    navigation: list[dict[str, Any]] = [
        {
            "id": "overview",
            "title": "概览",
            "items": [
                {"label": "首页", "href": "/", "icon": "home"},
                {"label": "插件谱系", "href": "/lineage/", "icon": "lineage"},
            ],
        },
        {
            "id": "reference",
            "title": "参考",
            "items": [
                {"label": "插件", "href": "/plugins/", "icon": "plugin"},
                {"label": "Context", "href": "/contexts/", "icon": "context"},
                {"label": "Accessor", "href": "/accessors/", "icon": "accessor"},
                {"label": "可视化", "href": "/visualizations/", "icon": "visualization"},
            ],
        },
    ]
    source_routes = _guide_source_routes(guide_sections, root, plugins)
    guides, source_indexes = _guide_models_from_sections(
        guide_sections,
        project_root=root,
        source_routes=source_routes,
    )
    for section in guide_sections:
        if not any(item["href"] == section["route"] for item in navigation[1]["items"]):
            navigation[1]["items"].append(
                {"label": section["title"], "href": section["route"], "icon": "guide"}
            )

    for section in guide_sections:
        section_pages = []
        for page in section["pages"]:
            page_record = _route_record(
                page["route"],
                "guide",
                page["title"],
                page.get("source"),
            )
            _register_route(routes, page_record)
            section_pages.append(page_record)
        index_record = _route_record(section["route"], "guide-index", section["title"])
        _register_route(routes, index_record)
        if section["id"] == "cli":
            navigation_item = next(
                item for item in navigation[1]["items"] if item["href"] == section["route"]
            )
            navigation_item["children"] = [
                {
                    "label": page["title"],
                    "href": page["route"],
                    "icon": "file",
                }
                for page in section_pages
            ]
        # Keep route ownership and navigation explicit; Markdown body sections
        # live in the separate guides collection below.
        section["pages"] = section_pages

    model: dict[str, Any] = {
        "schema": SITE_MODEL_VERSION,
        "modelVersion": "1.2.0",
        "project": {
            "name": "WaveformAnalysis",
            "version": _package_version(),
            "tagline": "可审计、离线优先的科学波形分析文档。",
        },
        "provenance": "generated",
        "routes": [
            {
                "path": record["route"],
                "title": record["title"],
                "kind": (
                    record["kind"]
                    if record["kind"]
                    in {
                        "home",
                        "plugin",
                        "context",
                        "accessor",
                        "visualization",
                        "lineage",
                        "guide",
                    }
                    else "guide"
                ),
            }
            for _, record in sorted(routes.items())
        ],
        "navigation": navigation,
        "plugins": sorted(plugins, key=lambda item: item["provides"]),
        "contexts": [*context_pages, *adapter_pages],
        "accessors": accessors,
        "visualizations": visualization_pages,
        "guides": guides,
        "source_indexes": source_indexes,
        "lineage": build_lineage_facts(generator),
    }
    validate_site_model(model)
    return model


def validate_site_model(model: Mapping[str, Any]) -> None:
    """Validate contract shape and invariants without requiring jsonschema."""

    if not isinstance(model, Mapping):
        raise SiteModelError("site model must be a JSON object")
    if model.get("schema") != SITE_MODEL_VERSION:
        raise SiteModelError(f"site model schema must be {SITE_MODEL_VERSION!r}")
    required = {
        "routes",
        "navigation",
        "plugins",
        "contexts",
        "accessors",
        "visualizations",
        "guides",
        "source_indexes",
        "lineage",
        "project",
        "modelVersion",
        "provenance",
    }
    missing = sorted(required.difference(model))
    if missing:
        raise SiteModelError("site model is missing required fields: " + ", ".join(missing))
    routes = model["routes"]
    if not isinstance(routes, list) or not routes:
        raise SiteModelError("site model routes must be a non-empty list")
    seen: set[str] = set()
    valid_kinds = {"home", "plugin", "context", "accessor", "visualization", "lineage", "guide"}
    for index, record in enumerate(routes):
        if not isinstance(record, Mapping):
            raise SiteModelError(f"routes[{index}] must be an object")
        route = canonical_route(str(record.get("path", "")), field=f"routes[{index}].path")
        if route in seen:
            raise SiteModelError(f"Duplicate site route {route!r}")
        seen.add(route)
        kind = record.get("kind")
        if kind not in valid_kinds:
            raise SiteModelError(f"routes[{index}].kind is not supported: {kind!r}")

    def validate_navigation_items(items: Any, *, path: str) -> None:
        if not isinstance(items, list):
            raise SiteModelError(f"{path} must be an array")
        for item_index, item in enumerate(items):
            item_path = f"{path}[{item_index}]"
            if not isinstance(item, Mapping):
                raise SiteModelError(f"{item_path} must be an object")
            for key in ("label", "href", "icon"):
                if not isinstance(item.get(key), str) or not item[key]:
                    raise SiteModelError(f"{item_path}.{key} must be a non-empty string")
            href = canonical_route(item["href"], field=f"{item_path}.href")
            if href not in seen:
                raise SiteModelError(f"{item_path}.href references an unknown route {href!r}")
            if "children" in item:
                validate_navigation_items(item["children"], path=f"{item_path}.children")

    navigation = model["navigation"]
    if not isinstance(navigation, list):
        raise SiteModelError("site model navigation must be an array")
    for section_index, section in enumerate(navigation):
        if not isinstance(section, Mapping):
            raise SiteModelError(f"navigation[{section_index}] must be an object")
        validate_navigation_items(section.get("items"), path=f"navigation[{section_index}].items")
    if model.get("provenance") not in {"generated", "fixture"}:
        raise SiteModelError("site model provenance must be generated or fixture")
    project = model["project"]
    if not isinstance(project, Mapping) or not all(
        isinstance(project.get(key), str) and project.get(key)
        for key in ("name", "version", "tagline")
    ):
        raise SiteModelError("site model project must contain name, version, and tagline")
    records = [
        item
        for item in model["plugins"]
        if isinstance(item, Mapping) and item.get("provides") == "records"
    ]
    if records:
        record = records[0]
        if (
            record.get("version") != "0.14.2"
            or not record.get("dependsOn")
            or record["dependsOn"][0] != "raw_files"
        ):
            raise SiteModelError(
                "records plugin must be v0.14.2 with raw_files as its first dependency"
            )
    if not any(
        route.get("path") == "/plugins/records/" and route.get("kind") == "plugin"
        for route in routes
        if isinstance(route, Mapping)
    ):
        raise SiteModelError("records plugin route is missing")
    lineage = model["lineage"]
    if (
        not isinstance(lineage, Mapping)
        or not isinstance(lineage.get("nodes"), list)
        or not isinstance(lineage.get("edges"), list)
    ):
        raise SiteModelError("lineage must contain nodes and edges arrays")
    json.dumps(_json_value(model), ensure_ascii=False, allow_nan=False)
    if SITE_MODEL_SCHEMA_PATH.is_file():
        try:
            import jsonschema
        except ImportError:
            return
        try:
            schema = json.loads(SITE_MODEL_SCHEMA_PATH.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(_json_value(model))
        except jsonschema.ValidationError as exc:
            raise SiteModelError(
                f"site model JSON schema validation failed: {exc.message}"
            ) from exc


def model_json_bytes(model: Mapping[str, Any]) -> bytes:
    """Return canonical UTF-8 JSON bytes for hashing and build inputs."""

    validate_site_model(model)
    return (
        json.dumps(_json_value(model), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def site_model_sha256(model: Mapping[str, Any]) -> str:
    return hashlib.sha256(model_json_bytes(model)).hexdigest()


def write_site_model(model: Mapping[str, Any], path: Path) -> Path:
    """Atomically write a validated model and return its resolved path."""

    payload = model_json_bytes(model)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(destination)
    return destination


def load_site_model(path: Path, *, validate: bool = True) -> dict[str, Any]:
    model = json.loads(Path(path).read_text(encoding="utf-8"))
    if validate:
        validate_site_model(model)
    return model


__all__ = [
    "SITE_MODEL_VERSION",
    "SITE_MODEL_SCHEMA_VERSION",
    "SITE_MODEL_KIND",
    "SITE_MODEL_FILENAME",
    "SITE_MODEL_SCHEMA_FILENAME",
    "SITE_MODEL_SCHEMA_PATH",
    "SITE_MODEL_ENV",
    "SITE_MODEL_ENV_ALIASES",
    "SITE_MODEL_EXPORT_ENV",
    "SiteModelError",
    "build_guide_facts",
    "build_lineage_facts",
    "build_site_model",
    "canonical_route",
    "load_site_model",
    "model_json_bytes",
    "route_without_leading_slash",
    "site_model_sha256",
    "validate_site_model",
    "write_site_model",
]
