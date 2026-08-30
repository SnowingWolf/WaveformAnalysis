"""Safe rendering helpers for curated offline documentation."""

import re
from xml.etree import ElementTree

from markupsafe import Markup, escape

_CONTENT_BLOCK_KINDS = frozenset(
    {"heading", "paragraph", "list", "note", "code", "image", "mathml", "table", "mermaid"}
)
_MATHML_TAGS = frozenset(
    {
        "math",
        "mrow",
        "mi",
        "mn",
        "mo",
        "mtext",
        "ms",
        "mspace",
        "mstyle",
        "merror",
        "mpadded",
        "mphantom",
        "mfenced",
        "menclose",
        "msub",
        "msup",
        "msubsup",
        "munder",
        "mover",
        "munderover",
        "mmultiscripts",
        "mtable",
        "mtr",
        "mtd",
        "maligngroup",
        "malignmark",
        "mlabeledtr",
        "mfrac",
        "msqrt",
        "mroot",
        "mstack",
        "mlongdiv",
        "mscarries",
        "mscarry",
        "msline",
        "maction",
        "semantics",
        "annotation",
        "annotation-xml",
    }
)
_MATHML_ATTRIBUTES = frozenset(
    {
        "xmlns",
        "display",
        "mathvariant",
        "mathsize",
        "mathcolor",
        "mathbackground",
        "scriptlevel",
        "displaystyle",
        "accent",
        "accentunder",
        "stretchy",
        "symmetric",
        "form",
        "fence",
        "separator",
        "lspace",
        "rspace",
        "minsize",
        "maxsize",
        "movablelimits",
        "largeop",
        "linebreak",
        "depth",
        "height",
        "width",
        "voffset",
        "linethickness",
        "numalign",
        "denomalign",
        "bevelled",
        "open",
        "close",
        "separators",
        "notation",
        "columnalign",
        "rowalign",
        "columnspacing",
        "rowspacing",
        "columnlines",
        "rowlines",
        "frame",
        "framespacing",
        "equalcolumns",
        "equalrows",
        "columnspan",
        "rowspan",
        "groupalign",
        "align",
        "charalign",
        "charspacing",
        "side",
        "minlabelspacing",
        "selection",
        "actiontype",
        "encoding",
    }
)


def _safe_mathml(value: str) -> Markup:
    """Validate a small, presentation-only MathML subset before marking it safe."""
    if "<!" in value or "<?" in value:
        raise ValueError("MathML must not contain declarations or processing instructions")
    try:
        root = ElementTree.fromstring(value)
    except ElementTree.ParseError as exc:
        raise ValueError("Invalid MathML content block") from exc

    if root.tag.rsplit("}", maxsplit=1)[-1] != "math":
        raise ValueError("A MathML content block must have a <math> root element")
    for element in root.iter():
        tag = element.tag.rsplit("}", maxsplit=1)[-1]
        if tag not in _MATHML_TAGS:
            raise ValueError(f"Unsupported MathML element: {tag}")
        for attribute in element.attrib:
            attribute_name = attribute.rsplit("}", maxsplit=1)[-1]
            if attribute_name not in _MATHML_ATTRIBUTES:
                raise ValueError(f"Unsupported MathML attribute: {attribute_name}")
    return Markup(ElementTree.tostring(root, encoding="unicode", method="xml"))


def _highlight_python(source: str) -> Markup:
    """Return trusted offline Pygments markup for registry-controlled Python examples."""
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import PythonLexer
    except ImportError as exc:
        raise RuntimeError(
            "site-web Accessor examples require Pygments. Install the documentation extra: "
            'pip install -e ".[docgen]"'
        ) from exc
    return Markup(highlight(source, PythonLexer(), HtmlFormatter(nowrap=True)))


def _inline_code(value: str) -> Markup:
    """Escape prose first, then render restricted emphasis and code notation."""
    escaped = str(escape(value))
    emphasized = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return Markup(re.sub(r"`([^`]+)`", r"<code>\1</code>", emphasized))
