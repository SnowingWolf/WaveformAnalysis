# Plugin Set & Profile 指南

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [插件功能](README.md) > Plugin Set & Profile

本指南说明如何使用 **Plugin Set** 与 **Profile** 组合插件，形成可维护的处理链路。[^source]

---

## Plugin Sets

Plugin Set 是最小可复用插件组，每个 set 只关注单一职责。

| Set | 插件 | 说明 |
| --- | --- | --- |
| `io` | RawFileNamesPlugin | 扫描并分组原始文件 |
| `waveform` | WaveformsPlugin, FilteredWaveformsPlugin | 波形提取与滤波 |
| `basic_features` | HitFinderPlugin, BasicFeaturesPlugin | 基础特征计算 |
| `tabular` | DataFramePlugin | 表格化输出 |
| `events` | GroupedEventsPlugin, PairedEventsPlugin | 事件分组与配对 |
| `signal_processing` | SignalPeaksPlugin, WaveformWidthPlugin, WaveformWidthIntegralPlugin | 可选信号处理扩展 |
| `diagnostics_legacy` | CacheAnalysisPlugin, RecordsPlugin, EventsPlugin, EventFramePlugin, EventsGroupedPlugin | 诊断/兼容插件 |

示例：

```python
from waveform_analysis.core.plugins.plugin_sets import plugins_io, plugins_waveform

io_plugins = plugins_io()
waveform_plugins = plugins_waveform()
```

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
io + waveform + basic_features + tabular + events
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
