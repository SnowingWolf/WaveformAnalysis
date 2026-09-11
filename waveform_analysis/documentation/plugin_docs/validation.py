"""Structural validation for generated plugin reference pages."""

from pathlib import Path
import re
from typing import Any

EXPECTED_SECTIONS = {
    "auto": ["Overview", "Configuration", "Output", "Usage"],
    "agent": [
        "Overview",
        "Configuration",
        "Output",
        "Usage",
        "Operational Notes",
        "Maintenance",
    ],
}

FRONTMATTER_FIELDS = (
    "schema_version",
    "document_type",
    "profile",
    "provides",
    "plugin_class",
    "module",
    "version",
    "summary",
    "depends_on",
    "declared_depends_on",
    "resolved_depends_on",
    "dependency_profile",
    "dependency_profile_values",
    "dependency_config_keys",
    "output_kind",
    "execution_kind",
    "narrative_source",
    "narrative_source_reason",
    "source_fingerprint",
    "generated",
)


def _escape_markdown_cell(value: Any) -> str:
    return str(value).replace("|", r"\|").replace("\n", "<br>")


def check_plugin_document_structure(content: str, profile: str) -> list[str]:
    """Validate generated plugin Markdown section and Overview table structure."""
    errors: list[str] = []
    expected = EXPECTED_SECTIONS.get(profile)
    if expected is None:
        return [f"Unknown profile: {profile}"]
    if not content.startswith("---\n") or "\n---\n" not in content[4:]:
        errors.append("Missing YAML frontmatter")
    else:
        frontmatter = content.split("\n---\n", 1)[0][4:]
        keys = [line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line]
        missing = [field for field in FRONTMATTER_FIELDS if field not in keys]
        extra = [key for key in keys if key not in FRONTMATTER_FIELDS]
        if missing:
            errors.append(f"Missing frontmatter fields: {missing!r}")
        if extra:
            errors.append(f"Unexpected frontmatter fields: {extra!r}")
        if not re.search(r"^schema_version:\s*2\s*$", frontmatter, flags=re.MULTILINE):
            errors.append("Unsupported plugin reference schema_version; expected 2")
        if f'profile: "{profile}"' not in frontmatter:
            errors.append(f"Frontmatter profile does not match {profile!r}")
    sections = re.findall(r"^## ([^#].*)$", content, flags=re.MULTILINE)
    if sections != expected:
        errors.append(f"Expected H2 sections {expected!r}, got {sections!r}")
    overview_start = content.find("## Overview")
    config_start = content.find("## Configuration")
    if overview_start < 0 or config_start < 0:
        return errors
    overview = content[overview_start:config_start]
    contract = overview.find("| Item | Value |")
    dependencies = overview.find(
        "| Dependency | Version Constraint | Resolution | Required Fields | Description |"
    )
    if contract < 0:
        errors.append("Overview is missing the Contract table")
    if dependencies < 0:
        errors.append("Overview is missing the Dependencies table")
    if contract >= 0 and dependencies >= 0 and contract > dependencies:
        errors.append("Contract table must precede Dependencies table")
    summary = overview[len("## Overview") : contract if contract >= 0 else len(overview)].strip()
    if not summary:
        errors.append("Overview summary must precede the Contract table")
    if "| Name | Type | Default | Unit | Tracked | Deprecated | Description |" not in content:
        errors.append("Configuration table header is missing")
    if "| Field | DType | Unit | Meaning |" not in content:
        errors.append("Output table header is missing")
    return errors


def check_plugin_document(path: Path, profile: str) -> list[str]:
    """Validate a generated page; INDEX.md intentionally follows separate rules."""
    path = Path(path)
    if path.name == "INDEX.md":
        return []
    return check_plugin_document_structure(path.read_text(encoding="utf-8"), profile)
