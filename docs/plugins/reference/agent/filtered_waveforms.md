# filtered_waveforms (FilteredWaveformsPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `filtered_waveforms` |
| Depends On | `st_waveforms` |
| Output Kind | `structured_array` |
| Version | `2.4.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.filtering` |
| Accelerator | `cpu` |

## Inputs

- `st_waveforms`

## Outputs

| Field | DType |
|-------|-------|
| `baseline` | `float64` |
| `baseline_upstream` | `float64` |
| `timestamp` | `int64` |
| `dt` | `int32` |
| `event_length` | `int32` |
| `board` | `int16` |
| `channel` | `int16` |
| `wave` | `('<i2', (1500,))` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `filter_type` | `str` | `SG` | 滤波器类型: 'BW' 或 'SG' |
| `lowcut` | `float` | `0.1` | BW 低频截止 |
| `highcut` | `float` | `0.5` | BW 高频截止 |
| `fs` | `float` | `0.5` | BW 采样率（GHz） |
| `filter_order` | `int` | `4` | BW 阶数 |
| `sg_window_size` | `int` | `11` | SG 窗口大小（奇数） |
| `sg_poly_order` | `int` | `2` | SG 多项式阶数 |
| `daq_adapter` | `str` | `None` | DAQ 适配器名称（用于自动推断采样率） |
| `max_workers` | `int` | `None` | 并行工作线程数；None 使用 CPU 核心数，1 或 0 禁用并行 |
| `batch_size` | `int` | `0` | 每批次事件数（0 表示不分批，整个通道一次处理） |

## Execution Path

`filtered_waveforms` 依赖链入口：
`st_waveforms -> filtered_waveforms`

## Failure Modes

- 依赖数据缺失或字段不匹配，导致 compute 阶段报错
- 配置值类型/范围不合法，触发参数校验异常
- 输出 dtype 变更但版本未升级，可能导致缓存命中异常

## Change Playbook

1. 修改 `options`/`output_dtype`/核心算法后同步提升 `version`
2. 保持 `provides` 稳定；若必须变更，更新依赖插件与文档索引
3. 新增/删除输出字段时，同时更新消费方插件和回归测试

## Validation

```bash
# 单插件文档再生成
waveform-docs generate plugins-agent --plugin filtered_waveforms

# 覆盖率检查
waveform-docs check coverage --strict
```
