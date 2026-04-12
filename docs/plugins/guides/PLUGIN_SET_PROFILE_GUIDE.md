# Plugin Set & Profile 指南

**导航**: [文档中心](../../README.md) > [插件系统](../README.md) > Plugin Set & Profile

本指南说明如何使用 **Plugin Set** 与 **Profile** 组合插件，形成可维护的处理链路。[^source]

> 文档同步说明：本页对应 `waveform_analysis/core/plugins/plugin_sets/*` 与
> `waveform_analysis/core/plugins/profiles.py` 中的 `# DOC` 引用。

---

## Plugin Sets

Plugin Set 是最小可复用插件组，每个 set 只关注单一职责。

| Set | 插件 | 说明 |
| --- | --- | --- |
| `io` | RawFileNamesPlugin | 扫描并分组原始文件 |
| `waveform` | WaveformsPlugin, FilteredWaveformsPlugin, RecordsPlugin | 波形提取、滤波与 records 构建 |
| `basic_features` | BasicFeaturesPlugin, WaveformWidthIntegralPlugin | 基础特征计算 |
| `tabular` | DataFramePlugin | 表格化输出 |
| `events` | GroupedEventsPlugin, PairedEventsPlugin | 事件分组与配对 |
| `peaks` | HitFinderPlugin, ThresholdHitPlugin, HitMergeClustersPlugin, HitMergePlugin, HitMergedComponentsPlugin, WaveformWidthPlugin, S1S2ClassifierPlugin | 峰值检测与峰特征扩展 |

示例：

```python
from waveform_analysis.core.plugins.plugin_sets import plugins_io, plugins_waveform

io_plugins = plugins_io()
waveform_plugins = plugins_waveform()
```

`plugins_waveform()` 已包含 `RecordsPlugin` 与 `WavePoolPlugin`，注册后可直接使用
`records_view`：

```python
from waveform_analysis.core.data import records_view
from waveform_analysis.core.plugins.plugin_sets import plugins_io, plugins_waveform

ctx.register(*plugins_io(), *plugins_waveform())
rv = records_view(ctx, run_id)
```

注意：`records_view(...)` 现在要求正式 `records + wave_pool` 产物同时可用，不会再
fallback 到内部 `RecordsBundle`。

其中 `rv.waves(record_id, ...)` 返回指定 `record_id` 的原始波形，`rv.signals(record_id, ...)`
返回做过 baseline 校正且按 `records.polarity` 统一为负极性的信号。批量访问同样使用
`rv.waves([record_id, ...], pad_to=..., mask=True)` / `rv.signals([record_id, ...], ...)`。

---

## Profiles

Profile 是对多个 Plugin Set 的组合，代表一条可执行 pipeline。

### CPU 默认 Profile

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context()
ctx.register(*profiles.cpu_default())
```

`cpu_default()` 等价于：

```
io + waveform + peaks + basic_features + tabular + events
```

---

## Profile 选择

CLI 可通过 `--profile` 选择执行链路：

```bash
waveform-process --run-name run_001 --profile cpu
```

目前 `streaming` 与 `jax` 仍为占位 Profile，会提示未实现。

---

## 兼容 standard_plugins

历史用法仍可使用：

```python
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins
ctx.register(*standard_plugins)
```

推荐新代码使用 `profiles.cpu_default()`，便于后续扩展。

[^source]: 来源：`waveform_analysis/core/plugins/plugin_sets/`、`waveform_analysis/core/plugins/profiles.py`、`waveform_analysis/cli.py`。
