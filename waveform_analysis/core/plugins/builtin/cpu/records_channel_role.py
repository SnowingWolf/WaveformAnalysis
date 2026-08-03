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
    agent_doc = {
        "overview": (
            "`records_veto_mask` 输出一个与 `records` 等长的布尔掩码，标记哪些记录应被视为"
            " veto 通道信号而被排除在正常 hit 检测之外。它解决的是物理层面的通道角色问题："
            "实验中部分通道被定义为 veto 通道（例如宇宙线或噪声监测），这些通道检测到信号时，"
            "同一触发窗口内的正常事件应被当作干扰丢弃。\n\n"
            "该插件不会丢弃任何数据，而是产出一个可供下游分析阶段查询的掩码。掩码由两部分"
            "合成：首先按 (board, channel) 从 `channel_config` 解析每个通道的角色（"
            "`role='veto'`），再把角色掩码与 `records_asymmetry_mask` 按位与——即只有"
            "『既是 veto 通道、又通过了波形不对称性筛选』的记录才被置为 True。\n\n"
            "它与 `records_detector_mask` 是互补的兄弟产物，二者共享同一套角色解析逻辑，"
            "仅 `role` 不同；`records_veto_mask` 专门服务于 veto 剔除需求。"
        ),
        "workflow_steps": [
            "读取 records：从 context 获取 `records` 结构化数组，并校验其必须包含 `board` 与 `channel` 字段，缺失即抛错。",
            "解析通道角色：按 (board, channel) 遍历（带 rule_cache 缓存），调用 `channel_config` 解析每个通道的 `role`，非法值抛错。",
            "构建角色掩码：将 `role='veto'` 的通道所对应的所有 records 行标记为 True，其余为 False。",
            "合成不对称掩码：读取 `records_asymmetry_mask`，与角色掩码按位与，得到『veto 且通过不对称筛选』的最终掩码；长度不一致时抛错。",
            "返回结果：输出与 records 等长的 bool 数组。",
        ],
        "behavior_notes": [
            "Only `(board, channel)` pairs present in the channel role config are affected; any channel without an explicit `role` stays `detector`.",
            "The output is the AND of the veto-channel role mask and `records_asymmetry_mask`, so a veto-role record that fails asymmetry selection is NOT masked.",
            "`records` missing `board` or `channel` fields raises `ValueError` explicitly.",
            "Records and `records_asymmetry_mask` must be equal length, otherwise `ValueError` is raised.",
        ],
        "field_notes": {
            "value": "布尔掩码：True 表示该记录属于 veto 通道并已通过不对称性筛选，应在正常的 detector hit 分析中剔除；单位不适用（无物理量纲，仅为布尔标记）。",
        },
        "config_notes": {
            "channel_config": "按 (board, channel) 的通道角色配置；`role='detector'` 进入正常 hit，`role='veto'` 作为 veto 通道保留。不配置的通道默认为 detector。",
        },
        "failure_modes": [
            "`records` 不是结构化数组，或其缺少 `board`/`channel` 字段时抛出 `ValueError`。",
            "`channel_config` 中某通道的 `role` 不是 `detector`/`veto` 时抛出 `ValueError`。",
            "`records_asymmetry_mask` 与 `records` 长度不一致时抛出 `ValueError`。",
        ],
        "downstream_consumers": [],
        "agent_change_notes": [
            "修改角色解析或掩码合成逻辑会同时影响 `records_detector_mask`，请一起回归测试。",
        ],
    }


__all__ = [
    "RecordsDetectorMaskPlugin",
    "RecordsVetoMaskPlugin",
]
