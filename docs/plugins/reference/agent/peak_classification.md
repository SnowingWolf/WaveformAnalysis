# peak_classification (PeakClassificationPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `peak_classification` |
| Depends On | `peaks` |
| Output Kind | `structured_array` |
| Version | `1.2.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.peak_classification` |
| Accelerator | `cpu` |

## Source Notes

从 peaklet 特征进行 S1/S2 分类。

该插件基于 peaks 的多维特征进行信号类型甄别。

默认分类规则（基于 n_hits 和 rise_time_10_50）：
┌─────────────┬──────────────────┬──────────┬────────────────────────────────┐
│ n_hits      │ rise_time_10_50  │ 分类结果 │ 说明                           │
├─────────────┼──────────────────┼──────────┼────────────────────────────────┤
│ < 8         │ 任意             │ S1       │ 少量 hits（单通道或少量通道）  │
│ >= 8        │ <= 100 ns        │ S1       │ 多 hits 但快速上升（类 S1）    │
│ >= 8        │ > 100 ns         │ S2       │ 多 hits 且慢速上升（典型 S2）  │
└─────────────┴──────────────────┴──────────┴────────────────────────────────┘

物理意义：
- n_hits < 8: 信号集中在少量通道，典型的 S1 直接闪烁特征
- n_hits >= 8 且 rise_time_10_50 <= 100 ns: 多通道但快速上升，可能是强 S1
- n_hits >= 8 且 rise_time_10_50 > 100 ns: 多通道且慢速上升，典型 S2 电子漂移信号

分类标签：
- 0: Unknown（未知类型）
- 1: S1（闪烁信号）
- 2: S2（电离信号）
- 3: S1_S2（混合信号或分类冲突）

## Inputs

- `peaks`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `peak_id` | `int64` | - |
| `label` | `int8` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `priority_order` | `list` | `['s1_s2', 's1', 's2']` | 分类优先级顺序（列表），从高到低。例如: ['s1_s2', 's1', 's2'] 表示先判定 s1_s2，再判定 s1，最后判定 s2。可用值: 's1', 's2', 's1_s2' |
| `default_label` | `str` | `unknown` | 当不满足任何配置条件时的默认标签。默认 'unknown'（推荐用于灵活分类）。 |
| `strict` | `bool` | `False` | 如果为 True，至少需要配置一个 S1 或 S2 的判断条件。 |
| `s1_selection` | `dict` | `None` | S1 分类配置。字典包含：- 'accept_any': 列表，每个元素是一个条件组（字典），满足任一组即为 S1 候选- 'reject_any': 列表，每个元素是一个条件组（字典），满足任一组即排除示例: {'accept_any': [{'width': (0, 100)}, {'area': (0, 500)}], 'reject_any': [{'width': (500, None)}]} |
| `s2_selection` | `dict` | `None` | S2 分类配置，格式同 s1_selection。 |
| `s1_s2_selection` | `dict` | `None` | S1_S2 分类配置，格式同 s1_selection。命中后优先标记为 S1_S2。 |

## Execution Path

`peak_classification` 依赖链入口：
`peaks -> peak_classification`

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
waveform-docs generate plugins-agent --plugin peak_classification

# 覆盖率检查
waveform-docs check coverage --strict
```
