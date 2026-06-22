# peak_classification (PeakClassificationPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `peak_classification` |
| Depends On | `peaks` |
| Output Kind | `structured_array` |
| Version | `1.1.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.peak_classification` |
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
| `conflict_policy` | `str` | `prefer_s1` | 当同时满足 S1 和 S2 条件时的处理策略。- 'prefer_s1': 优先标记为 S1（默认）- 'prefer_s2': 优先标记为 S2- 'unknown': 标记为 Unknown- 'mark_as_s1_s2': 标记为 S1_S2（混合信号） |
| `default_label` | `str` | `unknown` | 当不满足任何配置条件时的默认标签。默认 'unknown'（推荐用于灵活分类）。 |
| `strict` | `bool` | `False` | 如果为 True，至少需要配置一个 S1 或 S2 的判断条件。 |
| `s1_selection` | `dict` | `None` | S1 分类配置。字典包含：- 'accept_any': 列表，每个元素是一个条件组（字典），满足任一组即为 S1 候选- 'reject_any': 列表，每个元素是一个条件组（字典），满足任一组即排除示例: {'accept_any': [{'width': (0, 100)}, {'area': (0, 500)}], 'reject_any': [{'width': (500, None)}]} |
| `s2_selection` | `dict` | `None` | S2 分类配置，格式同 s1_selection。 |

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
