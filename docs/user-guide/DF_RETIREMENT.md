# 旧表格链路退役迁移

**导航**：[文档中心](../README.md) > [用户指南](README.md) > 旧表格链路退役迁移

内置 `df → df_events → df_paired` 链路已移除。现行插件保留结构化产物，调用方在分析层
按所需粒度转为 pandas 表格。此变更不会删除已有缓存、导出数据或历史 notebook。

## 移除范围与替代边界

| 已移除入口 | 原职责 | 迁移方式 |
| --- | --- | --- |
| `df` / `DataFramePlugin` | 单记录特征转表、按时间排序、可选增益换算 | 读取 `basic_features`，显式转表、排序和标定 |
| `df_events` / `GroupedEventsPlugin` | 按时间窗口组织多通道符合记录 | 没有等价的内置替代；按原分析定义迁移分组逻辑 |
| `df_paired` / `PairedEventsPlugin` | 对旧符合分组筛选并展开通道列 | 没有等价的内置替代；明确筛选与输出粒度后单独实现 |
| `plugins_tabular()` / `tabular` | 注册上述三个插件 | 从 profile/自定义注册代码中删除该集合 |
| `events_df`、`events_grouped` 等旧别名 | 访问旧表格链路 | 按原含义迁移，不再使用别名 |

上述插件类不再从 `waveform_analysis.plugins`、旧 `core.plugins`、`builtin` 或 CPU 兼容入口导出；
对应插件 bundle 和 `cpu.dataframe` / `cpu.event_analysis` 兼容模块也已移除。
普通 pandas、DataFrame 存储和查询，以及独立的 `EventAnalyzer` 分析能力仍保留。

`peaks` 每行代表一个重建峰。`s1_s2_pairs` 保留通过完整性和配置筛选的候选配对，
由 `selected` 标记最终选择；统计选中配对时需显式筛选 `pairs[pairs["selected"]]`。
两者的输入、匹配规则与行粒度均不同于旧多通道符合表，不能通过更换产物名保持原结果。
迁移符合分析时应对照原通道选择、时间窗口、时间单位、重复匹配与筛选规则验证。

## 单记录特征转表与排序

```python
import pandas as pd

from waveform_analysis import Context
from waveform_analysis.plugins import BasicFeaturesPlugin, plugins_io, plugins_waveform

run_id = "run_001"  # 替换为真实 run
ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*plugins_io(), *plugins_waveform(), BasicFeaturesPlugin())
features = ctx.get_data(run_id, "basic_features")
df = pd.DataFrame(features)

# 原 df 插件按 timestamp 排序；转换为 DataFrame 本身不会增加排序步骤。
df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
```

`basic_features` 包含 `record_id`、`board`、`channel`、`timestamp`、`height`、`amp`、
`area` 和 `max_abs_diff`。每行对应一条记录；`timestamp` 使用标准链路的 ps 单位。
硬件通道使用 `(board, channel)` 唯一标识；不要只按 channel 合并不同板卡。
保留 `record_id` 作为关联键，不能依靠排序后的 DataFrame 行号回查波形。
稳定排序为相同时间戳保留输入次序，旧表的同时间戳次序不应作为迁移后的匹配契约。

## SPE 标定在分析层显式进行

`basic_features.area` 是基线校正后的 ADC 采样值之和，未乘采样间隔 `dt`，可记为
ADC·sample；`height` 是 ADC 幅度。面积增益必须来自相同采样、积分窗口与基线约定的
SPE 面积标定，单位为 ADC·sample/PE，才能计算 `area_pe = area / gain`。
若已有标定使用 ADC·ns/PE，应先统一采样间隔与积分约定。

原来的 `df.gain_adc_per_pe` 配置入口已移除，`basic_features` 不会自动增加 PE 列。
可把实测面积增益保存在 run 的 JSON 中，并由分析代码读取：

```json
{
  "calibration": {
    "gain_adc_per_pe": {
      "0:9": 200.0,
      "1:9": 180.0
    }
  }
}
```

以上数值仅为示例。若文件放在 `DAQ/<run_id>/run_config.json`，需显式配置路径：

```python
ctx.set_config({"run_config_path": "{data_root}/{run_id}/run_config.json"})
gain_config = ctx.get_run_config(run_id)["calibration"]["gain_adc_per_pe"]
```

按每行的 board/channel 对齐增益后再换算：

```python
import numpy as np

from waveform_analysis.core.hardware import (
    get_gain_adc_per_pe,
    resolve_channel_value_map,
    unique_hardware_channels,
)

if any(not np.isfinite(value) or value <= 0 for value in gain_config.values()):
    raise ValueError("SPE 面积增益必须为有限的正数")
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
```

未配置增益的通道得到 `NaN`，不能作为零 PE。`height` 保留 ADC 单位；若需要峰高标定，
必须使用单独测得的峰高增益，不能拿面积增益同时生成 `height_pe`。
这些派生列不属于插件缓存，修改增益后需要重新生成分析表和导出文件。

仓库内可参考 [无需 DAQ 的标定演示](../../examples/demo_spe_gain_config.py)、
[run 配置与显式增益集成](../../examples/gain_integration_guide.py) 和
[批量增益配置工具](../../examples/set_gain_batch.py)。后者只合并所选通道的 JSON 标定，
保留 run 身份、hardware 信息及其他通道配置。

## CLI 必须指定输出目标

普通处理不再默认请求 `df_paired`，也不会自动猜测替代目标：

```bash
waveform-process --run-name run_001 --target basic_features --verbose
waveform-process --run-name run_001 --target peaks --output outputs/run_001_peaks.parquet
```

CLI 只导出由标量字段组成的一维结构化数组；波形池、嵌套数组和对象字段不在表导出范围内。
默认文件名为 `outputs/<run_name>_<target>.csv`。导出保留产物行顺序，不自动排序或换算 PE。
需要排序、校准或自定义符合分析时，使用上面的 Python 分析流程。
DAQ 扫描、DAQ 信息显示及配置查看不要求 `--target`，详见 [CLI 指南](../cli/WAVEFORM_PROCESS.md)。

## 既有数据与历史复现

本次代码退役不清理已有缓存、CSV/Parquet、原始 DAQ 数据或历史 notebook。
新版本的 `Context` 会拒绝旧产物名，不会因为旧缓存仍存在而恢复旧插件语义。

保留旧分析结果及其代码版本、配置、依赖环境和标定记录。需要复现旧链路时，在旧版本的
独立 checkout/环境中运行；迁移后的分析使用独立输出文件，并按记录、符合组或配对粒度
分别比较结果。不要先删除旧结果再判断迁移是否等价。
