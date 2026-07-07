# s1_s2_pair_candidates (S1S2PairCandidatesPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `s1_s2_pair_candidates` |
| Depends On | `peak_classification`, `peaks` |
| Output Kind | `structured_array` |
| Version | `0.1.3` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates` |
| Accelerator | `cpu` |

## Source Notes

S1-S2 配对候选生成插件。

这个插件只负责“生成候选”，不负责“选择最终配对”。
它先把 `peak_classification` 的结果拆成 S1 和 S2，然后以 S2 为 anchor，
在漂移时间窗口内向前搜索所有物理上允许的 S1 候选。

为什么这样设计：
- S2 通常对应漂移后的电离信号，时间更靠后，适合作为锚点
- 以 S2 为中心向前找 S1，可以直接把因果约束写成时间窗口
- 候选生成和候选选择分层后，后续可以独立调分数、歧义规则和质量筛选

核心原理：
- 先按 `peak_id -> label` 建表，只接受 `LABEL_S1` 和 `LABEL_S2`
- `LABEL_UNKNOWN` 和 `LABEL_S1_S2` 不参与配对
- 对每个 S2，只在 `[t_S2 - max_drift_time, t_S2 - min_drift_time]` 内找 S1
- 用时间有序数组 + 二分搜索，把候选筛选从全扫描降到局部搜索
- 只记录候选对、观测量、排名和歧义标志，不做最终裁决

输出字段分成几类：
- Identity: `pair_id`、`s1_peak_id`、`s2_peak_id`、索引字段
- Timing: `s1_time`、`s2_time`、`drift_time`、`drift_time_ns`
- Observables: `s1_area`、`s2_area`、`log10_s2_s1`、宽度、通道数
- Score: 预留给第二层插件打分使用
- Ranking: 记录某个候选在局部竞争中的排序和歧义程度
- Flags: 标记时间边界、孤立信号、多候选冲突等情况

计算方式：
- `drift_time = t_S2 - t_S1`
- `drift_time_ns = drift_time / 1000`
- `s1_width` 和 `s2_width` 直接沿用 `peaks.width`，单位为 ns
- 候选时间窗口为 `[t_S2 - max_drift_time, t_S2 - min_drift_time]`
- `log10_s2_s1 = log10(s2_area / s1_area)`，若 `s1_area <= 0` 则记为 `0.0`
- `score_*` 字段在这一层不计算，统一置零，留给后续插件补充分数
- `rank_for_s1` 和 `rank_for_s2` 由后续排序步骤填充；当前阶段只统计局部候选数
- `FLAG_MULTI_S1_CANDIDATE` 和 `FLAG_MULTI_S2_CANDIDATE` 表示同一事件存在多个竞争配对
- 孤立信号的 `pair_id = -1`，对应缺失端的 id、index、time、drift 字段都用 `-1` 或 `0`

默认约束：
- `t_S2 > t_S1`
- `min_drift_time <= t_S2 - t_S1 <= max_drift_time`
- 可选最小面积阈值用于清理噪声候选

这一步的输出是“候选表”，后续插件可以基于分数、歧义和质量标志，
再从这些候选里选出最终的 S1-S2 配对。

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
| `rank_for_s1` | `int32` | - |
| `rank_for_s2` | `int32` | - |
| `n_s1_candidates_for_s2` | `int32` | - |
| `n_s2_candidates_for_s1` | `int32` | - |
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
