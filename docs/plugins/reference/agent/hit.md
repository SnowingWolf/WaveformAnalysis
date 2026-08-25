---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "hit"
plugin_class: "HitFinderPlugin"
module: "waveform_analysis.core.plugins.builtin.hit.plugin"
version: "3.0.0"
summary: "Detect peaks in waveforms and extract peak features."
depends_on: []
declared_depends_on: []
resolved_depends_on: ["records", "wave_pool"]
dependency_profile: "documentation-default-v1"
dependency_profile_values: {"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}
dependency_config_keys: ["use_filtered", "wave_source"]
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "90424264df7f1c8b2a1785b15805e9af0b6cb14270e90be56053e1075d86e0af"
generated: true
---
# hit

## Overview

Detect peaks in waveforms and extract peak features.
峰值检测插件 - 基于波形检测峰值并计算峰值特征。

使用 scipy.signal.find_peaks 进行峰值检测，支持多种峰值筛选条件。 计算峰值的位置、高度、积分、边缘等特征。

注意：此插件是当前唯一官方 Hit 检测接口（provides="hit"）。

配置示例： >>> ctx.set_config({ ... 'dt': 2, ... 'use_filtered': True, # 使用滤波后的波形 ... }, plugin_name='hit')

| Item | Value |
| --- | --- |
| Provides | `hit` |
| Plugin Class | `HitFinderPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit.plugin` |
| Version | `3.0.0` |
| Category | 特征提取 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `90424264df7f1c8b2a1785b15805e9af0b6cb14270e90be56053e1075d86e0af` |

### Dependencies

默认文档画像：`documentation-default-v1`（{"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}）。
该插件通过 `resolve_depends_on(context, run_id)` 动态解析依赖；可能影响解析的配置键：`use_filtered`, `wave_source`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | dynamic-default | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | dynamic-default | - | Build wave_pool from the shared internal records bundle. |
### How It Works

1. 从波形中检测峰值
2. 使用配置的参数检测每个事件中的峰值，计算峰值特征 （位置、高度、积分、边缘等）。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `use_filtered` | `bool` | `True` | - | yes | no | 是否使用 filtered_waveforms（默认 True，需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | - | yes | no | 波形数据源: auto\|records\|st_waveforms\|filtered_waveforms |
| `use_derivative` | `bool` | `True` | - | yes | no | 是否使用一阶导数进行峰值检测（True: 检测导数峰值, False: 检测波形峰值） |
| `height` | `float` | `30.0` | - | yes | no | 峰值的最小高度阈值 |
| `distance` | `int` | `2` | - | yes | no | 峰值之间的最小距离（采样点数） |
| `prominence` | `float` | `0.7` | - | yes | no | 峰值的最小显著性（prominence） |
| `width` | `int` | `4` | - | yes | no | 峰值的最小宽度（采样点数） |
| `threshold` | `any` | `None` | - | yes | no | 峰值的阈值条件（可选） |
| `height_method` | `str` | `minmax` | - | yes | no | 峰高计算方法: 'diff' (积分差分) 或 'minmax' (最大最小值差) |
| `height_window_extension` | `int` | `4` | - | yes | no | height_method='minmax' 时，峰值窗口左右两侧扩展的采样点数 |
| `dt` | `int` | `None` | - | yes | no | 采样间隔（ns）。仅在输入数据缺少 dt 字段时作为兼容补充。 |
| `parallel` | `bool` | `True` | - | yes | no | 是否启用并行峰值检测（按事件分块并行） |
| `n_workers` | `int` | `0` | - | yes | no | 并行 worker 数；<=0 表示自动（基于 CPU 核心数） |
| `chunk_size` | `int` | `1024` | - | yes | no | 并行分块大小（每个任务处理的事件数） |
| `parallel_min_events` | `int` | `20480` | - | yes | no | 触发并行的最小事件数（小数据量时自动串行） |
## Output

structured_array output with fields: position, height, integral, edge_start, edge_end, dt, timestamp, board, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `position` | `int64` | samples | Peak position as sample index within the waveform |
| `height` | `float32` | ADC counts | Peak height above baseline |
| `integral` | `float32` | ADC counts | Peak integral (area) |
| `edge_start` | `float32` | samples | Peak left edge boundary |
| `edge_end` | `float32` | samples | Peak right edge boundary |
| `dt` | `int32` | ns | Sample interval in nanoseconds |
| `timestamp` | `int64` | ps | Global timestamp in picoseconds |
| `board` | `int16` | None | Hardware board index |
| `channel` | `int16` | None | Physical channel number |
| `record_id` | `int64` | None | Source record identifier |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "hit")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- Hit bundle - provides 'hit' (HitFinderPlugin)。
- 使用 scipy.signal.find_peaks 进行峰值检测，支持多种峰值筛选条件。 计算峰值的位置、高度、积分、边缘等特征。
### Failure Modes

- `hit` 的实际输入由 `resolve_depends_on(context, run_id)` 决定；默认画像之外的配置需要重新确认依赖是否可用。
- 动态依赖无法解析、所需配置不合法或上游产物缺失时，插件不会生成有效输出。
### Downstream Impact

直接消费者：`waveform_width`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin hit
waveform-docs check coverage --strict --fail-on-warning
```
