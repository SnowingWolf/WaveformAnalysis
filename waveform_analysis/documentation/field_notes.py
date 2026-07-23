"""Load source-reviewed dtype field narratives for generated plugin references."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files

import yaml

_METADATA_KEYS = {"schema_version", "notes"}


@lru_cache(maxsize=1)
def load_dtype_field_notes() -> dict[str, dict[str, str]]:
    """Return bundled per-plugin output field narratives."""
    resource = files("waveform_analysis.documentation").joinpath("dtype_field_notes.yaml")
    raw = yaml.safe_load(resource.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("dtype_field_notes.yaml must declare schema_version: 1")

    notes: dict[str, dict[str, str]] = {}
    for provides, fields in raw.items():
        if provides in _METADATA_KEYS:
            continue
        if not isinstance(provides, str) or not isinstance(fields, dict):
            raise ValueError("dtype_field_notes.yaml entries must map provides to field notes")
        notes[provides] = {
            str(name): str(description)
            for name, description in fields.items()
            if isinstance(name, str) and isinstance(description, str) and description.strip()
        }
    return notes


def dtype_field_notes_for(provides: str) -> dict[str, str]:
    """Return a copy of the field narratives declared for one plugin output."""
    return dict(load_dtype_field_notes().get(provides, {}))
