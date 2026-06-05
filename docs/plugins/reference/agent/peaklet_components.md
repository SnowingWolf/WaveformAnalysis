# peaklet_components (PeakletComponentsPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `peaklet_components` |
| Depends On | `peaklets`, `hit_merged` |
| Output Kind | `structured_array` |
| Version | `1.0.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.peaklets` |
| Accelerator | `cpu` |

## Inputs

- `peaklets`
- `hit_merged`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `peaklet_index` | `int64` | - |
| `merged_index` | `int64` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `time_window_ns` | `float` | `100.0` | 跨通道 peaklet 合并时间窗口 |
| `max_total_width_ns` | `float` | `10000.0` | peaklet 最大总宽度 |
| `dt` | `int` | `None` | 保留兼容配置；优先使用输入 hit_merged 的 dt |

## Execution Path

`peaklet_components` 依赖链入口：
`peaklets -> hit_merged -> peaklet_components`

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
waveform-docs generate plugins-agent --plugin peaklet_components

# 覆盖率检查
waveform-docs check coverage --strict
```
