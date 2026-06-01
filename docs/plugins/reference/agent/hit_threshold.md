# hit_threshold (ThresholdHitPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_threshold` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `0.11.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.hit_finder` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType |
|-------|-------|
| `position` | `int64` |
| `height` | `float32` |
| `integral` | `float32` |
| `edge_start` | `int32` |
| `edge_end` | `int32` |
| `width` | `float32` |
| `dt` | `int32` |
| `rise_time` | `float32` |
| `fall_time` | `float32` |
| `timestamp` | `int64` |
| `board` | `int16` |
| `channel` | `int16` |
| `record_id` | `int64` |

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
| `streaming_chunk_size` | `int` | `100000` | 流式处理时的 chunk 大小（仅对 RecordsBundleRef 生效） |

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

## 内存优化与处理模式

`hit_threshold` 插件根据输入数据类型和大小自动选择最优处理模式，以平衡内存占用和处理速度。

### 三种处理模式

| 模式 | 触发条件 | 内存占用 | 处理速度 | 适用场景 |
|------|---------|---------|---------|---------|
| **直接模式** | RecordsBundle 且记录数 ≤ `streaming_chunk_size` | 全部数据 | 最快（基准） | 小数据集（< 100k records） |
| **批处理模式** | RecordsBundle 且记录数 > `streaming_chunk_size` | ~200MB (chunk_size=100k) | -2~5% | 中等数据集（100k-1M records） |
| **流式模式** | RecordsBundleRef（磁盘分片） | ~200MB (chunk_size=100k) | -5~10% | 大数据集（2TB+, 1M+ records） |

### 自动模式切换示例

```python
from waveform_analysis.core.processing import build_records_from_v1725_files

# 小数据集：自动使用直接模式
small_bundle = build_records_from_v1725_files(
    file_paths=small_file_list,  # < 100k records
    dt_ns=2,
    keep_on_disk=False,  # 返回 RecordsBundle
)
# → 直接模式：一次性加载所有波形，速度最快

# 中等数据集：自动使用批处理模式
medium_bundle = build_records_from_v1725_files(
    file_paths=medium_file_list,  # 100k-1M records
    dt_ns=2,
    keep_on_disk=False,  # 返回 RecordsBundle
)
# → 批处理模式：分批加载波形，降低内存峰值

# 大数据集：自动使用流式模式
large_bundle_ref = build_records_from_v1725_files(
    file_paths=large_file_list,  # 2TB+, 1M+ records
    dt_ns=2,
    keep_on_disk=True,  # 返回 RecordsBundleRef（磁盘分片）
)
# → 流式模式：逐分片处理，内存占用 < 200MB

# hit_threshold 自动检测并选择最优模式
ctx.register_plugin(ThresholdHitPlugin())
hits = ctx.get_data(run_id, "hit_threshold")
```

### 配置批处理/流式处理

```python
ctx.config["hit_threshold"] = {
    "threshold": 10.0,
    "streaming_chunk_size": 50_000,  # 降低内存占用（默认 100k）
}
```

**注意**：
- `streaming_chunk_size` 同时控制批处理模式和流式模式的 chunk 大小
- 降低 chunk_size 可减少内存占用，但会略微降低处理速度
- 推荐值：50k-200k（根据可用内存调整）

### 适用场景

| 场景 | 推荐模式 | 配置建议 |
|------|---------|---------|
| 小规模实验（< 100k records） | 直接模式 | 默认配置即可 |
| 中等规模分析（100k-1M records） | 批处理模式 | 默认配置或调整 chunk_size |
| 大规模生产（2TB+, 1M+ records） | 流式模式 | `keep_on_disk=True` + 调整 chunk_size |
| 内存受限环境（< 64GB RAM） | 批处理/流式模式 | 降低 chunk_size 到 50k |
| st_waveforms 数据源 | 直接模式 | 不支持流式处理 |
