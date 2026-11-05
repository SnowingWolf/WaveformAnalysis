#!/usr/bin/env python
"""将 basic_features 转为表格，并在分析层显式进行 SPE 面积标定。

area 是 ADC 采样值之和（ADC·sample），未乘采样间隔。这里的增益须来自相同
采样与积分窗口的 SPE 面积标定，单位为 ADC·sample/PE。height 保留 ADC 单位；
面积增益不能同时用作峰高增益。缺少增益的通道保留为 NaN。
"""

import numpy as np
import pandas as pd

from waveform_analysis import Context
from waveform_analysis.core.hardware import (
    get_gain_adc_per_pe,
    resolve_channel_value_map,
    unique_hardware_channels,
)
from waveform_analysis.plugins import BasicFeaturesPlugin, plugins_io, plugins_waveform


def main() -> None:
    run_id = "demo_run"  # 替换为真实 run，并设置正确的 DAQ adapter。
    ctx = Context(
        storage_dir="./wa_data",
        config={"data_root": "DAQ", "daq_adapter": "vx2730"},
    )
    ctx.register(*plugins_io(), *plugins_waveform(), BasicFeaturesPlugin())
    df = pd.DataFrame(ctx.get_data(run_id, "basic_features"))

    # 示例数值，使用前替换为实测 SPE 面积增益。此映射由分析代码消费。
    gain_config = {f"0:{channel}": 200.0 for channel in range(9, 16)}
    gain_map = resolve_channel_value_map(
        gain_config,
        run_id,
        unique_hardware_channels(df["board"].to_numpy(), df["channel"].to_numpy()),
        plugin_name="analysis",
        value_name="gain_adc_per_pe",
    )
    gains = np.array(
        [get_gain_adc_per_pe(gain_map, row.board, row.channel) for row in df.itertuples()],
        dtype=float,
    )
    df["area_pe"] = df["area"] / gains
    print(df[["record_id", "board", "channel", "area", "area_pe", "height"]].head())
    print("area: ADC·sample；area_pe: PE；height: ADC。标定列不属于插件缓存产物。")


if __name__ == "__main__":
    main()
