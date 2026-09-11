"""Load source-reviewed dtype field narratives for generated plugin references."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files

import yaml

_METADATA_KEYS = {"schema_version", "notes"}


@lru_cache(maxsize=1)
def load_dtype_field_notes() -> dict[str, dict[str, dict[str, str]]]:
    """Return bundled per-plugin output field narratives with units.

    Each field value may be either a plain string (treated as the description,
    with units defaulting to "None") or a dict with ``doc`` and ``units`` keys.
    """
    resource = files("waveform_analysis.documentation").joinpath("dtype_field_notes.yaml")
    raw = yaml.safe_load(resource.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("dtype_field_notes.yaml must declare schema_version: 1")

    notes: dict[str, dict[str, dict[str, str]]] = {}
    for provides, fields in raw.items():
        if provides in _METADATA_KEYS:
            continue
        if not isinstance(provides, str) or not isinstance(fields, dict):
            raise ValueError("dtype_field_notes.yaml entries must map provides to field notes")
        plugin_notes: dict[str, dict[str, str]] = {}
        for name, value in fields.items():
            if not isinstance(name, str):
                continue
            if isinstance(value, str):
                if value.strip():
                    plugin_notes[name] = {"doc": value, "units": "None"}
            elif isinstance(value, dict):
                doc = str(value.get("doc", ""))
                units = str(value.get("units", "None"))
                if doc.strip():
                    plugin_notes[name] = {"doc": doc, "units": units}
        notes[provides] = plugin_notes
    return notes


def dtype_field_notes_for(provides: str) -> dict[str, dict[str, str]]:
    """Return a copy of the field narratives (with doc and units) for one plugin."""
    return dict(load_dtype_field_notes().get(provides, {}))
