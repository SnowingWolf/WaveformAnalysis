#!/usr/bin/env python
"""无需 DAQ 的 SPE 面积标定演示：逐 board:channel 显式换算。

basic_features.area 是 ADC 采样值之和，未乘 dt；gain_adc_per_pe 在本示例中
存放匹配采样间隔、积分窗口及基线方法的 SPE 面积增益（ADC·sample/PE）。
height 仍是 ADC 幅度，需要另行测得的峰高增益才能标定。Context 不自动增加 PE 列。
"""

import numpy as np
import pandas as pd

from waveform_analysis.core.hardware import (
    get_gain_adc_per_pe,
    resolve_channel_value_map,
    unique_hardware_channels,
)
from waveform_analysis.plugins import BasicFeaturesPlugin


def calibrate_area(features: np.ndarray, gain_config: dict[str, float]) -> pd.DataFrame:
    """把单记录特征转表；没有标定的通道 area_pe 为 NaN。"""
    # 外部标定值必须有效；不要把错误标定默默当成缺少标定。
    if any(not np.isfinite(value) or value <= 0 for value in gain_config.values()):
        raise ValueError("SPE 面积增益必须为有限的正数，单位为 ADC·sample/PE")
    df = pd.DataFrame(features)
    gain_map = resolve_channel_value_map(
        gain_config,
        "demo_run",
        unique_hardware_channels(df["board"].to_numpy(), df["channel"].to_numpy()),
        plugin_name="analysis",
        value_name="gain_adc_per_pe",
    )
    gains = np.array(
        [get_gain_adc_per_pe(gain_map, row.board, row.channel) for row in df.itertuples()],
        dtype=float,
    )
    df["area_pe"] = df["area"] / gains
    return df


def main() -> None:
    # 真实分析时改为 features = ctx.get_data(run_id, "basic_features")。
    features = np.zeros(3, dtype=BasicFeaturesPlugin.output_dtype)
    features["record_id"] = [0, 1, 2]
    features["board"] = [0, 1, 1]
    features["channel"] = [0, 0, 1]
    features["area"] = [150.0, 300.0, 80.0]
    features["height"] = [20.0, 25.0, 10.0]
    # 同一 channel 在不同 board 上是不同的硬件通道；故意不配置 1:1。
    gain_config = {"0:0": 15.0, "1:0": 30.0}
    df = calibrate_area(features, gain_config)
    print(df[["record_id", "board", "channel", "area", "area_pe", "height"]])
    print("前两条各为 10 PE；1:1 未标定，area_pe 为 NaN；height 保留 ADC 单位。")
    print("换算在分析层完成。修改增益后须重新生成分析表及其导出文件。")


if __name__ == "__main__":
    main()
