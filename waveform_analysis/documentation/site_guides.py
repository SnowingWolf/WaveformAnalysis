"""Strict, HTML-free manifest parser for the Next documentation site."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
import re
from typing import Any

import yaml

_SECTION_ID = re.compile(r"[a-z][a-z0-9-]*")
_ROUTE = re.compile(r"/(?:[A-Za-z0-9._~-]+/)*")
_TAGS = {"markdown", "reflect", "plugin-provider"}
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.DOTALL)


@dataclass(frozen=True)
class GuidePageSpec:
    source: Path | None
    source_label: str
    route: str
    section_id: str
    tag: str = "markdown"
    title_override: str | None = None
    summary_override: str | None = None
    nav_weight: int = 0


@dataclass(frozen=True)
class GuideSectionSpec:
    section_id: str
    title: str
    index_route: str
    pages: tuple[GuidePageSpec, ...]
    source_indexes: tuple[Path, ...] = ()
    nav_weight: int = 0


@dataclass(frozen=True)
class GuideManifest:
    project_root: Path
    docs_root: Path
    sections: tuple[GuideSectionSpec, ...]
    provider_pages: tuple[GuidePageSpec, ...] = ()


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return YAML frontmatter and the untouched Markdown body."""

    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text
    values = yaml.safe_load(match.group(1))
    if values is None:
        values = {}
    if not isinstance(values, dict):
        raise ValueError("Markdown frontmatter must be a mapping")
    return values, text[match.end() :]


def _validated_route(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty canonical route")
    if ".html" in value or "?" in value or "#" in value or "\\" in value:
        raise ValueError(f"{field} must be an extensionless canonical route: {value!r}")
    path = PurePosixPath(value)
    if not value.startswith("/") or not value.endswith("/") or ".." in path.parts:
        raise ValueError(f"{field} must use leading and trailing slashes without '..': {value!r}")
    if not _ROUTE.fullmatch(value):
        raise ValueError(f"{field} contains unsupported route characters: {value!r}")
    return value


def _validated_source(project_root: Path, docs_root: Path, value: Any, *, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty Markdown path")
    source = (project_root / value).resolve()
    if not source.is_relative_to(docs_root):
        raise ValueError(f"{field} must stay inside {docs_root}: {value!r}")
    if not source.is_file() or source.suffix.lower() != ".md":
        raise ValueError(f"{field} must be an existing Markdown file: {value!r}")
    return source


def _optional_str(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _validated_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _validated_tag(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or value not in _TAGS:
        raise ValueError(f"{field} must be one of {sorted(_TAGS)}")
    return value


def _derived_route(source: Path, docs_root: Path) -> str:
    relative = source.relative_to(docs_root).with_suffix("").as_posix()
    return f"/{relative}/"


def load_guide_manifest(manifest_path: Path) -> GuideManifest:
    """Load canonical guide facts without rendering Markdown or HTML."""

    path = Path(manifest_path).resolve()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("site guide manifest must be a mapping")
    if raw.get("schema_version") != 2:
        raise ValueError("site guide manifest must declare schema_version: 2")
    raw_sections = raw.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError("site guide manifest must contain a non-empty sections list")

    project_root = path.parent.parent.resolve()
    docs_root = (project_root / "docs").resolve()
    sections: list[GuideSectionSpec] = []
    providers: list[GuidePageSpec] = []
    section_ids: set[str] = set()
    sources: set[Path] = set()
    routes: set[str] = set()

    def register_route(route: str) -> None:
        if route in routes:
            raise ValueError(f"Duplicate guide route: {route}")
        routes.add(route)

    for section_index, raw_section in enumerate(raw_sections):
        if not isinstance(raw_section, dict):
            raise ValueError(f"sections[{section_index}] must be a mapping")
        section_id = raw_section.get("id")
        if not isinstance(section_id, str) or not _SECTION_ID.fullmatch(section_id):
            raise ValueError(f"sections[{section_index}].id must be a lowercase route id")
        if section_id in section_ids:
            raise ValueError(f"Duplicate guide section id: {section_id}")
        section_ids.add(section_id)
        title = raw_section.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"sections[{section_index}].title must be a non-empty string")
        index_route = _validated_route(
            raw_section.get("index_route"), field=f"sections[{section_index}].index_route"
        )
        register_route(index_route)
        nav_weight = _validated_int(
            raw_section.get("nav_weight", 0), field=f"sections[{section_index}].nav_weight"
        )

        raw_indexes = raw_section.get("source_indexes", [])
        if not isinstance(raw_indexes, list):
            raise ValueError(f"sections[{section_index}].source_indexes must be a list")
        source_indexes = [
            _validated_source(
                project_root, docs_root, value, field=f"sections[{section_index}].source_indexes"
            )
            for value in raw_indexes
        ]

        page_specs: list[GuidePageSpec] = []
        raw_pages = raw_section.get("pages", [])
        if not isinstance(raw_pages, list):
            raise ValueError(f"sections[{section_index}].pages must be a list")
        for page_index, raw_page in enumerate(raw_pages):
            if not isinstance(raw_page, dict):
                raise ValueError(f"sections[{section_index}].pages[{page_index}] must be a mapping")
            field = f"sections[{section_index}].pages[{page_index}]"
            tag = _validated_tag(raw_page.get("tag", "markdown"), field=f"{field}.tag")
            source_value = raw_page.get("source")
            source = None
            if source_value is not None:
                source = _validated_source(
                    project_root, docs_root, source_value, field=f"{field}.source"
                )
                if source in sources:
                    raise ValueError(f"Duplicate guide source: {source_value}")
                sources.add(source)
            if tag == "markdown" and source is None:
                raise ValueError(f"{field}.source is required for markdown pages")
            route = _validated_route(raw_page.get("route"), field=f"{field}.route")
            register_route(route)
            spec = GuidePageSpec(
                source=source,
                source_label=str(source_value or route),
                route=route,
                section_id=section_id,
                tag=tag,
                title_override=_optional_str(raw_page.get("title"), field=f"{field}.title"),
                summary_override=_optional_str(raw_page.get("summary"), field=f"{field}.summary"),
                nav_weight=_validated_int(
                    raw_page.get("nav_weight", 0), field=f"{field}.nav_weight"
                ),
            )
            page_specs.append(spec)
            if tag != "markdown":
                providers.append(spec)

        source_dirs = raw_section.get("source_dirs", [])
        excludes = raw_section.get("exclude", [])
        if not isinstance(source_dirs, list) or not isinstance(excludes, list):
            raise ValueError(f"sections[{section_index}].source_dirs and exclude must be lists")
        for dir_index, value in enumerate(source_dirs):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"sections[{section_index}].source_dirs[{dir_index}] must be a path"
                )
            base = (project_root / value).resolve()
            if not base.is_relative_to(docs_root) or not base.is_dir():
                raise ValueError(
                    f"sections[{section_index}].source_dirs[{dir_index}] must stay inside docs"
                )
            for source in sorted(base.rglob("*.md")):
                relative = source.relative_to(docs_root).as_posix()
                if source.name == "README.md":
                    if source not in source_indexes:
                        source_indexes.append(source)
                    continue
                if any(fnmatch(relative, str(pattern)) for pattern in excludes):
                    continue
                if source in sources:
                    continue
                frontmatter, _ = parse_frontmatter(source.read_text(encoding="utf-8"))
                if frontmatter.get("exclude_from_nav") or frontmatter.get("hidden"):
                    continue
                tag = _validated_tag(
                    frontmatter.get("tag", "markdown"), field=f"frontmatter tag in {relative}"
                )
                route = _derived_route(source, docs_root)
                register_route(route)
                sources.add(source)
                spec = GuidePageSpec(
                    source=source,
                    source_label=relative,
                    route=route,
                    section_id=section_id,
                    tag=tag,
                    title_override=_optional_str(
                        frontmatter.get("title"), field=f"frontmatter title in {relative}"
                    ),
                    summary_override=_optional_str(
                        frontmatter.get("summary"), field=f"frontmatter summary in {relative}"
                    ),
                    nav_weight=_validated_int(
                        frontmatter.get("nav_weight", 0),
                        field=f"frontmatter nav_weight in {relative}",
                    ),
                )
                page_specs.append(spec)
                if tag != "markdown":
                    providers.append(spec)

        page_specs.sort(key=lambda item: (item.nav_weight, item.route))
        sections.append(
            GuideSectionSpec(
                section_id=section_id,
                title=title.strip(),
                index_route=index_route,
                pages=tuple(page_specs),
                source_indexes=tuple(source_indexes),
                nav_weight=nav_weight,
            )
        )

    sections.sort(key=lambda item: (item.nav_weight, item.section_id))
    return GuideManifest(project_root, docs_root, tuple(sections), tuple(providers))


__all__ = [
    "GuideManifest",
    "GuidePageSpec",
    "GuideSectionSpec",
    "load_guide_manifest",
    "parse_frontmatter",
]
