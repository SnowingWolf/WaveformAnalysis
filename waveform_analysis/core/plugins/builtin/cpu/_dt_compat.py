"""Backward-compatible shim. Implementation moved to builtin.shared.dt_compat."""

from waveform_analysis.core.plugins.builtin.shared.dt_compat import (
    get_raw_config_value,
    require_dt_array,
    resolve_dt_config,
)

__all__ = ["get_raw_config_value", "resolve_dt_config", "require_dt_array"]
