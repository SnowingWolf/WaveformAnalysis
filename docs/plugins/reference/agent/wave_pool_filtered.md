# wave_pool_filtered (WavePoolFilteredPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `wave_pool_filtered` |
| Depends On | `records`, `wave_pool` |
| Output Kind | `array` |
| Version | `3.0.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.records` |
| Accelerator | `cpu` |

## Inputs

- `records`
- `wave_pool`

## Outputs

| Field | DType |
|-------|-------|
| `value` | `float32` |

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
| `max_workers` | `int` | `None` | 并行工作线程数；None 使用 CPU 核心数，1 或 0 禁用并行 |
| `batch_size` | `int` | `0` | 每批次记录数（0 表示不分批，整个通道一次处理） |
| `channel_config` | `dict` | `None` | 按 (board, channel) 的插件通道覆盖配置，可覆盖滤波参数 |

## Execution Path

`wave_pool_filtered` 依赖链入口：
`records -> wave_pool -> wave_pool_filtered`

## Failure Modes

- 依赖数据缺失或字段不匹配，导致 compute 阶段报错
- 配置值类型/范围不合法，触发参数校验异常
- SG/BW 在超短波形上可能回退原始波形，以避免无效窗口或 `padlen` 异常
- 输出 dtype 变更但版本未升级，可能导致缓存命中异常

## Change Playbook

1. 修改 `options`/`output_dtype`/核心算法后同步提升 `version`
2. 保持 `provides` 稳定；若必须变更，更新依赖插件与文档索引
3. 新增/删除输出字段时，同时更新消费方插件和回归测试

## Validation

```bash
# 单插件文档再生成
waveform-docs generate plugins-agent --plugin wave_pool_filtered

# 覆盖率检查
waveform-docs check coverage --strict
```
