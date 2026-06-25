"""Records-backed channel role masks for detector/veto splitting."""

from __future__ import annotations

from typing import Any

import numpy as np

from waveform_analysis.core.hardware.channel import resolve_effective_channel_config
from waveform_analysis.core.plugins.core.base import Option, Plugin

ROLE_DETECTOR = "detector"
ROLE_VETO = "veto"
VALID_ROLES = {ROLE_DETECTOR, ROLE_VETO}


def _empty_mask(length: int) -> np.ndarray:
    return np.zeros(length, dtype=np.bool_)


def _resolve_roles(
    context: Any,
    plugin: Plugin,
    run_id: str,
    records: np.ndarray,
) -> np.ndarray:
    names = records.dtype.names or ()
    missing = [name for name in ("board", "channel") if name not in names]
    if missing:
        raise ValueError(f"{plugin.provides} records input missing fields: {missing}")

    channel_config = context.get_config(plugin, "channel_config")
    roles = np.full(len(records), ROLE_DETECTOR, dtype="U8")
    rule_cache: dict[tuple[int, int], str] = {}

    boards = records["board"].astype(np.int16, copy=False)
    channels = records["channel"].astype(np.int16, copy=False)
    for board, channel in zip(boards.tolist(), channels.tolist(), strict=False):
        key = (int(board), int(channel))
        if key in rule_cache:
            continue
        rule = resolve_effective_channel_config(
            context=context,
            plugin=plugin,
            run_id=run_id,
            board=key[0],
            channel=key[1],
            base_values={"role": ROLE_DETECTOR},
            channel_config=channel_config,
        )
        role = str(rule.get("role", ROLE_DETECTOR)).strip().lower()
        if role not in VALID_ROLES:
            raise ValueError(
                f"{plugin.provides} invalid role {role!r} for channel "
                f"{key[0]}:{key[1]}; expected one of {sorted(VALID_ROLES)}"
            )
        rule_cache[key] = role

    for key, role in rule_cache.items():
        roles[(boards == key[0]) & (channels == key[1])] = role
    return roles


class _RecordsChannelRoleMaskPlugin(Plugin):
    """Base class for records channel role masks."""

    depends_on = ["records", "records_asymmetry_mask"]
    save_when = "always"
    output_dtype = np.dtype(np.bool_)
    role: str = ROLE_DETECTOR

    options = {
        "channel_config": Option(
            default=None,
            type=dict,
            help=(
                "按 (board, channel) 的通道角色配置；role='detector' 进入正常 hit，"
                "role='veto' 仅作为 veto 通道保留。"
            ),
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        records = context.get_data(run_id, "records")
        if not isinstance(records, np.ndarray):
            raise ValueError(f"{self.provides} expects records as a structured array")

        mask = _empty_mask(len(records))
        if len(records) == 0:
            return mask

        roles = _resolve_roles(context, self, run_id, records)
        asymmetry_mask = np.asarray(
            context.get_data(run_id, "records_asymmetry_mask"),
            dtype=np.bool_,
        )
        if len(asymmetry_mask) != len(records):
            raise ValueError(
                "records_asymmetry_mask length mismatch: "
                f"mask has {len(asymmetry_mask)} entries, records has {len(records)}"
            )
        return (roles == self.role) & asymmetry_mask


class RecordsDetectorMaskPlugin(_RecordsChannelRoleMaskPlugin):
    """Bool mask for records that should enter normal detector hit finding."""

    provides = "records_detector_mask"
    description = "Bool mask for detector-channel records after channel-role splitting."
    version = "0.1.0"
    role = ROLE_DETECTOR


class RecordsVetoMaskPlugin(_RecordsChannelRoleMaskPlugin):
    """Bool mask for records that should be held out as veto channels."""

    provides = "records_veto_mask"
    description = "Bool mask for veto-channel records after channel-role splitting."
    version = "0.1.0"
    role = ROLE_VETO


__all__ = [
    "RecordsDetectorMaskPlugin",
    "RecordsVetoMaskPlugin",
]
