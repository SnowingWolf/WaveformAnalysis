"""Manifest-driven Markdown guides for the offline documentation site."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
import posixpath
from pathlib import Path, PurePosixPath
import re
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml


@dataclass(frozen=True)
class GuidePageSpec:
    source: Path
    source_label: str
    route: str
    section_id: str


@dataclass(frozen=True)
class GuideSectionSpec:
    section_id: str
    title: str
    index_route: str
    source_indexes: tuple[Path, ...]
    pages: tuple[GuidePageSpec, ...]


@dataclass(frozen=True)
class GuideManifest:
    project_root: Path
    docs_root: Path
    sections: tuple[GuideSectionSpec, ...]


@dataclass(frozen=True)
class GuideHeading:
    level: int
    title: str
    anchor: str


@dataclass(frozen=True)
class GuideAsset:
    source: Path
    route: str


@dataclass(frozen=True)
class RenderedGuidePage:
    source: Path
    source_label: str
    route: str
    section_id: str
    title: str
    summary: str
    html: str
    has_mermaid: bool
    headings: tuple[GuideHeading, ...]
    assets: tuple[GuideAsset, ...]


@dataclass(frozen=True)
class RenderedGuideSection:
    section_id: str
    title: str
    index_route: str
    pages: tuple[RenderedGuidePage, ...]


@dataclass(frozen=True)
class RenderedGuideSite:
    sections: tuple[RenderedGuideSection, ...]
    warnings: tuple[str, ...]


class _PlainTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_text(value: str) -> str:
    parser = _PlainTextParser()
    parser.feed(value)
    return " ".join("".join(parser.parts).split())


def _validated_route(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    route = PurePosixPath(value)
    if route.is_absolute() or ".." in route.parts or route.suffix != ".html":
        raise ValueError(f"{field} must be a relative .html path without '..': {value!r}")
    return route.as_posix()


def _validated_source(project_root: Path, docs_root: Path, value: Any, *, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    source = (project_root / value).resolve()
    if not source.is_relative_to(docs_root):
        raise ValueError(f"{field} must stay inside {docs_root}: {value!r}")
    if not source.is_file() or source.suffix.lower() != ".md":
        raise ValueError(f"{field} must reference an existing Markdown file: {value!r}")
    return source


def load_guide_manifest(manifest_path: Path) -> GuideManifest:
    """Load and strictly validate one guide publication manifest."""
    manifest_path = Path(manifest_path).resolve()
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("site guide manifest must declare schema_version: 1")
    raw_sections = raw.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError("site guide manifest must contain a non-empty sections list")

    project_root = manifest_path.parent.parent.resolve()
    docs_root = (project_root / "docs").resolve()
    sections: list[GuideSectionSpec] = []
    section_ids: set[str] = set()
    sources: set[Path] = set()
    routes: set[str] = set()
    for section_index, raw_section in enumerate(raw_sections):
        if not isinstance(raw_section, dict):
            raise ValueError(f"sections[{section_index}] must be a mapping")
        section_id = raw_section.get("id")
        if not isinstance(section_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", section_id):
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
        if index_route in routes:
            raise ValueError(f"Duplicate guide route: {index_route}")
        routes.add(index_route)

        raw_source_indexes = raw_section.get("source_indexes", [])
        if not isinstance(raw_source_indexes, list):
            raise ValueError(f"sections[{section_index}].source_indexes must be a list")
        source_indexes = tuple(
            _validated_source(
                project_root,
                docs_root,
                value,
                field=f"sections[{section_index}].source_indexes",
            )
            for value in raw_source_indexes
        )
        raw_pages = raw_section.get("pages")
        if not isinstance(raw_pages, list) or not raw_pages:
            raise ValueError(f"sections[{section_index}].pages must be a non-empty list")
        pages: list[GuidePageSpec] = []
        for page_index, raw_page in enumerate(raw_pages):
            if not isinstance(raw_page, dict):
                raise ValueError(f"sections[{section_index}].pages[{page_index}] must be a mapping")
            source_value = raw_page.get("source")
            source = _validated_source(
                project_root,
                docs_root,
                source_value,
                field=f"sections[{section_index}].pages[{page_index}].source",
            )
            route = _validated_route(
                raw_page.get("route"),
                field=f"sections[{section_index}].pages[{page_index}].route",
            )
            if source in sources:
                raise ValueError(f"Duplicate guide source: {source_value}")
            if route in routes:
                raise ValueError(f"Duplicate guide route: {route}")
            sources.add(source)
            routes.add(route)
            pages.append(
                GuidePageSpec(
                    source=source,
                    source_label=str(source_value),
                    route=route,
                    section_id=section_id,
                )
            )
        sections.append(
            GuideSectionSpec(
                section_id=section_id,
                title=title.strip(),
                index_route=index_route,
                source_indexes=source_indexes,
                pages=tuple(pages),
            )
        )
    return GuideManifest(project_root=project_root, docs_root=docs_root, sections=tuple(sections))


def _relative_href(current_route: str, target_route: str, fragment: str = "") -> str:
    current_dir = PurePosixPath(current_route).parent.as_posix()
    href = posixpath.relpath(target_route, current_dir)
    return f"{href}#{fragment}" if fragment else href


def _plugin_reference_route(source: Path, docs_root: Path) -> str | None:
    relative = source.relative_to(docs_root).as_posix()
    prefixes = ("plugins/reference/agent/", "plugins/reference/builtin/auto/")
    for prefix in prefixes:
        if relative.startswith(prefix):
            name = source.stem
            return "plugins/index.html" if name == "INDEX" else f"plugins/{name}.html"
    return None


class _GuideRenderer:
    """Mistune renderer wrapper with route-aware links and stable heading ids."""

    def __init__(
        self,
        *,
        page: GuidePageSpec,
        manifest: GuideManifest,
        source_routes: dict[Path, str],
        source_index_routes: dict[Path, str],
        warnings: list[str],
    ):
        try:
            import mistune
        except ImportError as exc:
            raise RuntimeError(
                "site-web Markdown guides require Mistune. Install the documentation extra: "
                'pip install -e ".[docgen]"'
            ) from exc

        outer = self

        class Renderer(mistune.HTMLRenderer):
            def __init__(self):
                # Documentation Markdown is repository-controlled source. Keep raw HTML
                # available for semantic elements such as <details> and <kbd>.
                super().__init__(escape=False)
                self.title = ""
                self.summary = ""
                self.headings: list[GuideHeading] = []
                self.assets: dict[str, GuideAsset] = {}
                self.has_mermaid = False
                self._heading_counts: dict[str, int] = {}

            def heading(self, text: str, level: int, **attrs: Any) -> str:
                plain = _plain_text(text)
                slug = re.sub(r"[^\w\s-]", "", plain.casefold(), flags=re.UNICODE)
                slug = re.sub(r"[\s-]+", "-", slug).strip("-") or "section"
                count = self._heading_counts.get(slug, 0)
                self._heading_counts[slug] = count + 1
                anchor = slug if count == 0 else f"{slug}-{count + 1}"
                self.headings.append(GuideHeading(level=level, title=plain, anchor=anchor))
                if level == 1 and not self.title:
                    self.title = plain
                return f'<h{level} id="{escape(anchor, quote=True)}">{text}</h{level}>\n'

            def paragraph(self, text: str) -> str:
                plain = _plain_text(text)
                if plain.removeprefix("导航").lstrip().startswith(":"):
                    return ""
                if not self.summary and plain:
                    self.summary = plain
                return super().paragraph(text)

            def link(self, text: str, url: str, title: str | None = None) -> str:
                href = outer.resolve_url(url, is_image=False, assets=self.assets)
                if href is None:
                    message = f"未收录 Markdown 链接: {page.source_label} -> {url}"
                    if message not in warnings:
                        warnings.append(message)
                    return (
                        '<span class="guide-link-unavailable" '
                        f'title="{escape(message, quote=True)}">{text}</span>'
                    )
                return super().link(text, href, title)

            def image(self, text: str, url: str, title: str | None = None) -> str:
                href = outer.resolve_url(url, is_image=True, assets=self.assets)
                if href is None:
                    raise ValueError(f"Guide image cannot be omitted: {page.source_label} -> {url}")
                return super().image(text, href, title)

            def block_code(self, code: str, info: str | None = None) -> str:
                language = (info or "").strip().split(None, 1)[0].lower()
                if language == "mermaid":
                    self.has_mermaid = True
                    escaped_code = escape(code)
                    return (
                        '<div class="mermaid-block" data-mermaid-block>'
                        '<pre class="mermaid-source"><code>'
                        f"{escaped_code}</code></pre>"
                        '<div class="mermaid-render" data-mermaid-render '
                        'aria-label="Mermaid 图表"></div>'
                        '<p class="mermaid-error" data-mermaid-error hidden>'
                        "图表渲染失败，已保留 Mermaid 源码。</p></div>\n"
                    )
                if language in {"py", "python"}:
                    try:
                        from pygments import highlight
                        from pygments.formatters import HtmlFormatter
                        from pygments.lexers import PythonLexer
                    except ImportError as exc:
                        raise RuntimeError(
                            "Python guide code blocks require Pygments. Install the documentation extra: "
                            'pip install -e ".[docgen]"'
                        ) from exc
                    highlighted = highlight(
                        code,
                        PythonLexer(),
                        HtmlFormatter(nowrap=True),
                    )
                    return (
                        '<pre class="code-block language-python"><code>'
                        f"{highlighted}</code></pre>\n"
                    )
                return super().block_code(code, info)

        self.page = page
        self.manifest = manifest
        self.source_routes = source_routes
        self.source_index_routes = source_index_routes
        self.renderer = Renderer()
        self.markdown = mistune.create_markdown(
            renderer=self.renderer,
            plugins=["table", "footnotes"],
        )

    def resolve_url(self, url: str, *, is_image: bool, assets: dict[str, GuideAsset]) -> str | None:
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc:
            return url
        if not parsed.path:
            return f"#{unquote(parsed.fragment)}" if parsed.fragment else url
        target = (self.page.source.parent / unquote(parsed.path)).resolve()
        if not target.is_relative_to(self.manifest.project_root):
            raise ValueError(
                f"Guide link escapes the repository: {self.page.source_label} -> {url}"
            )
        if not target.is_relative_to(self.manifest.docs_root):
            if is_image:
                raise ValueError(
                    f"Guide image must stay inside docs/: {self.page.source_label} -> {url}"
                )
            return None
        if target.suffix.lower() == ".md":
            target_route = self.source_routes.get(target) or self.source_index_routes.get(target)
            if target == self.manifest.docs_root / "README.md":
                target_route = "index.html"
            target_route = target_route or _plugin_reference_route(target, self.manifest.docs_root)
            if target_route is None:
                return None
            return _relative_href(self.page.route, target_route, unquote(parsed.fragment))
        if not target.is_file():
            if is_image:
                raise ValueError(f"Guide asset does not exist: {self.page.source_label} -> {url}")
            return None
        asset_route = f"assets/content/{target.relative_to(self.manifest.docs_root).as_posix()}"
        assets[asset_route] = GuideAsset(source=target, route=asset_route)
        return _relative_href(self.page.route, asset_route, unquote(parsed.fragment))

    def render(self) -> RenderedGuidePage:
        rendered = self.markdown(self.page.source.read_text(encoding="utf-8"))
        if not self.renderer.title:
            raise ValueError(f"Guide source must contain an H1 heading: {self.page.source_label}")
        return RenderedGuidePage(
            source=self.page.source,
            source_label=self.page.source_label,
            route=self.page.route,
            section_id=self.page.section_id,
            title=self.renderer.title,
            summary=self.renderer.summary or self.renderer.title,
            html=rendered,
            has_mermaid=self.renderer.has_mermaid,
            headings=tuple(self.renderer.headings),
            assets=tuple(self.renderer.assets.values()),
        )


def render_guide_manifest(manifest: GuideManifest) -> RenderedGuideSite:
    """Render all explicitly selected pages and return navigation/search metadata."""
    source_routes = {
        page.source: page.route for section in manifest.sections for page in section.pages
    }
    source_index_routes = {
        source: section.index_route
        for section in manifest.sections
        for source in section.source_indexes
    }
    warnings: list[str] = []
    rendered_sections = []
    for section in manifest.sections:
        pages = tuple(
            _GuideRenderer(
                page=page,
                manifest=manifest,
                source_routes=source_routes,
                source_index_routes=source_index_routes,
                warnings=warnings,
            ).render()
            for page in section.pages
        )
        rendered_sections.append(
            RenderedGuideSection(
                section_id=section.section_id,
                title=section.title,
                index_route=section.index_route,
                pages=pages,
            )
        )
    return RenderedGuideSite(sections=tuple(rendered_sections), warnings=tuple(warnings))
