"""完整事件重建插件

整合 S1-S2 配对、位置重建和事件级别特征。

此插件是事件分析链的最终阶段，整合所有前置分析结果，
输出完整的物理事件记录，包含：
- S1/S2 信号特征
- 空间位置信息
- 事件拓扑特征（预留）
- 质量评估指标

第一版 (v0.0.0) 仅建立数据结构和 lineage，高级特征预留接口。

事件重建流程：
1. 从 s1_s2_pairs 获取选定配对
2. 从 position_reconstruction 获取位置信息
3. 复制基本特征
4. 评估事件质量
5. 输出完整事件记录

Author: Claude Code
Version: 0.0.0 (Placeholder for lineage)
"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin

# ============================================================================
# 质量标志定义
# ============================================================================

FLAG_EVENT_VALID = 1 << 0  # 事件通过基本质量检查
FLAG_POSITION_VALID = 1 << 1  # 位置重建有效
FLAG_FIDUCIAL_VOLUME = 1 << 2  # 在基准体积内
FLAG_SINGLE_SCATTER = 1 << 3  # 单次散射事件（高置信度）

# 问题标志
FLAG_AMBIGUOUS_PAIRING = 1 << 8  # 配对存在歧义
FLAG_LOW_S1 = 1 << 9  # S1 信号过弱
FLAG_LOW_S2 = 1 << 10  # S2 信号过弱


# ============================================================================
# 数据结构定义
# ============================================================================

EVENT_DTYPE = np.dtype(
    [
        # === Identity ===
        ("event_id", "i8"),  # 全局唯一标识
        ("event_number", "i8"),  # run 内事件编号（从 0 开始）
        ("run_id", "U32"),  # 运行 ID
        # === References ===
        ("pair_id", "i8"),  # S1-S2 配对 ID
        ("s1_peak_id", "i8"),  # S1 peak ID
        ("s2_peak_id", "i8"),  # S2 peak ID
        # === Position (mm) ===
        ("x", "f4"),  # X 坐标
        ("y", "f4"),  # Y 坐标
        ("z", "f4"),  # Z 坐标 (漂移距离)
        ("r", "f4"),  # 径向坐标 r = sqrt(x^2 + y^2)
        # === Timing (ns) ===
        ("drift_time_ns", "f4"),  # 漂移时间
        ("s1_time", "f8"),  # S1 时间（相对于 run 起点）
        ("s2_time", "f8"),  # S2 时间
        # === Raw signals ===
        ("s1_area", "f4"),  # S1 原始面积
        ("s2_area", "f4"),  # S2 原始面积
        ("log10_s2_s1", "f4"),  # log10(S2/S1)
        ("s1_n_channels", "i2"),  # S1 通道数
        ("s2_n_channels", "i2"),  # S2 通道数
        # === Topology (预留) ===
        ("s1_area_fraction_top", "f4"),  # S1 顶部光电倍增管占比
        ("s2_area_fraction_top", "f4"),  # S2 顶部光电倍增管占比
        ("s1_rise_time", "f4"),  # S1 上升时间 (ns)
        ("s2_rise_time", "f4"),  # S2 上升时间 (ns)
        # === Basic quality ===
        ("n_s1_candidates_for_s2", "i4"),  # 该 S2 的 S1 候选数
        ("n_s2_candidates_for_s1", "i4"),  # 该 S1 的 S2 候选数
        # === Flags ===
        ("flags", "u4"),  # 状态标志位
    ]
)


# ============================================================================
# 插件实现
# ============================================================================


class EventPlugin(Plugin):
    """完整事件重建插件

    整合 S1-S2 配对和位置重建，输出完整的物理事件记录。

    输入:
    - s1_s2_pairs: S1-S2 配对结果
    - position_reconstruction: 位置重建结果

    输出:
    - events: 完整事件记录

    v0.0.0 状态:
    - 仅建立数据结构和依赖关系
    - 基本特征从输入数据复制
    - 拓扑特征使用占位值（预留接口）
    - 质量评估使用简单阈值检查

    未来版本计划:
    - v0.1.0: 基础特征提取和质量检查
    - v0.2.0: 拓扑特征计算（需要通道波形信息）
    - v0.3.0: 高级质量评估
    - v1.0.0: 完整的事件重建和分类
    """

    provides = "events"
    depends_on = ["s1_s2_pairs", "position_reconstruction"]
    description = "Complete event reconstruction from S1-S2 pairs and position"
    version = "0.0.1"
    save_when = "always"
    output_dtype = EVENT_DTYPE

    options = {
        "min_s1": Option(
            default=0.0,
            type=float,
            help="最小 S1 阈值（用于质量筛选）",
            min_value=0.0,
        ),
        "min_s2": Option(
            default=0.0,
            type=float,
            help="最小 S2 阈值（用于质量筛选）",
            min_value=0.0,
        ),
        "fiducial_radius": Option(
            default=None,
            type=(float, type(None)),
            help="基准体积半径 (mm)。None 表示不应用",
        ),
        "fiducial_z_range": Option(
            default=None,
            type=(tuple, type(None)),
            help="基准体积 Z 范围 (z_min, z_max) mm。None 表示不应用",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        """执行完整事件重建

        v0.0.0 实现:
        1. 关联 pairs 和 positions（通过 pair_id）
        2. 复制基本特征
        3. 设置拓扑特征占位值
        4. 应用简单质量标志

        Args:
            context: 上下文对象
            run_id: 运行 ID

        Returns:
            完整事件记录数组
        """
        # 获取依赖数据
        pairs = context.get_data(run_id, "s1_s2_pairs")
        positions = context.get_data(run_id, "position_reconstruction")

        # 获取配置
        min_s1 = context.get_config(self, "min_s1")
        min_s2 = context.get_config(self, "min_s2")
        fiducial_r = context.get_config(self, "fiducial_radius")
        fiducial_z = context.get_config(self, "fiducial_z_range")

        # 筛选已选定的配对
        selected_pairs = pairs[pairs["selected"]]

        # 空数据处理
        if len(selected_pairs) == 0 or len(positions) == 0:
            return np.zeros(0, dtype=EVENT_DTYPE)

        # 初始化结果数组
        n_events = len(selected_pairs)
        events = np.zeros(n_events, dtype=EVENT_DTYPE)

        # 填充基本标识
        events["event_id"] = np.arange(n_events)
        events["event_number"] = np.arange(n_events)
        events["run_id"] = run_id

        # 填充引用 ID
        events["pair_id"] = selected_pairs["pair_id"]
        events["s1_peak_id"] = selected_pairs["s1_peak_id"]
        events["s2_peak_id"] = selected_pairs["s2_peak_id"]

        # 填充位置信息
        events["x"] = positions["x"]
        events["y"] = positions["y"]
        events["z"] = positions["z"]
        events["r"] = positions["r"]

        # 填充时间信息
        events["s1_time"] = selected_pairs["s1_time"] / 1e12  # ps -> s
        events["s2_time"] = selected_pairs["s2_time"] / 1e12
        events["drift_time_ns"] = selected_pairs["drift_time_ns"]

        # 填充原始信号
        events["s1_area"] = selected_pairs["s1_area"]
        events["s2_area"] = selected_pairs["s2_area"]
        events["log10_s2_s1"] = selected_pairs["log10_s2_s1"]
        events["s1_n_channels"] = selected_pairs["s1_n_channels"]
        events["s2_n_channels"] = selected_pairs["s2_n_channels"]

        # 拓扑特征（v0.0.0 占位）
        events["s1_area_fraction_top"] = 0.5  # 占位
        events["s2_area_fraction_top"] = 0.5  # 占位
        events["s1_rise_time"] = 0.0  # 占位
        events["s2_rise_time"] = 0.0  # 占位

        # 歧义信息
        events["n_s1_candidates_for_s2"] = selected_pairs["n_s1_candidates_for_s2"]
        events["n_s2_candidates_for_s1"] = selected_pairs["n_s2_candidates_for_s1"]

        # 设置标志位
        self._apply_quality_flags(
            events, positions, selected_pairs, min_s1, min_s2, fiducial_r, fiducial_z
        )

        return events

    def _apply_quality_flags(
        self,
        events: np.ndarray,
        positions: np.ndarray,
        pairs: np.ndarray,
        min_s1: float,
        min_s2: float,
        fiducial_r: float | None,
        fiducial_z: tuple | None,
    ):
        """应用质量标志（in-place 修改）

        v0.0.0 实现简单的阈值检查。
        """
        # 位置有效性
        position_valid = positions["flags"] & 0x01 != 0  # FLAG_POSITION_VALID
        events["flags"][position_valid] |= FLAG_POSITION_VALID

        # 信号阈值
        s1_valid = events["s1_area"] >= min_s1
        s2_valid = events["s2_area"] >= min_s2

        low_s1 = ~s1_valid
        low_s2 = ~s2_valid
        events["flags"][low_s1] |= FLAG_LOW_S1
        events["flags"][low_s2] |= FLAG_LOW_S2

        # 基准体积
        if fiducial_r is not None:
            in_fiducial_r = events["r"] <= fiducial_r
        else:
            in_fiducial_r = np.ones(len(events), dtype=bool)

        if fiducial_z is not None:
            z_min, z_max = fiducial_z
            in_fiducial_z = (events["z"] >= z_min) & (events["z"] <= z_max)
        else:
            in_fiducial_z = np.ones(len(events), dtype=bool)

        in_fiducial = in_fiducial_r & in_fiducial_z
        events["flags"][in_fiducial] |= FLAG_FIDUCIAL_VOLUME

        # 配对歧义
        ambiguous = (events["n_s1_candidates_for_s2"] > 1) | (events["n_s2_candidates_for_s1"] > 1)
        events["flags"][ambiguous] |= FLAG_AMBIGUOUS_PAIRING

        # 整体有效性（v0.0.0: 简单逻辑）
        valid = position_valid & s1_valid & s2_valid
        events["flags"][valid] |= FLAG_EVENT_VALID

        # 单次散射（v0.0.0: 占位，基于配对分数）
        high_score = pairs["score_total"] > 0.5  # 占位阈值
        events["flags"][high_score] |= FLAG_SINGLE_SCATTER
