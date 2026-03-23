# hit (HitFinderPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `2.3.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.peak_finding` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType |
|-------|-------|
| `position` | `int64` |
| `height` | `float32` |
| `integral` | `float32` |
| `edge_start` | `float32` |
| `edge_end` | `float32` |
| `timestamp` | `int64` |
| `board` | `int16` |
| `channel` | `int16` |
| `event_index` | `int64` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `use_filtered` | `bool` | `True` | 是否使用 filtered_waveforms（默认 True，需要先注册 FilteredWaveformsPlugin） |
| `use_derivative` | `bool` | `True` | 是否使用一阶导数进行峰值检测（True: 检测导数峰值, False: 检测波形峰值） |
| `height` | `float` | `30.0` | 峰值的最小高度阈值 |
| `distance` | `int` | `2` | 峰值之间的最小距离（采样点数） |
| `prominence` | `float` | `0.7` | 峰值的最小显著性（prominence） |
| `width` | `int` | `4` | 峰值的最小宽度（采样点数） |
| `threshold` | `any` | `None` | 峰值的阈值条件（可选） |
| `height_method` | `str` | `minmax` | 峰高计算方法: 'diff' (积分差分) 或 'minmax' (最大最小值差) |
| `height_window_extension` | `int` | `4` | height_method='minmax' 时，峰值窗口左右两侧扩展的采样点数 |
| `sampling_interval_ns` | `float` | `2.0` | 采样间隔（纳秒），用于计算全局时间戳。默认 2.0 ns |
| `parallel` | `bool` | `True` | 是否启用并行峰值检测（按事件分块并行） |
| `n_workers` | `int` | `0` | 并行 worker 数；<=0 表示自动（基于 CPU 核心数） |
| `chunk_size` | `int` | `1024` | 并行分块大小（每个任务处理的事件数） |
| `parallel_min_events` | `int` | `20480` | 触发并行的最小事件数（小数据量时自动串行） |

## Execution Path

`hit` 依赖链入口：
`SOURCE -> hit`

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
waveform-docs generate plugins-agent --plugin hit

# 覆盖率检查
waveform-docs check coverage --strict
```
