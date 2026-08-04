"""能量重建插件（结构占位版本）

基于 S1-S2 配对的能量重建。

此插件从选定的 S1-S2 配对中提取信号面积信息，计算事件的能量。

核心功能：
- 从 s1_s2_pairs 中提取 selected 配对
- 定义完整的能量重建输出结构与接口
- 当前为结构占位：能量值填 NaN，算法后续填充

状态：
- v0.1.0: 结构占位，定义 dtype、依赖、接口与 compute 骨架，未实现实际算法

能量重建方法（规划）：
- S1 能量: 基于 S1 面积与增益标定
- S2 能量: 基于 S2 面积与增益标定
- 总能量: 组合 S1/S2 能量

版本历史：
- v0.1.0: 结构占位，完整 dtype + compute 骨架

Author: Claude Code
Version: 0.1.0
"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin

# ============================================================================
# 质量标志定义
# ============================================================================

FLAG_ENERGY_RECONSTRUCTED = 1 << 0  # 能量重建成功
FLAG_S1_ENERGY_VALID = 1 << 1  # S1 能量有效
FLAG_S2_ENERGY_VALID = 1 << 2  # S2 能量有效
FLAG_LOW_S1_SIGNAL = 1 << 3  # S1 信号太弱，能量重建质量低
FLAG_LOW_S2_SIGNAL = 1 << 4  # S2 信号太弱，能量重建质量低
FLAG_SATURATED_S2 = 1 << 5  # S2 饱和（预留）
FLAG_ENERGY_NOT_IMPLEMENTED = 1 << 6  # 结构占位：算法未实现


# ============================================================================
# 数据结构定义
# ============================================================================

ENERGY_RECONSTRUCTION_DTYPE = np.dtype(
    [
        # === Identity ===
        ("event_id", "i8"),  # 事件唯一标识
        ("pair_id", "i8"),  # 对应的 S1-S2 配对 ID
        ("s1_peak_id", "i8"),  # S1 peak ID
        ("s2_peak_id", "i8"),  # S2 peak ID
        # === Energy (单位: keV) ===
        ("s1_energy", "f4"),  # S1 能量
        ("s2_energy", "f4"),  # S2 能量
        ("total_energy", "f4"),  # 总能量
        ("s1_energy_fraction", "f4"),  # S1 能量占总能量比例
        # === Energy uncertainty (单位: keV) ===
        ("s1_energy_err", "f4"),  # S1 能量不确定度
        ("s2_energy_err", "f4"),  # S2 能量不确定度
        ("total_energy_err", "f4"),  # 总能量不确定度
        # === Reconstruction quality ===
        ("energy_chi2", "f4"),  # 能量重建的卡方值
        ("energy_ndf", "i2"),  # 能量重建的自由度
        ("energy_goodness", "f4"),  # 整体能量质量 (0-1)
        # === Reconstruction method ===
        ("s1_method", "U16"),  # S1 能量方法: "area_scale", "none"
        ("s2_method", "U16"),  # S2 能量方法: "area_scale", "none"
        # === Input observables ===
        ("s1_area", "f4"),  # S1 面积（用于标定）
        ("s2_area", "f4"),  # S2 面积（用于标定）
        ("s1_n_channels", "i2"),  # S1 通道数
        ("s2_n_channels", "i2"),  # S2 通道数
        ("drift_time_ns", "f4"),  # 漂移时间 (ns)
        # === Flags ===
        ("flags", "u4"),  # 状态标志位
    ]
)


# ============================================================================
# 插件实现
# ============================================================================


class EnergyReconstructionPlugin(Plugin):
    """能量重建插件（结构占位版本）

    从选定的 S1-S2 配对重建事件能量。

    输入:
    - s1_s2_pairs: S1-S2 配对结果（仅处理 selected=True 的配对）

    输出:
    - energy_reconstruction: 能量重建结果

    v0.1.0 功能:
    - 定义完整的输出结构与接口
    - 筛选 selected 配对并填充身份与可观测字段
    - 能量字段填占位值 NaN，标志 FLAG_ENERGY_NOT_IMPLEMENTED

    未来版本计划:
    - v0.2.0: 实现基于面积的线性标定能量重建
    - v1.0.0: 位置相关能量校正（电场、光收集效率）
    """

    provides = "energy_reconstruction"
    depends_on = ["s1_s2_pairs"]
    description = "Reconstruct energy from selected S1-S2 pairs"
    version = "0.1.0"
    save_when = "always"
    output_dtype = ENERGY_RECONSTRUCTION_DTYPE

    options = {
        "s1_energy_scale": Option(
            default=1.0,
            type=float,
            help="S1 面积到能量的转换系数 (keV/PE)，占位默认值",
            min_value=0.0,
        ),
        "s2_energy_scale": Option(
            default=1.0,
            type=float,
            help="S2 面积到能量的转换系数 (keV/PE)，占位默认值",
            min_value=0.0,
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        """执行能量重建（结构占位）

        v0.1.0 实现:
        1. 筛选 selected=True 的配对
        2. 填充身份字段与可观测字段
        3. 能量字段填占位值 NaN，标记算法未实现

        Args:
            context: 上下文对象
            run_id: 运行 ID

        Returns:
            能量重建结果数组
        """
        # 获取依赖数据
        pairs = context.get_data(run_id, "s1_s2_pairs")

        # 筛选已选定的配对
        selected_pairs = pairs[pairs["selected"]]

        # 空数据处理
        if len(selected_pairs) == 0:
            return np.zeros(0, dtype=ENERGY_RECONSTRUCTION_DTYPE)

        n_events = len(selected_pairs)
        energies = np.zeros(n_events, dtype=ENERGY_RECONSTRUCTION_DTYPE)

        # 填充身份信息（向量化）
        energies["event_id"] = np.arange(n_events)
        energies["pair_id"] = selected_pairs["pair_id"]
        energies["s1_peak_id"] = selected_pairs["s1_peak_id"]
        energies["s2_peak_id"] = selected_pairs["s2_peak_id"]

        # 填充可观测字段（直接继承，便于审计）
        energies["s1_area"] = selected_pairs["s1_area"]
        energies["s2_area"] = selected_pairs["s2_area"]
        energies["s1_n_channels"] = selected_pairs["s1_n_channels"]
        energies["s2_n_channels"] = selected_pairs["s2_n_channels"]
        energies["drift_time_ns"] = selected_pairs["drift_time_ns"]

        # === 占位能量值（NaN 表示未计算）===
        placeholder_fields = (
            "s1_energy",
            "s2_energy",
            "total_energy",
            "s1_energy_fraction",
            "s1_energy_err",
            "s2_energy_err",
            "total_energy_err",
            "energy_chi2",
        )
        for field in placeholder_fields:
            energies[field] = np.nan

        energies["energy_ndf"] = 0
        energies["energy_goodness"] = 0.0

        # 方法占位
        energies["s1_method"] = "none"
        energies["s2_method"] = "none"

        # 标记算法未实现
        energies["flags"] |= FLAG_ENERGY_NOT_IMPLEMENTED

        return energies
