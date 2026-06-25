# s1_s2_pair_candidates (S1S2PairCandidatesPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `s1_s2_pair_candidates` |
| Depends On | `peak_classification`, `peaks` |
| Output Kind | `structured_array` |
| Version | `0.1.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates` |
| Accelerator | `cpu` |

## Inputs

- `peak_classification`
- `peaks`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `pair_id` | `int64` | - |
| `s1_peak_id` | `int64` | - |
| `s2_peak_id` | `int64` | - |
| `s1_index` | `int32` | - |
| `s2_index` | `int32` | - |
| `s1_time` | `int64` | - |
| `s2_time` | `int64` | - |
| `drift_time` | `int64` | - |
| `drift_time_ns` | `float32` | - |
| `s1_area` | `float32` | - |
| `s2_area` | `float32` | - |
| `log10_s2_s1` | `float32` | - |
| `s1_width` | `float32` | - |
| `s2_width` | `float32` | - |
| `s1_n_channels` | `int16` | - |
| `s2_n_channels` | `int16` | - |
| `score_total` | `float32` | - |
| `score_time` | `float32` | - |
| `score_s1_quality` | `float32` | - |
| `score_s2_quality` | `float32` | - |
| `score_ratio` | `float32` | - |
| `score_pattern` | `float32` | - |
| `score_ambiguity` | `float32` | - |
| `rank_for_s1` | `int16` | - |
| `rank_for_s2` | `int16` | - |
| `n_s1_candidates_for_s2` | `int16` | - |
| `n_s2_candidates_for_s1` | `int16` | - |
| `delta_score_to_next_best` | `float32` | - |
| `flags` | `uint32` | - |
| `selected` | `bool` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `max_drift_time` | `float` | `50000.0` | 最大漂移时间 (ns). 典型液氙 TPC 约 50 μs |
| `min_drift_time` | `float` | `0.0` | 最小漂移时间 (ns). 用于过滤噪声 |
| `time_field` | `str` | `center_time` | 使用的时间字段 |
| `min_s1_area` | `(<class 'float'>, <class 'NoneType'>)` | `None` | S1 最小面积阈值 (可选) |
| `min_s2_area` | `(<class 'float'>, <class 'NoneType'>)` | `None` | S2 最小面积阈值 (可选) |
| `allow_orphan_s1` | `bool` | `False` | 是否输出孤立 S1 (无 S2 配对) |
| `allow_orphan_s2` | `bool` | `False` | 是否输出孤立 S2 (无 S1 配对) |

## Execution Path

`s1_s2_pair_candidates` 依赖链入口：
`peak_classification -> peaks -> s1_s2_pair_candidates`

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
waveform-docs generate plugins-agent --plugin s1_s2_pair_candidates

# 覆盖率检查
waveform-docs check coverage --strict
```
