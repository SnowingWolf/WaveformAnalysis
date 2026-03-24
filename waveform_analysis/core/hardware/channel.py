"""Hardware-channel identity, config lookup, and grouping helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
import warnings

import numpy as np

VALID_POLARITIES = {"positive", "negative"}


@dataclass(frozen=True, order=True, slots=True)
class HardwareChannel:
    """Unique hardware channel identity."""

    board: int
    channel: int


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """Normalized per-hardware-channel config entry."""

    polarity: str = "unknown"
    geometry: str = "unknown"
    adc_bits: int | None = None
    fixed_baseline: float | None = None
    gain_adc_per_pe: float | None = None


@dataclass(frozen=True, slots=True)
class ChannelMetadata:
    """Normalized per-hardware-channel metadata truth entry."""

    polarity: str = "unknown"
    geometry: str = "unknown"
    adc_bits: int | None = None


@dataclass(frozen=True, slots=True)
class PluginChannelRule:
    """Resolved plugin config for a single hardware channel."""

    channel: HardwareChannel
    values: dict[str, Any]

    def get(self, name: str, default: Any = None) -> Any:
        return self.values.get(name, default)


def make_channel(board: Any, channel: Any) -> HardwareChannel:
    return HardwareChannel(board=int(board), channel=int(channel))


def channel_from_fields(board: Any, channel: Any) -> HardwareChannel:
    return make_channel(board, channel)


def channel_from_record(record: np.void | Mapping[str, Any]) -> HardwareChannel:
    if "board" not in record or "channel" not in record:
        raise KeyError("record must contain 'board' and 'channel'")
    return make_channel(record["board"], record["channel"])


def require_board_channel_fields(dtype: np.dtype) -> None:
    names = set(dtype.names or ())
    missing = [name for name in ("board", "channel") if name not in names]
    if missing:
        raise ValueError(f"dtype missing required fields: {', '.join(missing)}")


def extract_board_channel_fields(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    require_board_channel_fields(data.dtype)
    return (
        np.asarray(data["board"], dtype=np.int32),
        np.asarray(data["channel"], dtype=np.int32),
    )


def _channel_key_dtype() -> np.dtype:
    return np.dtype([("board", np.int32), ("channel", np.int32)])


def _channel_keys_from_arrays(boards: np.ndarray, channels: np.ndarray) -> np.ndarray:
    keys = np.empty(len(boards), dtype=_channel_key_dtype())
    keys["board"] = np.asarray(boards, dtype=np.int32)
    keys["channel"] = np.asarray(channels, dtype=np.int32)
    return keys


def unique_hardware_channels(
    boards: Sequence[int] | np.ndarray,
    channels: Sequence[int] | np.ndarray,
) -> list[HardwareChannel]:
    if len(boards) != len(channels):
        raise ValueError("boards and channels must have the same length")
    if len(boards) == 0:
        return []
    keys = _channel_keys_from_arrays(np.asarray(boards), np.asarray(channels))
    unique_keys = np.unique(keys)
    return [HardwareChannel(int(item["board"]), int(item["channel"])) for item in unique_keys]


def group_indices_by_hardware_channel(
    boards: Sequence[int] | np.ndarray,
    channels: Sequence[int] | np.ndarray,
) -> dict[HardwareChannel, np.ndarray]:
    if len(boards) != len(channels):
        raise ValueError("boards and channels must have the same length")
    if len(boards) == 0:
        return {}

    boards_arr = np.asarray(boards, dtype=np.int32)
    channels_arr = np.asarray(channels, dtype=np.int32)
    keys = _channel_keys_from_arrays(boards_arr, channels_arr)
    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    group_starts = np.flatnonzero(np.r_[True, sorted_keys[1:] != sorted_keys[:-1]])
    group_ends = np.r_[group_starts[1:], len(order)]

    groups: dict[HardwareChannel, np.ndarray] = {}
    for start, end in zip(group_starts, group_ends, strict=False):
        key = sorted_keys[start]
        groups[HardwareChannel(int(key["board"]), int(key["channel"]))] = order[start:end]
    return groups


def iter_hardware_channel_indices(data: np.ndarray) -> Iterator[tuple[HardwareChannel, np.ndarray]]:
    boards, channels = extract_board_channel_fields(data)
    yield from group_indices_by_hardware_channel(boards, channels).items()


def iter_hardware_channel_groups(data: np.ndarray) -> Iterator[tuple[HardwareChannel, np.ndarray]]:
    for hw_channel, indices in iter_hardware_channel_indices(data):
        yield hw_channel, data[indices]


def _normalize_adc_bits(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def normalize_channel_config_entry(raw: Any) -> ChannelConfig:
    if not isinstance(raw, Mapping):
        return ChannelConfig()

    polarity = raw.get("polarity", "unknown")
    if not isinstance(polarity, str) or polarity not in VALID_POLARITIES:
        polarity = "unknown"

    geometry = raw.get("geometry", "unknown")
    if not isinstance(geometry, str) or not geometry.strip():
        geometry = "unknown"

    adc_bits = _normalize_adc_bits(raw.get("adc_bits"))

    fixed_baseline = raw.get("fixed_baseline")
    try:
        fixed_baseline_value = float(fixed_baseline) if fixed_baseline is not None else None
    except (TypeError, ValueError):
        fixed_baseline_value = None

    gain_adc_per_pe = raw.get("gain_adc_per_pe")
    try:
        gain_value = float(gain_adc_per_pe) if gain_adc_per_pe is not None else None
    except (TypeError, ValueError):
        gain_value = None
    if gain_value is not None and gain_value <= 0:
        gain_value = None

    return ChannelConfig(
        polarity=polarity,
        geometry=geometry,
        adc_bits=adc_bits,
        fixed_baseline=fixed_baseline_value,
        gain_adc_per_pe=gain_value,
    )


def normalize_channel_metadata_entry(raw: Any) -> ChannelMetadata:
    if not isinstance(raw, Mapping):
        return ChannelMetadata()

    polarity = raw.get("polarity", "unknown")
    if not isinstance(polarity, str) or polarity not in VALID_POLARITIES:
        polarity = "unknown"

    geometry = raw.get("geometry", "unknown")
    if not isinstance(geometry, str) or not geometry.strip():
        geometry = "unknown"

    adc_bits = _normalize_adc_bits(raw.get("adc_bits"))

    return ChannelMetadata(
        polarity=polarity,
        geometry=geometry,
        adc_bits=adc_bits,
    )


def _parse_channel_ref(key: Any) -> HardwareChannel | None:
    if isinstance(key, HardwareChannel):
        return key
    if isinstance(key, tuple | list) and len(key) == 2:
        try:
            return make_channel(key[0], key[1])
        except (TypeError, ValueError):
            return None
    if isinstance(key, str):
        text = key.strip()
        if ":" in text:
            left, right = text.split(":", 1)
            try:
                return make_channel(left.strip(), right.strip())
            except (TypeError, ValueError):
                return None
    return None


def _channel_ref_error(key: Any) -> ValueError:
    return ValueError(
        f"Invalid channel key {key!r}; expected HardwareChannel, (board, channel), "
        'or "board:channel".'
    )


def _select_run_block(config: Any, run_id: str) -> Mapping[Any, Any]:
    if not isinstance(config, Mapping):
        return {}
    run_block = config.get(run_id)
    if isinstance(run_block, Mapping):
        config = run_block
    return config


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_group_sequence(groups: Any) -> list[Mapping[str, Any]]:
    if isinstance(groups, Mapping):
        result: list[Mapping[str, Any]] = []
        for name, group in groups.items():
            if not isinstance(group, Mapping):
                continue
            if "name" in group:
                result.append(group)
            else:
                result.append({"name": str(name), **group})
        return result
    if isinstance(groups, Sequence) and not isinstance(groups, str | bytes):
        return [item for item in groups if isinstance(item, Mapping)]
    return []


def _resolve_layered_channel_overrides(
    config_block: Mapping[str, Any],
    channel: HardwareChannel,
    *,
    group_value_key: str,
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}

    defaults = config_block.get("defaults")
    if isinstance(defaults, Mapping):
        resolved.update(defaults)

    for group in _as_group_sequence(config_block.get("groups")):
        if not _channel_in_selector(channel, group.get("channels")):
            continue
        values = group.get(group_value_key)
        if values is None and group_value_key != "config":
            values = group.get("config")
        if isinstance(values, Mapping):
            resolved.update(values)

    channels_block = config_block.get("channels")
    if not isinstance(channels_block, Mapping):
        channels_block = config_block
    if isinstance(channels_block, Mapping):
        direct = channels_block.get(channel)
        if isinstance(direct, Mapping):
            resolved.update(direct)
        else:
            for key, values in channels_block.items():
                if key in {"defaults", "groups", "channels"}:
                    continue
                parsed = _parse_channel_ref(key)
                if parsed is None:
                    raise _channel_ref_error(key)
                if parsed != channel:
                    continue
                if not isinstance(values, Mapping):
                    raise ValueError(
                        f"Invalid channel config for {key!r}; expected a mapping, got "
                        f"{type(values).__name__}."
                    )
                resolved.update(values)
                break

    return resolved


def _iter_metadata_layers(channel_metadata: Any) -> list[Mapping[str, Any]]:
    if isinstance(channel_metadata, Mapping):
        return [channel_metadata]
    if isinstance(channel_metadata, Sequence) and not isinstance(channel_metadata, str | bytes):
        return [item for item in channel_metadata if isinstance(item, Mapping)]
    return []


def get_channel_metadata_config(context: Any, run_id: str) -> list[Mapping[str, Any]]:
    """Return top-level channel_metadata layers for a run in precedence order."""
    context_config = _as_mapping(getattr(context, "config", {}))
    base = context_config.get("channel_metadata")

    run_config: Mapping[str, Any] = {}
    run_config_getter = getattr(context, "get_run_config", None)
    if callable(run_config_getter):
        try:
            run_config = _as_mapping(run_config_getter(run_id))
        except Exception:
            run_config = {}
    override = run_config.get("channel_metadata")

    layers: list[Mapping[str, Any]] = []
    if isinstance(base, Mapping):
        layers.append(base)
    if isinstance(override, Mapping):
        layers.append(override)
    return layers


def get_plugin_run_config(
    context: Any,
    plugin: Any,
    run_id: str,
) -> dict[str, Any]:
    """Return raw run-level config tree for a plugin.

    Supported shapes, in precedence order:
    1) ``context.get_plugin_run_config(plugin, run_id)`` if available
    2) ``context.get_run_config(run_id)["plugins"][plugin_name]``
    3) ``context.config[plugin_name]["runs"][run_id]``
    """
    getter = getattr(context, "get_plugin_run_config", None)
    if callable(getter):
        try:
            result = getter(plugin, run_id)
        except TypeError:
            result = getter(getattr(plugin, "provides", plugin), run_id)
        if isinstance(result, Mapping):
            return dict(result)

    plugin_name = getattr(plugin, "provides", str(plugin))

    run_config_getter = getattr(context, "get_run_config", None)
    if callable(run_config_getter):
        try:
            run_config = run_config_getter(run_id)
        except Exception:
            run_config = {}
        plugins_block = _as_mapping(_as_mapping(run_config).get("plugins"))
        plugin_block = plugins_block.get(plugin_name)
        if isinstance(plugin_block, Mapping):
            return dict(plugin_block)

    context_config = _as_mapping(getattr(context, "config", {}))
    plugin_block = _as_mapping(context_config.get(plugin_name))
    runs_block = _as_mapping(plugin_block.get("runs"))
    run_block = runs_block.get(run_id)
    if isinstance(run_block, Mapping):
        return dict(run_block)

    return {}


def _channel_in_selector(channel: HardwareChannel, selectors: Any) -> bool:
    if not isinstance(selectors, Sequence) or isinstance(selectors, str | bytes):
        return False
    for item in selectors:
        parsed = _parse_channel_ref(item)
        if parsed == channel:
            return True
    return False


def resolve_plugin_channel_overrides(
    plugin_run_config: Mapping[str, Any],
    channel: HardwareChannel,
) -> dict[str, Any]:
    """Resolve run/group/channel override layers for a specific channel."""
    return _resolve_layered_channel_overrides(
        plugin_run_config,
        channel,
        group_value_key="config",
    )


def resolve_effective_channel_config(
    context: Any,
    plugin: Any,
    run_id: str,
    board: int,
    channel: int,
    base_values: Mapping[str, Any] | None = None,
    channel_config: Mapping[str, Any] | None = None,
) -> PluginChannelRule:
    """Resolve final plugin config for one hardware channel."""
    hw_channel = HardwareChannel(board=int(board), channel=int(channel))
    resolved: dict[str, Any] = {}
    if isinstance(base_values, Mapping):
        resolved.update(base_values)

    if isinstance(channel_config, Mapping):
        selected = _select_run_block(channel_config, run_id)
        resolved.update(resolve_plugin_channel_overrides(selected, hw_channel))

    return PluginChannelRule(channel=hw_channel, values=resolved)


def resolve_effective_channel_option(
    context: Any,
    plugin: Any,
    run_id: str,
    board: int,
    channel: int,
    option_name: str,
    default: Any = None,
    base_values: Mapping[str, Any] | None = None,
    channel_config: Mapping[str, Any] | None = None,
) -> Any:
    """Resolve a single effective option for one hardware channel."""
    rule = resolve_effective_channel_config(
        context=context,
        plugin=plugin,
        run_id=run_id,
        board=board,
        channel=channel,
        base_values=base_values,
        channel_config=channel_config,
    )
    return rule.get(option_name, default)


def resolve_channel_configs(
    channel_config: Any,
    run_id: str,
    channels: Iterable[HardwareChannel],
    plugin_name: str,
) -> dict[HardwareChannel, ChannelConfig]:
    channel_list = sorted(set(channels))
    if not channel_list:
        return {}
    if channel_config is None:
        return {channel: ChannelConfig() for channel in channel_list}

    if channel_config is not None and not isinstance(channel_config, Mapping):
        warnings.warn(
            f"Plugin '{plugin_name}' run '{run_id}': channel config must be dict-like, "
            "falling back to unknown defaults.",
            UserWarning,
            stacklevel=3,
        )
        return {channel: ChannelConfig() for channel in channel_list}

    selected = _select_run_block(channel_config, run_id)
    if isinstance(selected.get("channels"), Mapping):
        selected = selected["channels"]
    parsed: dict[HardwareChannel, ChannelConfig] = {}
    issues: dict[HardwareChannel, list[str]] = defaultdict(list)

    for key, value in selected.items():
        hw_channel = _parse_channel_ref(key)
        if hw_channel is None:
            raise _channel_ref_error(key)

        parsed[hw_channel] = normalize_channel_config_entry(value)

        if not isinstance(value, Mapping):
            issues[hw_channel].extend(
                ["polarity", "geometry", "adc_bits", "fixed_baseline", "gain_adc_per_pe"]
            )
            continue
        if parsed[hw_channel].polarity == "unknown" and value.get("polarity") is not None:
            issues[hw_channel].append("polarity")
        if parsed[hw_channel].geometry == "unknown" and value.get("geometry") is not None:
            issues[hw_channel].append("geometry")
        if parsed[hw_channel].adc_bits is None and value.get("adc_bits") is not None:
            issues[hw_channel].append("adc_bits")
        if parsed[hw_channel].fixed_baseline is None and value.get("fixed_baseline") is not None:
            issues[hw_channel].append("fixed_baseline")
        if parsed[hw_channel].gain_adc_per_pe is None and value.get("gain_adc_per_pe") is not None:
            issues[hw_channel].append("gain_adc_per_pe")

    resolved: dict[HardwareChannel, ChannelConfig] = {}
    missing: list[HardwareChannel] = []
    for channel in channel_list:
        config = parsed.get(channel)
        if config is None:
            config = ChannelConfig()
            missing.append(channel)
        resolved[channel] = config

    if missing:
        for channel in missing:
            issues[channel].extend(["polarity", "geometry", "adc_bits"])

    if issues:
        parts = []
        for channel in sorted(issues):
            fields = ",".join(sorted(set(issues[channel])))
            parts.append(f"board{channel.board}:ch{channel.channel}[{fields}]")
        warnings.warn(
            f"Plugin '{plugin_name}' run '{run_id}': missing/invalid channel_metadata -> "
            + "; ".join(parts),
            UserWarning,
            stacklevel=3,
        )

    return resolved


def resolve_effective_channel_metadata(
    channel_metadata: Any,
    *,
    board: int,
    channel: int,
) -> ChannelMetadata:
    hw_channel = HardwareChannel(board=int(board), channel=int(channel))
    resolved: dict[str, Any] = {}
    for selected in _iter_metadata_layers(channel_metadata):
        resolved.update(
            _resolve_layered_channel_overrides(
                selected,
                hw_channel,
                group_value_key="metadata",
            )
        )
    return normalize_channel_metadata_entry(resolved)


def resolve_channel_metadata_map(
    channel_metadata: Any,
    *,
    channels: Iterable[HardwareChannel],
) -> dict[HardwareChannel, ChannelMetadata]:
    channel_list = sorted(set(channels))
    return {
        hw_channel: resolve_effective_channel_metadata(
            channel_metadata,
            board=hw_channel.board,
            channel=hw_channel.channel,
        )
        for hw_channel in channel_list
    }


def resolve_channel_value_map(
    channel_config: Any,
    run_id: str,
    channels: Iterable[HardwareChannel],
    plugin_name: str,
    value_name: str,
) -> dict[HardwareChannel, float]:
    channel_list = sorted(set(channels))
    if not channel_list or channel_config is None:
        return {}
    if not isinstance(channel_config, Mapping):
        warnings.warn(
            f"Plugin '{plugin_name}' run '{run_id}': channel config must be dict-like, "
            f"cannot resolve '{value_name}'.",
            UserWarning,
            stacklevel=3,
        )
        return {}

    selected = _select_run_block(channel_config, run_id)
    if isinstance(selected.get("channels"), Mapping):
        selected = selected["channels"]
    values: dict[HardwareChannel, float] = {}
    invalid: list[str] = []
    for key, raw_value in selected.items():
        hw_channel = _parse_channel_ref(key)
        if hw_channel is None:
            raise _channel_ref_error(key)
        if isinstance(raw_value, Mapping):
            raw_value = raw_value.get(value_name)
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            if raw_value is not None:
                invalid.append(f"board{hw_channel.board}:ch{hw_channel.channel}")
            continue
        if value_name == "gain_adc_per_pe" and value <= 0:
            invalid.append(f"board{hw_channel.board}:ch{hw_channel.channel}")
            continue
        values[hw_channel] = value

    if invalid:
        warnings.warn(
            f"Plugin '{plugin_name}' run '{run_id}': invalid '{value_name}' entries -> "
            + ", ".join(sorted(invalid)),
            UserWarning,
            stacklevel=3,
        )
    return values


def get_channel_config(
    configs: Mapping[HardwareChannel, ChannelConfig],
    board: int,
    channel: int,
) -> ChannelConfig:
    return configs.get(HardwareChannel(int(board), int(channel)), ChannelConfig())


def get_channel_metadata(
    configs: Mapping[HardwareChannel, ChannelMetadata],
    board: int,
    channel: int,
) -> ChannelMetadata:
    return configs.get(HardwareChannel(int(board), int(channel)), ChannelMetadata())


def get_channel_config_for_record(
    configs: Mapping[HardwareChannel, ChannelConfig],
    record: np.void | Mapping[str, Any],
) -> ChannelConfig:
    return configs.get(channel_from_record(record), ChannelConfig())


def get_polarity(
    configs: Mapping[HardwareChannel, ChannelConfig],
    board: int,
    channel: int,
    default: str = "unknown",
) -> str:
    polarity = get_channel_config(configs, board, channel).polarity
    return polarity if polarity in VALID_POLARITIES else default


def get_fixed_baseline(
    configs: Mapping[HardwareChannel, ChannelConfig | float],
    board: int,
    channel: int,
) -> float | None:
    key = HardwareChannel(int(board), int(channel))
    value = configs.get(key)
    if isinstance(value, ChannelConfig):
        return value.fixed_baseline
    if value is None:
        return None
    return float(value)


def get_gain_adc_per_pe(
    configs: Mapping[HardwareChannel, ChannelConfig | float],
    board: int,
    channel: int,
) -> float | None:
    key = HardwareChannel(int(board), int(channel))
    value = configs.get(key)
    if isinstance(value, ChannelConfig):
        return value.gain_adc_per_pe
    if value is None:
        return None
    return float(value)
