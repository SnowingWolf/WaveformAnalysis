"""Offline Markdown link and fragment validation.

The documentation build intentionally keeps Markdown as the source of truth.
This module validates that source without requiring a browser or a network
connection.  It understands ordinary Markdown links, reference links and
HTML ``href``/``src`` attributes embedded in Markdown files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlparse

_INLINE_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(\s*(?:<(?P<bracket>[^>]+)>|(?P<plain>[^\s)]+))")
_IMAGE_LINK_RE = re.compile(r"!\[[^\]\n]*\]\(\s*(?:<(?P<bracket>[^>]+)>|(?P<plain>[^\s)]+))")
_IMAGE_REFERENCE_LINK_RE = re.compile(r"!\[[^\]\n]*\]\[(?P<label>[^\]\n]*)\]")
_REFERENCE_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\[(?P<label>[^\]\n]*)\]")
_REFERENCE_DEF_RE = re.compile(
    r"^\s*\[(?P<label>[^\]]+)\]:\s*(?:<(?P<bracket>[^>]+)>|(?P<plain>\S+))",
    re.MULTILINE,
)
_ATX_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


@dataclass(frozen=True)
class LinkIssue:
    """One broken local link or fragment."""

    source: Path
    target: str
    message: str
    line: int | None = None
    kind: str = "link"

    def format(self, root: Path) -> str:
        try:
            source = self.source.relative_to(root).as_posix()
        except ValueError:
            source = self.source.as_posix()
        location = f"{source}:{self.line}" if self.line else source
        return f"{location} -> {self.target}: {self.message}"


@dataclass
class LinkReport:
    """Result returned by :class:`MarkdownLinkChecker`."""

    docs_dir: Path
    files_checked: int
    links_checked: int
    issues: list[LinkIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.issues

    @property
    def error_count(self) -> int:
        return len(self.issues)


class _MarkdownHtmlReferenceParser(HTMLParser):
    """Collect links and explicit anchors from HTML embedded in Markdown."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[tuple[str, str]] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001 - stdlib API
        values = {name.lower(): value for name, value in attrs if value is not None}
        for name in ("href", "src"):
            if values.get(name):
                self.references.append((name, values[name]))
        for name in ("id", "name"):
            if values.get(name):
                self.anchors.add(values[name])


def _without_fenced_code(text: str) -> str:
    """Remove fenced code blocks while retaining line numbers."""

    lines = text.splitlines(keepends=True)
    in_fence = False
    marker = ""
    output: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if not in_fence:
            fence = re.match(r"(`{3,}|~{3,})", stripped)
            if fence:
                in_fence = True
                marker = fence.group(1)[0]
                output.append("\n" if line.endswith("\n") else "")
            else:
                output.append(line)
            continue
        if re.match(rf"\s*{re.escape(marker)}{{3,}}\s*$", line):
            in_fence = False
        output.append("\n" if line.endswith("\n") else "")
    return "".join(output)


def _strip_inline_markup(value: str) -> str:
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"!?(?:\[([^\]]+)\])(?:\([^)]*\)|\[[^]]*\])", r"\1", value)
    value = re.sub(r"<[^>]+>", "", value)
    return value.strip().rstrip("#").strip()


def _heading_slug(value: str) -> str:
    """Generate the conservative GitHub/Mistune-style heading slug."""

    value = _strip_inline_markup(value).casefold()
    value = re.sub(r"[^\w\s\-\u0080-\uffff]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s\-]+", "-", value).strip("-")
    return value


def _anchors_for_file(path: Path) -> set[str]:
    """Return generated and explicit anchors for Markdown or HTML."""

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return set()

    anchors: set[str] = set()
    if path.suffix.lower() in {".md", ".markdown", ".mdown"}:
        body = _without_fenced_code(text)
        lines = body.splitlines()
        heading_counts: dict[str, int] = {}

        def add_heading(value: str) -> None:
            title = _strip_inline_markup(value)
            slug = _heading_slug(title)
            if not slug:
                return
            count = heading_counts.get(slug, 0)
            heading_counts[slug] = count + 1
            anchors.add(slug if count == 0 else f"{slug}-{count + 1}")
            # Accept the spelling emitted by simple Markdown renderers too.
            if title:
                anchors.add(title.replace(" ", "-"))

        for index, line in enumerate(lines):
            match = _ATX_HEADING_RE.match(line)
            if match:
                add_heading(match.group(1))
                continue
            if (
                line.strip()
                and index + 1 < len(lines)
                and re.fullmatch(r"\s*(?:=+|-+)\s*", lines[index + 1])
            ):
                add_heading(line)
    parser = _MarkdownHtmlReferenceParser()
    try:
        parser.feed(text)
    except Exception:  # pragma: no cover - HTMLParser is intentionally forgiving
        pass
    anchors.update(parser.anchors)
    return anchors


def _is_external(target: str) -> bool:
    parsed = urlparse(target)
    return bool(parsed.scheme or parsed.netloc)


def _line_for_target(text: str, target: str) -> int | None:
    for number, line in enumerate(text.splitlines(), 1):
        if target in line:
            return number
    return None


class MarkdownLinkChecker:
    """Check local Markdown links below a documentation root."""

    def __init__(self, docs_dir: Path | str = "docs") -> None:
        self.docs_dir = Path(docs_dir).resolve()
        if not self.docs_dir.is_dir():
            raise ValueError(f"文档目录不存在: {self.docs_dir}")
        # Links such as ``../README.md`` intentionally resolve against the
        # repository root rather than being rejected merely for leaving docs/.
        self.project_root = self.docs_dir.parent

    def _iter_markdown(self) -> list[Path]:
        return sorted(
            path
            for path in self.docs_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".md", ".markdown", ".mdown"}
            and not any(part in {"node_modules", ".git", "_site", "build"} for part in path.parts)
        )

    @staticmethod
    def _references(text: str) -> list[tuple[str, str, int | None]]:
        body = _without_fenced_code(text)
        references: list[tuple[str, str, int | None]] = []
        definitions: dict[str, str] = {}
        for match in _REFERENCE_DEF_RE.finditer(body):
            target = match.group("bracket") or match.group("plain")
            definitions[match.group("label").strip().casefold()] = target

        for match in _INLINE_LINK_RE.finditer(body):
            target = match.group("bracket") or match.group("plain")
            references.append((target, "link", _line_for_target(body, target)))
        for match in _IMAGE_LINK_RE.finditer(body):
            target = match.group("bracket") or match.group("plain")
            references.append((target, "resource", _line_for_target(body, target)))
        for match in _IMAGE_REFERENCE_LINK_RE.finditer(body):
            label = match.group("label").strip()
            if not label:
                label = re.match(r"!\[([^\]]*)\]", match.group(0)).group(1).strip()
            target = definitions.get(label.casefold())
            if target:
                references.append((target, "resource", _line_for_target(body, match.group(0))))
        for match in _REFERENCE_LINK_RE.finditer(body):
            label = match.group("label").strip() or match.group(0).split("]", 1)[0][1:]
            target = definitions.get(label.casefold())
            if target:
                references.append((target, "link", _line_for_target(body, match.group(0))))

        parser = _MarkdownHtmlReferenceParser()
        try:
            parser.feed(body)
        except Exception:  # pragma: no cover - HTMLParser is forgiving
            pass
        references.extend(
            (target, kind, _line_for_target(body, target)) for kind, target in parser.references
        )
        return references

    def _check_reference(
        self,
        source: Path,
        target: str,
        kind: str,
        line: int | None,
    ) -> LinkIssue | None:
        target = target.strip()
        if not target or _is_external(target):
            return None if target else LinkIssue(source, target, "链接目标为空", line, kind)
        parsed = urlparse(target)
        path_text = unquote(parsed.path)
        fragment = unquote(parsed.fragment)
        if path_text:
            resolved = (source.parent / path_text).resolve()
            if not resolved.is_relative_to(self.project_root):
                return LinkIssue(
                    source,
                    target,
                    f"链接越过项目根目录: {resolved}",
                    line,
                    kind,
                )
            if not resolved.exists():
                return LinkIssue(source, target, f"本地资源不存在: {resolved}", line, kind)
        else:
            resolved = source
        if fragment:
            if resolved.suffix.lower() in {".md", ".markdown", ".mdown", ".html", ".htm"}:
                anchors = _anchors_for_file(resolved)
                if not any(anchor.casefold() == fragment.casefold() for anchor in anchors):
                    return LinkIssue(
                        source,
                        target,
                        f"fragment 不存在: #{fragment}",
                        line,
                        "fragment",
                    )
        return None

    def check(self) -> LinkReport:
        files = self._iter_markdown()
        issues: list[LinkIssue] = []
        links_checked = 0
        for source in files:
            try:
                text = source.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                issues.append(LinkIssue(source, "", f"无法读取 Markdown: {exc}", kind="file"))
                continue
            for target, kind, line in self._references(text):
                links_checked += 1
                issue = self._check_reference(source, target, kind, line)
                if issue:
                    issues.append(issue)
        return LinkReport(
            docs_dir=self.docs_dir,
            files_checked=len(files),
            links_checked=links_checked,
            issues=issues,
        )


def check_markdown_links(docs_dir: Path | str = "docs") -> LinkReport:
    """Convenience wrapper for the CLI and callers that need a report."""

    return MarkdownLinkChecker(docs_dir).check()


__all__ = ["LinkIssue", "LinkReport", "MarkdownLinkChecker", "check_markdown_links"]
