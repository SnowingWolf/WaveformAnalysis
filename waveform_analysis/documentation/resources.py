"""Packaged resource locations shared by documentation generators."""

from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent


def template_directory() -> Path:
    """Return the installed documentation template directory."""
    return _PACKAGE_ROOT / "templates"
