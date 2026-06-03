"""Helpers for run-level metadata stored in ``run_config.json``."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import re
from typing import Any

RUN_NUMBER_PATTERN = re.compile(r"^\d{6}$")
CHANNEL_KEY_PATTERN = re.compile(r"^\d+:\d+$")
VALID_DAQ_STATUSES = frozenset({"planned", "acquiring", "acquired", "failed"})
VALID_POLARITIES = frozenset({"positive", "negative"})


class RunConfigValidationError(ValueError):
    """Raised when a run_config.json payload does not match the expected metadata schema."""


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RunConfigValidationError(f"{path} must be an object")
    return value


def _validate_channel_key(key: Any, path: str) -> str:
    if not isinstance(key, str) or not CHANNEL_KEY_PATTERN.fullmatch(key):
        raise RunConfigValidationError(f"{path} must use 'board:channel' string keys")
    return key


def _validate_bool(value: Any, path: str) -> None:
    if not isinstance(value, bool):
        raise RunConfigValidationError(f"{path} must be a boolean")


def _validate_number_or_null(value: Any, path: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RunConfigValidationError(f"{path} must be a number or null")


def _validate_iso_utc(value: Any, path: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise RunConfigValidationError(f"{path} must be an ISO-8601 UTC string or null")
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RunConfigValidationError(f"{path} must be an ISO-8601 UTC string") from exc
    if parsed.tzinfo is None:
        raise RunConfigValidationError(f"{path} must include timezone information")
    if parsed.utcoffset() != timedelta(0):
        raise RunConfigValidationError(f"{path} must use UTC timezone")


def _validate_channel_config(config: dict[str, Any], path: str) -> None:
    if "enabled" in config:
        _validate_bool(config["enabled"], f"{path}.enabled")
    if "polarity" in config and config["polarity"] not in VALID_POLARITIES:
        raise RunConfigValidationError(f"{path}.polarity must be one of {sorted(VALID_POLARITIES)}")
    if "bias_voltage_v" in config:
        _validate_number_or_null(config["bias_voltage_v"], f"{path}.bias_voltage_v")


def _validate_electrodes(hardware: dict[str, Any]) -> None:
    electrodes = hardware.get("electrodes")
    if electrodes is None:
        return
    electrodes = _require_mapping(electrodes, "hardware.electrodes")
    for name, spec in electrodes.items():
        if not isinstance(name, str) or not name:
            raise RunConfigValidationError("hardware.electrodes keys must be non-empty strings")
        spec = _require_mapping(spec, f"hardware.electrodes.{name}")
        if "enabled" in spec:
            _validate_bool(spec["enabled"], f"hardware.electrodes.{name}.enabled")
        if "voltage_v" in spec:
            _validate_number_or_null(spec["voltage_v"], f"hardware.electrodes.{name}.voltage_v")


def validate_run_config(run_config: dict[str, Any], *, require_identity: bool = False) -> None:
    """Validate run identity, DAQ metadata, and hardware metadata when present.

    Existing legacy run configs that only contain ``calibration`` or ``plugins`` remain valid unless
    ``require_identity`` is set. This keeps the helper opt-in and avoids changing the behavior of
    :meth:`Context.get_run_config`.
    """

    _require_mapping(run_config, "run_config")

    run_number = run_config.get("run_number")
    if run_number is None:
        if require_identity:
            raise RunConfigValidationError("run_number is required")
    elif not isinstance(run_number, str) or not RUN_NUMBER_PATTERN.fullmatch(run_number):
        raise RunConfigValidationError("run_number must be a 6-digit string")

    for key in ("run_id", "run_name"):
        value = run_config.get(key)
        if value is None:
            if require_identity and key == "run_id":
                raise RunConfigValidationError("run_id is required")
            continue
        if not isinstance(value, str) or not value.strip():
            raise RunConfigValidationError(f"{key} must be a non-empty string")

    daq = run_config.get("daq")
    if daq is None:
        if require_identity:
            raise RunConfigValidationError("daq is required")
    else:
        daq = _require_mapping(daq, "daq")
        status = daq.get("status")
        if status is not None and status not in VALID_DAQ_STATUSES:
            raise RunConfigValidationError(
                f"daq.status must be one of {sorted(VALID_DAQ_STATUSES)}"
            )
        if "start_time" in daq:
            _validate_iso_utc(daq["start_time"], "daq.start_time")
        elif require_identity:
            raise RunConfigValidationError("daq.start_time is required")
        if "end_time" in daq:
            _validate_iso_utc(daq["end_time"], "daq.end_time")
        for key in ("threshold_lsb", "sampling_rate_hz"):
            if key in daq:
                _validate_number_or_null(daq[key], f"daq.{key}")

    hardware = run_config.get("hardware")
    if hardware is not None:
        resolve_run_hardware_channels(run_config, validate=True)


def resolve_run_hardware_channels(
    run_config: dict[str, Any], *, validate: bool = True
) -> dict[str, dict[str, Any]]:
    """Return merged per-channel hardware metadata from a run config.

    Merge order is ``hardware.channel_groups`` in list order, then ``hardware.channels`` as the
    per-channel override layer. Channel keys must use the existing ``"board:channel"`` convention.
    """

    _require_mapping(run_config, "run_config")
    hardware = run_config.get("hardware", {})
    if hardware is None:
        return {}
    hardware = _require_mapping(hardware, "hardware")

    if validate:
        _validate_electrodes(hardware)

    merged: dict[str, dict[str, Any]] = {}
    groups = hardware.get("channel_groups", [])
    if groups is None:
        groups = []
    if not isinstance(groups, list):
        raise RunConfigValidationError("hardware.channel_groups must be a list")

    for idx, group in enumerate(groups):
        group_path = f"hardware.channel_groups[{idx}]"
        group = _require_mapping(group, group_path)
        channels = group.get("channels", [])
        if not isinstance(channels, list):
            raise RunConfigValidationError(f"{group_path}.channels must be a list")
        config = _require_mapping(group.get("config", {}), f"{group_path}.config")
        if validate:
            _validate_channel_config(config, f"{group_path}.config")
        for channel_key in channels:
            key = _validate_channel_key(channel_key, f"{group_path}.channels[]")
            merged.setdefault(key, {}).update(deepcopy(config))

    channels_block = hardware.get("channels", {})
    if channels_block is None:
        channels_block = {}
    channels_block = _require_mapping(channels_block, "hardware.channels")
    for raw_key, override in channels_block.items():
        key = _validate_channel_key(raw_key, "hardware.channels")
        override = _require_mapping(override, f"hardware.channels.{key}")
        if validate:
            _validate_channel_config(override, f"hardware.channels.{key}")
        merged.setdefault(key, {}).update(deepcopy(override))

    return merged
