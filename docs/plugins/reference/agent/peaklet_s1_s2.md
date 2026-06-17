# peaklet_s1_s2 (PeakletS1S2ClassifierPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `peaklet_s1_s2` |
| Depends On | `peaks` |
| Output Kind | `structured_array` |
| Version | `1.0.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.peaklet_s1_s2_classifier` |
| Accelerator | `cpu` |

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
| `s1_ranges` | `dict` | `None` | S1 特征范围字典。键为特征名，值为 (min, max) 元组。例如: {'width': (0, 100), 'area': (0, 500), 'n_hits': (1, 10)}。默认 None 时，使用默认分类规则：凡不满足 S2 条件的都判为 S1。 |
| `s2_ranges` | `dict` | `{'n_hits': (8, None), 'rise_time_10_50': (100.01, None)}` | S2 特征范围字典。键为特征名，值为 (min, max) 元组。例如: {'width': (300, None), 'area': (1000, None), 'n_hits': (8, None)}。默认: {'n_hits': (8, None), 'rise_time_10_50': (100.01, None)} - 即 n_hits >= 8 且 rise_time_10_50 > 100 ns 判定为 S2。None 表示不配置 S2 判断条件。 |
| `conflict_policy` | `str` | `prefer_s1` | 当同时满足 S1 和 S2 条件时的处理策略。默认 prefer_s1。 |
| `default_label` | `str` | `s1` | 当不满足任何配置条件时的默认标签。默认 's1' - 即凡不满足 S2 条件的都判为 S1（适用于默认配置）。 |
| `strict` | `bool` | `False` | 如果为 True，至少需要配置一个 S1 或 S2 的判断条件。 |

## Execution Path

`peaklet_s1_s2` 依赖链入口：
`peaks -> peaklet_s1_s2`

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
waveform-docs generate plugins-agent --plugin peaklet_s1_s2

# 覆盖率检查
waveform-docs check coverage --strict
```
