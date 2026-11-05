#!/usr/bin/env python
"""从 run_config.json 或显式映射读取 SPE 面积增益，并生成分析表。

示例保留 calibration.gain_adc_per_pe 作为分析层的配置格式；调用方负责读取并
换算，不会向 basic_features 或其它插件自动注入增益。area 是 ADC 采样值之和，
增益必须是相同采样与积分定义下的 ADC·sample/PE。height 保留 ADC 单位。

运行此文件仅打印配置示例。真实数据处理可调用 complete_workflow_example。
"""

import json

import numpy as np
import pandas as pd

from waveform_analysis import Context
from waveform_analysis.core.hardware import (
    get_gain_adc_per_pe,
    resolve_channel_value_map,
    unique_hardware_channels,
)
from waveform_analysis.plugins import BasicFeaturesPlugin, plugins_io, plugins_waveform


def calibrated_features(
    ctx: Context, run_id: str, gain_config: dict[str, float] | None = None
) -> pd.DataFrame:
    """显式映射优先；未传映射时读取 run 的 calibration.gain_adc_per_pe。"""
    if gain_config is None:
        run_config = ctx.get_run_config(run_id)
        gain_config = run_config["calibration"]["gain_adc_per_pe"]
    if any(not np.isfinite(value) or value <= 0 for value in gain_config.values()):
        raise ValueError("SPE 面积增益必须为有限的正数，单位为 ADC·sample/PE")
    df = pd.DataFrame(ctx.get_data(run_id, "basic_features"))
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
    return df


def complete_workflow_example(
    run_id: str, daq_root: str = "DAQ", daq_adapter: str = "vx2730"
) -> pd.DataFrame:
    """从真实 DAQ 计算 basic_features，然后读取该 run 的面积标定。"""
    ctx = Context(
        storage_dir="./wa_data",
        config={
            "data_root": daq_root,
            "daq_adapter": daq_adapter,
            # 本例选择把 JSON 放在各 DAQ run 目录中，故显式指定路径。
            "run_config_path": "{data_root}/{run_id}/run_config.json",
        },
    )
    ctx.register(*plugins_io(), *plugins_waveform(), BasicFeaturesPlugin())
    return calibrated_features(ctx, run_id)


def main() -> None:
    run_config = {
        "calibration": {
            "gain_adc_per_pe": {"0:9": 200.0, "0:10": 210.0, "1:9": 180.0},
        },
    }
    print("将下列示例标定替换为实测值，并合并到 DAQ/<run_id>/run_config.json：")
    print(json.dumps(run_config, indent=2, ensure_ascii=False))
    print("不要覆盖已有的 run、DAQ 或 hardware 元数据。批量设置可用 set_gain_batch.py。")
    print("调用 complete_workflow_example(run_id) 生成含 area_pe 的 DataFrame。")
    print("显式覆盖：calibrated_features(ctx, run_id, gain_config={'0:9': 200.0})。")
    print("缺少整个标定节会报错；部分通道缺少增益时，对应 area_pe 为 NaN。")
    print("area_pe: PE；height: ADC。标定结果不自动进入插件缓存，改增益后需重新导出。")


if __name__ == "__main__":
    main()
