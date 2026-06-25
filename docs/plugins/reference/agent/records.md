# records (RecordsPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `records` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `0.13.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.records` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `timestamp` | `int64` | - |
| `pid` | `int32` | - |
| `board` | `int16` | - |
| `channel` | `int16` | - |
| `baseline` | `float64` | - |
| `baseline_upstream` | `float64` | - |
| `polarity` | `<U8` | - |
| `record_id` | `int64` | - |
| `dt` | `int32` | - |
| `trigger_type` | `int16` | - |
| `flags` | `uint32` | - |
| `wave_offset` | `int64` | - |
| `event_length` | `int32` | - |
| `time` | `int64` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `daq_adapter` | `str` | `vx2730` | DAQ adapter name for records bundle (e.g., 'vx2730', 'v1725'). |
| `channel_workers` | `any` | `16` | Workers for channel-level waveform loading. |
| `channel_executor` | `str` | `process` | Executor type for channel-level loading and records merge: 'thread' or 'process'. |
| `n_jobs` | `int` | `16` | Workers per channel for file-level parsing; V1725 None=auto caps file readers at 4. |
| `use_process_pool` | `bool` | `True` | Use a process pool for file-level parsing (False=thread pool). |
| `chunksize` | `int` | `None` | CSV read chunk size; None reads full file (PyArrow if available). |
| `parse_engine` | `str` | `auto` | CSV engine: auto | polars | pyarrow | pandas |
| `records_part_size` | `int` | `250000` | Max events per records shard; <=0 disables sharding. |
| `v1725_part_size` | `int` | `20000` | Max V1725 waves per per-file records shard; <=0 uses one shard per file. |
| `keep_on_disk` | `any` | `True` | Keep merged records bundle disk-backed. None defaults to True for V1725 and False otherwise. |
| `memory_budget_gb` | `float` | `50.0` | Memory budget in GB for in-memory records bundle materialization. |
| `dt` | `int` | `None` | Sample interval in ns for records.dt (defaults to adapter rate or 1ns). |
| `baseline_samples` | `any` | `None` | Baseline range: int (sample count from adapter start) or tuple (start, end) relative to samples_start. JSON lists like [0, 800] are also accepted. None=adapter default. |

## Execution Path

`records` 依赖链入口：
`SOURCE -> records`

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
waveform-docs generate plugins-agent --plugin records

# 覆盖率检查
waveform-docs check coverage --strict
```
