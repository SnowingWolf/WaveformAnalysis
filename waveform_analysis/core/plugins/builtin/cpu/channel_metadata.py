"""Helpers to normalize and validate per-channel metadata from config."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any
import warnings

VALID_POLARITIES = {"positive", "negative"}


def _default_channel_meta() -> dict[str, Any]:
    return {
        "polarity": "unknown",
        "geometry": "unknown",
        "adc_bits": None,
    }


def _normalize_adc_bits(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            try:
                return int(text)
            except ValueError:
                return None
    return None


def _is_channel_key(key: Any) -> bool:
    if isinstance(key, int):
        return key >= 0
    if isinstance(key, str):
        return key.isdigit()
    return False


def resolve_channel_metadata(
    channel_metadata: Any,
    run_id: str,
    channels: Iterable[int],
    plugin_name: str,
) -> dict[int, dict[str, Any]]:
    """
    Resolve channel metadata for a run and return normalized defaults.

    Missing or invalid fields are replaced with:
    - polarity: "unknown"
    - geometry: "unknown"
    - adc_bits: None
    """
    run_meta: dict[str, Any] = {}
    if channel_metadata is not None and not isinstance(channel_metadata, dict):
        warnings.warn(
            f"Plugin '{plugin_name}' run '{run_id}': channel_metadata must be dict, "
            "falling back to unknown defaults.",
            UserWarning,
            stacklevel=3,
        )
    elif isinstance(channel_metadata, dict):
        run_block = channel_metadata.get(run_id)
        if isinstance(run_block, dict):
            run_meta = run_block
        elif all(_is_channel_key(key) for key in channel_metadata.keys()):
            run_meta = channel_metadata
        else:
            run_meta = {}

    normalized: dict[int, dict[str, Any]] = {}
    issues: dict[int, list[str]] = defaultdict(list)

    for ch in sorted({int(x) for x in channels}):
        meta = _default_channel_meta()
        ch_raw = run_meta.get(str(ch), run_meta.get(ch, None))
        if isinstance(ch_raw, dict):
            polarity = ch_raw.get("polarity")
            if isinstance(polarity, str) and polarity in VALID_POLARITIES:
                meta["polarity"] = polarity
            else:
                issues[ch].append("polarity")

            geometry = ch_raw.get("geometry")
            if isinstance(geometry, str) and geometry.strip():
                meta["geometry"] = geometry
            else:
                issues[ch].append("geometry")

            raw_adc_bits = ch_raw.get("adc_bits")
            adc_bits = _normalize_adc_bits(raw_adc_bits)
            meta["adc_bits"] = adc_bits
            if raw_adc_bits is not None and adc_bits is None:
                issues[ch].append("adc_bits")
        else:
            issues[ch].extend(["polarity", "geometry", "adc_bits"])
        normalized[ch] = meta

    if issues:
        parts = []
        for ch in sorted(issues):
            fields = ",".join(sorted(set(issues[ch])))
            parts.append(f"ch{ch}[{fields}]")
        warnings.warn(
            f"Plugin '{plugin_name}' run '{run_id}': missing/invalid channel_metadata -> "
            + "; ".join(parts),
            UserWarning,
            stacklevel=3,
        )

    return normalized
