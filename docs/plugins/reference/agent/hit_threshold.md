# hit_threshold (ThresholdHitPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_threshold` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `1.2.0` |
| Module | `waveform_analysis.core.plugins.builtin.hit.hit_finder` |
| Accelerator | `cpu` |

## Source Notes

Hit Finder Plugins - 阈值 Hit 检测插件

本模块包含：
1. HitFinderPlugin: 旧导入路径兼容别名（推荐改为 peak_finding.HitFinderPlugin）
2. ThresholdHitPlugin: 新的纯阈值 hit 插件（provides='hit_threshold'），输出 THRESHOLD_HIT_DTYPE

本版本的主要改动
----------------
1. records 输入路径优先使用 ragged layout：wave_pool + wave_offset + event_length。
2. 对每条 record 先做 min/max record-level prefilter：
   - positive polarity: max(wave) >= baseline + threshold
   - negative polarity: min(wave) <= baseline - threshold
   未通过预筛选的 record 不构造 mask、不找 hit 区间。
3. records 路径不再强制调用 rv.waves(...) 生成 padded 2D matrix，适合不等长波形。
4. waveform matrix 输入路径仍然保留，用于 st_waveforms / filtered_waveforms 等固定窗口数据。

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `position` | `int64` | - |
| `edge_start` | `int32` | - |
| `edge_end` | `int32` | - |
| `width` | `float32` | - |
| `dt` | `int32` | - |
| `timestamp` | `int64` | - |
| `board` | `int16` | - |
| `channel` | `int16` | - |
| `record_id` | `int64` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `threshold` | `float` | `10.0` | Hit 检测阈值 |
| `use_filtered` | `bool` | `False` | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | 波形数据源: auto|records|st_waveforms|filtered_waveforms |
| `left_extension` | `int` | `2` | Hit 左侧扩展点数 |
| `right_extension` | `int` | `2` | Hit 右侧扩展点数 |
| `dt` | `int` | `None` | 采样间隔（ns）。仅在输入数据缺少 dt 字段时作为兼容补充。 |
| `channel_config` | `dict` | `None` | 按 (board, channel) 的插件通道覆盖配置，可覆盖 threshold。 |
| `backend` | `str` | `auto` | Hit finding backend: auto|numba|ragged。auto 对 records 在达到 parallel_min_records 后尝试 numba，否则使用 ragged。 |
| `chunk_parallel` | `bool` | `True` | 是否对 records ragged numba 后端启用 chunk 级线程并行。 |
| `n_workers` | `int` | `0` | records ragged chunk 并行 worker 数；<=0 表示自动。 |
| `parallel_chunk_size` | `int` | `50000` | records ragged chunk 并行大小（每个任务处理的 record 数）。 |
| `parallel_min_records` | `int` | `50000` | 触发 records ragged chunk 并行的最小 record 数。 |
| `streaming_chunk_size` | `int` | `10000` | 流式处理时的 chunk 大小（仅对 RecordsBundleRef 生效） |
| `asymmetry_cut_enabled` | `bool` | `True` | 是否在 records 路径的 hit 查找前应用 records_asymmetry_mask。 |
| `channel_role_cut_enabled` | `bool` | `False` | 是否在 records 路径的 hit 查找前应用 records_detector_mask。 |

## Execution Path

`hit_threshold` 依赖链入口：
`SOURCE -> hit_threshold`

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
waveform-docs generate plugins-agent --plugin hit_threshold

# 覆盖率检查
waveform-docs check coverage --strict
```
