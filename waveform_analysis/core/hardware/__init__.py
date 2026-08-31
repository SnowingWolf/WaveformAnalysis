"""Hardware domain helpers."""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    "ChannelConfig": (".channel", "ChannelConfig"),
    "ChannelMetadata": (".channel", "ChannelMetadata"),
    "HardwareChannel": (".channel", "HardwareChannel"),
    "PluginChannelRule": (".channel", "PluginChannelRule"),
    "channel_from_fields": (".channel", "channel_from_fields"),
    "channel_from_record": (".channel", "channel_from_record"),
    "extract_board_channel_fields": (".channel", "extract_board_channel_fields"),
    "get_channel_config": (".channel", "get_channel_config"),
    "get_channel_metadata": (".channel", "get_channel_metadata"),
    "get_channel_config_for_record": (".channel", "get_channel_config_for_record"),
    "get_fixed_baseline": (".channel", "get_fixed_baseline"),
    "get_gain_adc_per_pe": (".channel", "get_gain_adc_per_pe"),
    "get_channel_metadata_config": (".channel", "get_channel_metadata_config"),
    "get_polarity": (".channel", "get_polarity"),
    "get_plugin_run_config": (".channel", "get_plugin_run_config"),
    "group_indices_by_hardware_channel": (
        ".channel",
        "group_indices_by_hardware_channel",
    ),
    "iter_hardware_channel_groups": (".channel", "iter_hardware_channel_groups"),
    "iter_hardware_channel_indices": (".channel", "iter_hardware_channel_indices"),
    "make_channel": (".channel", "make_channel"),
    "normalize_channel_config_entry": (".channel", "normalize_channel_config_entry"),
    "normalize_channel_metadata_entry": (
        ".channel",
        "normalize_channel_metadata_entry",
    ),
    "require_board_channel_fields": (".channel", "require_board_channel_fields"),
    "resolve_channel_configs": (".channel", "resolve_channel_configs"),
    "resolve_channel_metadata_map": (".channel", "resolve_channel_metadata_map"),
    "resolve_effective_channel_config": (
        ".channel",
        "resolve_effective_channel_config",
    ),
    "resolve_effective_channel_metadata": (
        ".channel",
        "resolve_effective_channel_metadata",
    ),
    "resolve_effective_channel_option": (
        ".channel",
        "resolve_effective_channel_option",
    ),
    "resolve_plugin_channel_overrides": (
        ".channel",
        "resolve_plugin_channel_overrides",
    ),
    "resolve_channel_value_map": (".channel", "resolve_channel_value_map"),
    "unique_hardware_channels": (".channel", "unique_hardware_channels"),
    # Geometry
    "DEFAULT_PMT_GAIN": (".geometry", "DEFAULT_PMT_GAIN"),
    "PmtEntry": (".geometry", "PmtEntry"),
    "PmtLayout": (".geometry", "PmtLayout"),
    "load_fallback_layout": (".geometry", "load_fallback_layout"),
    "load_pmt_layout_from_config": (".geometry", "load_pmt_layout_from_config"),
    "load_pmt_layout_from_runinfo": (".geometry", "load_pmt_layout_from_runinfo"),
}

__all__ = [
    "ChannelConfig",
    "ChannelMetadata",
    "HardwareChannel",
    "PluginChannelRule",
    "channel_from_fields",
    "channel_from_record",
    "extract_board_channel_fields",
    "get_channel_config",
    "get_channel_metadata",
    "get_channel_config_for_record",
    "get_fixed_baseline",
    "get_gain_adc_per_pe",
    "get_channel_metadata_config",
    "get_polarity",
    "get_plugin_run_config",
    "group_indices_by_hardware_channel",
    "iter_hardware_channel_groups",
    "iter_hardware_channel_indices",
    "make_channel",
    "normalize_channel_config_entry",
    "normalize_channel_metadata_entry",
    "require_board_channel_fields",
    "resolve_channel_configs",
    "resolve_channel_metadata_map",
    "resolve_effective_channel_config",
    "resolve_effective_channel_metadata",
    "resolve_effective_channel_option",
    "resolve_plugin_channel_overrides",
    "resolve_channel_value_map",
    "unique_hardware_channels",
    # Geometry
    "DEFAULT_PMT_GAIN",
    "PmtEntry",
    "PmtLayout",
    "load_fallback_layout",
    "load_pmt_layout_from_config",
    "load_pmt_layout_from_runinfo",
]


def __getattr__(name: str) -> object:
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__() -> list[str]:
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
