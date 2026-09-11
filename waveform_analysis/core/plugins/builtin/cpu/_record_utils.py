"""Backward-compatible shim. Implementation moved to builtin.shared.record_utils."""

from waveform_analysis.core.plugins.builtin.shared.record_utils import (
    RecordLookup,
    build_record_lookup_legacy,
    field_or_default,
    get_field_safe,
    resolve_record_indices,
)

__all__ = [
    "RecordLookup",
    "build_record_lookup_legacy",
    "get_field_safe",
    "field_or_default",
    "resolve_record_indices",
]
