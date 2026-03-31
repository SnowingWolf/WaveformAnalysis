# st_waveforms (WaveformsPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `st_waveforms` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `0.9.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.waveforms` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType |
|-------|-------|
| `baseline` | `float64` |
| `baseline_upstream` | `float64` |
| `polarity` | `<U8` |
| `timestamp` | `int64` |
| `record_id` | `int64` |
| `dt` | `int32` |
| `event_length` | `int32` |
| `board` | `int16` |
| `channel` | `int16` |
| `wave` | `('<i2', (1500,))` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `daq_adapter` | `str` | `vx2730` | DAQ adapter name (e.g., 'vx2730') |
| `wave_length` | `int` | `None` | Waveform length (number of sampling points). Automatically detect from the data when None。 |
| `dt` | `int` | `None` | Sampling interval in ns for st_waveforms.dt (None=auto from adapter). |
| `n_jobs` | `int` | `None` | Number of parallel workers for file-level processing (None=auto, uses min(total_files, 50)) |
| `use_process_pool` | `bool` | `False` | Whether to use process pool for file-level parallelism (False=thread pool for I/O, True=process pool for CPU-intensive) |
| `chunksize` | `int` | `None` | Chunk size for CSV reading (None=read entire file, enables PyArrow; set value to enable chunked reading but disables PyArrow) |
| `parse_engine` | `str` | `auto` | CSV engine: auto | polars | pyarrow | pandas |
| `use_upstream_baseline` | `bool` | `False` | Whether to use baseline from upstream plugin (requires 'baseline' data). |
| `baseline_samples` | `any` | `None` | Baseline range: int (sample count from adapter start) or tuple (start, end) relative to samples_start. JSON lists like [0, 800] are also accepted. None=adapter default. |
| `streaming_mode` | `bool` | `False` | Enable streaming mode: read files and structure waveforms incrementally to reduce memory usage. When enabled, uses memmap for output to avoid full vstack memory overhead. |

## Execution Path

`st_waveforms` 依赖链入口：
`SOURCE -> st_waveforms`

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
waveform-docs generate plugins-agent --plugin st_waveforms

# 覆盖率检查
waveform-docs check coverage --strict
```
