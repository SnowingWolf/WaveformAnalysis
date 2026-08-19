"""Manifest-driven Markdown guides for the offline documentation site."""

from __future__ import annotations

from dataclasses import dataclass, replace
from html import escape
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import posixpath
import re
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml


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
    source_indexes: tuple[Path, ...]
    pages: tuple[GuidePageSpec, ...]
    nav_weight: int = 0


@dataclass(frozen=True)
class GuideManifest:
    project_root: Path
    docs_root: Path
    sections: tuple[GuideSectionSpec, ...]
    provider_pages: tuple[GuidePageSpec, ...] = ()


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
    source: Path | None
    source_label: str
    route: str
    section_id: str
    title: str
    summary: str
    html: str | None
    has_mermaid: bool
    headings: tuple[GuideHeading, ...]
    assets: tuple[GuideAsset, ...]
    tag: str = "markdown"
    source_relative: str | None = None
    prev_route: str | None = None
    prev_title: str | None = None
    next_route: str | None = None
    next_title: str | None = None


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
    provider_pages: tuple[GuidePageSpec, ...] = ()


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


_FRONTMATTER_PATTERN = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.DOTALL)
_VALID_TAGS = ("markdown", "reflect", "plugin-provider")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from Markdown body. Returns (frontmatter, body)."""
    match = _FRONTMATTER_PATTERN.match(text)
    if not match:
        return {}, text
    raw = yaml.safe_load(match.group(1))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("Markdown frontmatter must be a mapping")
    return raw, text[match.end() :]


def _validated_tag(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or value not in _VALID_TAGS:
        raise ValueError(f"{field} must be one of {_VALID_TAGS}: {value!r}")
    return value


def _derived_route(source: Path, docs_root: Path) -> str:
    plugin_route = _plugin_reference_route(source, docs_root)
    if plugin_route is not None:
        return plugin_route
    relative = source.relative_to(docs_root).as_posix()
    return relative[: -len(".md")] + ".html"


def _glob_match(relative: str, pattern: str) -> bool:
    pattern = pattern.strip()
    if not pattern:
        return False
    if "**" in pattern:
        regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        return re.fullmatch(regex, relative) is not None
    return re.fullmatch(re.escape(pattern).replace(r"\*", "[^/]*"), relative) is not None


def _iter_scanned_sources(
    *,
    source_dirs: list[Any],
    excludes: list[Any],
    project_root: Path,
    docs_root: Path,
    section_index: int,
) -> tuple[list[Path], list[Path]]:
    if not isinstance(excludes, list):
        raise ValueError(f"sections[{section_index}].exclude must be a list")
    exclude_patterns = [str(value) for value in excludes if isinstance(value, str)]
    collected: list[Path] = []
    skipped_readmes: list[Path] = []
    for dir_index, dir_value in enumerate(source_dirs):
        if not isinstance(dir_value, str) or not dir_value:
            raise ValueError(
                f"sections[{section_index}].source_dirs[{dir_index}] must be a non-empty string"
            )
        base = (project_root / dir_value).resolve()
        if not base.is_relative_to(docs_root):
            raise ValueError(
                f"sections[{section_index}].source_dirs[{dir_index}] must stay inside {docs_root}: "
                f"{dir_value!r}"
            )
        if not base.is_dir():
            raise ValueError(
                f"sections[{section_index}].source_dirs[{dir_index}] must be an existing directory: "
                f"{dir_value!r}"
            )
        for source in sorted(base.rglob("*.md")):
            relative = source.relative_to(docs_root).as_posix()
            if source.name == "README.md":
                # README files are deliberately not rendered as individual pages.  Keep
                # their directory as a link target, however, unless a broader exclude
                # removes that subtree.  The manifest's explicit **/README.md exclusion
                # only documents the skip and must not suppress this compatibility map.
                if any(
                    _glob_match(relative, pattern) and not pattern.rstrip("/").endswith("README.md")
                    for pattern in exclude_patterns
                ):
                    continue
                skipped_readmes.append(source)
                continue
            if any(_glob_match(relative, pattern) for pattern in exclude_patterns):
                continue
            collected.append(source)
    return collected, skipped_readmes


def _optional_str(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _validated_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def load_guide_manifest(manifest_path: Path) -> GuideManifest:
    """Load and strictly validate one guide publication manifest (schema v1 or v2).

    v2 扩展:
    - ``sections[].source_dirs`` 目录扫描(Markdown 自动收录)
    - ``sections[].exclude`` glob 排除
    - ``sections[].nav_weight`` 栏目排序
    - ``sections[].pages[].tag`` 页面来源声明,缺省 ``markdown``
    - 页面 frontmatter 控制:``title`` / ``summary`` / ``nav_weight`` /
      ``exclude_from_nav`` / ``hidden`` / ``tag``
    tag != ``markdown`` 的页面不渲染,只登记到 ``provider_pages``。
    """
    manifest_path = Path(manifest_path).resolve()
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("site guide manifest must be a mapping")
    if raw.get("schema_version") not in (1, 2):
        raise ValueError("site guide manifest must declare schema_version: 1 or 2")
    raw_sections = raw.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError("site guide manifest must contain a non-empty sections list")

    project_root = manifest_path.parent.parent.resolve()
    docs_root = (project_root / "docs").resolve()
    sections: list[GuideSectionSpec] = []
    provider_pages: list[GuidePageSpec] = []
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
        register_route(index_route)
        nav_weight = raw_section.get("nav_weight", 0)
        if isinstance(nav_weight, bool) or not isinstance(nav_weight, int):
            raise ValueError(f"sections[{section_index}].nav_weight must be an integer")

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

        raw_pages = raw_section.get("pages", [])
        if not isinstance(raw_pages, list):
            raise ValueError(f"sections[{section_index}].pages must be a list")
        pages: list[GuidePageSpec] = []
        for page_index, raw_page in enumerate(raw_pages):
            if not isinstance(raw_page, dict):
                raise ValueError(f"sections[{section_index}].pages[{page_index}] must be a mapping")
            field = f"sections[{section_index}].pages[{page_index}]"
            tag = _validated_tag(raw_page.get("tag", "markdown"), field=f"{field}.tag")
            source: Path | None = None
            source_value = raw_page.get("source")
            if source_value is not None:
                source = _validated_source(
                    project_root,
                    docs_root,
                    source_value,
                    field=f"{field}.source",
                )
                if source in sources:
                    raise ValueError(f"Duplicate guide source: {source_value}")
                sources.add(source)
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
            pages.append(spec)
            if tag != "markdown":
                provider_pages.append(spec)

        source_dirs = raw_section.get("source_dirs", [])
        if not isinstance(source_dirs, list):
            raise ValueError(f"sections[{section_index}].source_dirs must be a list")
        scanned_sources, scanned_readmes = _iter_scanned_sources(
            source_dirs=source_dirs,
            excludes=raw_section.get("exclude", []),
            project_root=project_root,
            docs_root=docs_root,
            section_index=section_index,
        )
        source_index_list = list(source_indexes)
        for readme in scanned_readmes:
            if readme not in source_index_list:
                source_index_list.append(readme)
        for source in scanned_sources:
            if source in sources:
                continue
            frontmatter, _ = parse_frontmatter(source.read_text(encoding="utf-8"))
            if frontmatter.get("exclude_from_nav") or frontmatter.get("hidden"):
                continue
            tag = _validated_tag(
                frontmatter.get("tag", "markdown"),
                field=f"frontmatter tag in {source.relative_to(docs_root).as_posix()}",
            )
            source_label = source.relative_to(docs_root).as_posix()
            route = _derived_route(source, docs_root)
            register_route(route)
            sources.add(source)
            spec = GuidePageSpec(
                source=source,
                source_label=source_label,
                route=route,
                section_id=section_id,
                tag=tag,
                title_override=_optional_str(
                    frontmatter.get("title"), field=f"frontmatter title in {source_label}"
                ),
                summary_override=_optional_str(
                    frontmatter.get("summary"), field=f"frontmatter summary in {source_label}"
                ),
                nav_weight=_validated_int(
                    frontmatter.get("nav_weight", 0),
                    field=f"frontmatter nav_weight in {source_label}",
                ),
            )
            pages.append(spec)
            if tag != "markdown":
                provider_pages.append(spec)

        sections.append(
            GuideSectionSpec(
                section_id=section_id,
                title=title.strip(),
                index_route=index_route,
                source_indexes=tuple(source_index_list),
                pages=tuple(pages),
                nav_weight=nav_weight,
            )
        )
    sections.sort(key=lambda section: section.nav_weight)
    return GuideManifest(
        project_root=project_root,
        docs_root=docs_root,
        sections=tuple(sections),
        provider_pages=tuple(provider_pages),
    )


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
                parts = (info or "").strip().split(None, 1)
                language = parts[0].lower() if parts else ""
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
        if self.page.source is None:
            raise ValueError(f"Guide page has no Markdown source: {self.page.route}")
        _frontmatter, body = parse_frontmatter(self.page.source.read_text(encoding="utf-8"))
        rendered = self.markdown(body)
        if not self.renderer.title and not self.page.title_override:
            raise ValueError(
                f"Guide source must contain an H1 heading or a frontmatter title: "
                f"{self.page.source_label}"
            )
        title = self.page.title_override or self.renderer.title
        summary = self.page.summary_override or self.renderer.summary or title
        return RenderedGuidePage(
            source=self.page.source,
            source_label=self.page.source_label,
            route=self.page.route,
            section_id=self.page.section_id,
            title=title,
            summary=summary,
            html=rendered,
            has_mermaid=self.renderer.has_mermaid,
            headings=tuple(self.renderer.headings),
            assets=tuple(self.renderer.assets.values()),
            source_relative=_source_relative(self.page, self.manifest),
        )


def _source_relative(page: GuidePageSpec, manifest: GuideManifest) -> str | None:
    if page.source is None:
        return None
    if page.source.is_relative_to(manifest.project_root):
        return page.source.relative_to(manifest.project_root).as_posix()
    return page.source_label


def _spec_title(page: GuidePageSpec) -> str:
    if page.title_override:
        return page.title_override
    if page.source is not None:
        frontmatter, body = parse_frontmatter(page.source.read_text(encoding="utf-8"))
        if isinstance(frontmatter.get("title"), str):
            return frontmatter["title"]
        match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return Path(page.route).stem


def _placeholder_guide_page(page: GuidePageSpec, manifest: GuideManifest) -> RenderedGuidePage:
    title = _spec_title(page)
    return RenderedGuidePage(
        source=page.source,
        source_label=page.source_label,
        route=page.route,
        section_id=page.section_id,
        title=title,
        summary=page.summary_override or "",
        html=None,
        has_mermaid=False,
        headings=(),
        assets=(),
        tag=page.tag,
        source_relative=_source_relative(page, manifest),
    )


def render_guide_manifest(manifest: GuideManifest) -> RenderedGuideSite:
    """Render markdown pages, register provider pages, and link prev/next per section."""
    source_routes = {
        page.source: page.route
        for section in manifest.sections
        for page in section.pages
        if page.source is not None
    }
    source_index_routes = {
        source: section.index_route
        for section in manifest.sections
        for source in section.source_indexes
    }
    warnings: list[str] = []
    rendered_sections = []
    for section in manifest.sections:
        ordered = sorted(section.pages, key=lambda page: page.nav_weight)
        rendered_pages: list[RenderedGuidePage] = []
        for index, page in enumerate(ordered):
            if page.tag == "markdown":
                rendered = _GuideRenderer(
                    page=page,
                    manifest=manifest,
                    source_routes=source_routes,
                    source_index_routes=source_index_routes,
                    warnings=warnings,
                ).render()
            else:
                rendered = _placeholder_guide_page(page, manifest)
            prev_page = ordered[index - 1] if index > 0 else None
            next_page = ordered[index + 1] if index + 1 < len(ordered) else None
            rendered_pages.append(
                replace(
                    rendered,
                    prev_route=prev_page.route if prev_page else None,
                    prev_title=_spec_title(prev_page) if prev_page else None,
                    next_route=next_page.route if next_page else None,
                    next_title=_spec_title(next_page) if next_page else None,
                )
            )
        rendered_sections.append(
            RenderedGuideSection(
                section_id=section.section_id,
                title=section.title,
                index_route=section.index_route,
                pages=tuple(rendered_pages),
            )
        )
    return RenderedGuideSite(
        sections=tuple(rendered_sections),
        warnings=tuple(warnings),
        provider_pages=manifest.provider_pages,
    )
