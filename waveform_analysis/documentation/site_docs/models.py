"""Data models for curated offline documentation pages."""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from markupsafe import Markup

from .rendering import _CONTENT_BLOCK_KINDS, _safe_mathml


@dataclass(frozen=True)
class DocumentationContentBlock:
    """A controlled, offline-safe documentation element rendered by a web template."""

    kind: str
    text: str = ""
    items: tuple[str, ...] = ()
    ordered: bool = False
    heading_level: int = 3
    title: str = ""
    tone: str = "note"
    code: str = ""
    language: str = "text"
    image_src: str = ""
    image_alt: str = ""
    image_caption: str = ""
    mathml: str = ""
    mermaid: str = ""
    table_headers: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in _CONTENT_BLOCK_KINDS:
            raise ValueError(f"Unsupported documentation content block: {self.kind}")
        if self.kind == "heading":
            if not self.text:
                raise ValueError("A heading content block requires text")
            if self.heading_level not in {3, 4}:
                raise ValueError("A heading content block must use level 3 or 4")
        if self.kind == "paragraph" and not self.text:
            raise ValueError("A paragraph content block requires text")
        if self.kind == "list" and not self.items:
            raise ValueError("A list content block requires items")
        if self.kind == "note":
            if not self.text:
                raise ValueError("A note content block requires text")
            if self.tone not in {"note", "important", "warning"}:
                raise ValueError(f"Unsupported note tone: {self.tone}")
        if self.kind == "code" and not self.code:
            raise ValueError("A code content block requires source code")
        if self.kind == "image":
            if not self.image_src or not self.image_alt:
                raise ValueError("An image content block requires image_src and image_alt")
            path = PurePosixPath(self.image_src)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("image_src must be a relative path inside content-assets")
        if self.kind == "mathml":
            if not self.mathml:
                raise ValueError("A MathML content block requires mathml")
            _safe_mathml(self.mathml)
        if self.kind == "mermaid" and not self.mermaid:
            raise ValueError("A mermaid content block requires mermaid source")
        if self.kind == "table":
            if not self.table_headers:
                raise ValueError("A table content block requires table_headers")
            if any(len(row) != len(self.table_headers) for row in self.table_rows):
                raise ValueError("Every table content block row must match its header width")


@dataclass(frozen=True)
class AccessorMemberSpec:
    name: str
    description: str
    kind: str = "method"
    parameters: tuple["AccessorParameterSpec", ...] = ()
    returns: str = ""
    notes: tuple[str, ...] = ()
    example: str = ""


@dataclass(frozen=True)
class AccessorParameterSpec:
    name: str
    description: str


@dataclass(frozen=True)
class AccessorNarrativeSection:
    """One curated explanatory section rendered before an Accessor API list."""

    anchor: str
    title: str
    blocks: tuple[DocumentationContentBlock, ...]


@dataclass(frozen=True)
class AccessorDocumentationSpec:
    accessor_class: type
    slug: str
    summary: str
    introduction: str
    purpose: str
    example: str
    constructor_parameters: tuple[AccessorParameterSpec, ...]
    members: tuple[AccessorMemberSpec, ...]
    narrative_sections: tuple[AccessorNarrativeSection, ...] = ()
    overview_title: str = "整体介绍"
    overview_blocks: tuple[DocumentationContentBlock, ...] = ()


@dataclass(frozen=True)
class AccessorMemberView:
    name: str
    kind: str
    signature: str
    signature_html: Markup
    description: str
    parameters: tuple[AccessorParameterSpec, ...]
    returns: str
    notes: tuple[str, ...]
    example_html: Markup


@dataclass(frozen=True)
class AccessorDocumentationView:
    name: str
    slug: str
    module_path: str
    summary: str
    introduction: str
    purpose: str
    example_html: Markup
    constructor_signature: str
    constructor_parameters: tuple[AccessorParameterSpec, ...]
    members: tuple[AccessorMemberView, ...]
    narrative_sections: tuple[AccessorNarrativeSection, ...] = ()
    overview_title: str = "整体介绍"
    overview_blocks: tuple[DocumentationContentBlock, ...] = ()


@dataclass(frozen=True)
class ContentDocumentationSection:
    """One curated section in a static conceptual reference page."""

    anchor: str
    title: str
    blocks: tuple[DocumentationContentBlock, ...]


@dataclass(frozen=True)
class CallableDocumentationSpec:
    name: str
    callable: Any
    description: str
    parameters: tuple[AccessorParameterSpec, ...] = ()
    returns: str = ""
    notes: tuple[str, ...] = ()
    example: str = ""
    kind: str = "function"


@dataclass(frozen=True)
class CallableDocumentationGroup:
    anchor: str
    title: str
    description: str
    members: tuple[CallableDocumentationSpec, ...]


@dataclass(frozen=True)
class CallableDocumentationPageSpec:
    slug: str
    title: str
    eyebrow: str
    summary: str
    introduction: str
    groups: tuple[CallableDocumentationGroup, ...]
    narrative_sections: tuple[ContentDocumentationSection, ...] = ()


@dataclass(frozen=True)
class CallableDocumentationView:
    name: str
    signature_html: Markup
    description: str
    parameters: tuple[AccessorParameterSpec, ...]
    returns: str
    notes: tuple[str, ...]
    example_html: Markup
    kind: str


@dataclass(frozen=True)
class CallableDocumentationPageView:
    slug: str
    title: str
    eyebrow: str
    summary: str
    introduction: str
    groups: tuple[tuple[CallableDocumentationGroup, tuple[CallableDocumentationView, ...]], ...]
    narrative_sections: tuple[ContentDocumentationSection, ...] = ()
    href: str = ""
    has_mermaid: bool = False
    related_guide_href: str = ""
    related_guide_label: str = ""


@dataclass(frozen=True)
class AccessorSelectionGuideItem:
    name: str
    slug: str
    entry: str
    question: str
    scenario: str
    route: str = ""
