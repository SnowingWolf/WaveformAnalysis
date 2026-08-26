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
source_fingerprint: "dd7053d07ac26babebe513caebb58353b35e6f3aa323b2eface58f60e9b01482"
generated: true
---
# hit

## Overview

Detect peaks in waveforms and extract peak features.
HitFinderPlugin 是当前官方的静态峰值检测接口（provides='hit'），从波形中检测峰值并输出位置、高度、积分、边缘、时间戳、板卡、通道和 record_id 等特征。它使用`scipy.signal.find_peaks`，可在滤波波形或其他已解析波形源上工作。

旧版信号处理教程中的 `SignalPeaksPlugin` 已由本插件替代；兼容导入仍可从`waveform_analysis.core.plugins.builtin.cpu` 获取 `HitFinderPlugin`，但数据产物名称应统一使用`hit`。

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
| Source Fingerprint | `dd7053d07ac26babebe513caebb58353b35e6f3aa323b2eface58f60e9b01482` |

### Dependencies

默认文档画像：`documentation-default-v1`（{"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}）。
该插件通过 `resolve_depends_on(context, run_id)` 动态解析依赖；可能影响解析的配置键：`use_filtered`, `wave_source`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | dynamic-default | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | dynamic-default | - | Build wave_pool from the shared internal records bundle. |
### How It Works

1. 解析波形来源：依据 `use_filtered` 与 `wave_source` 动态选择 `records`/`wave_pool` 或 `st_waveforms`/`filtered_waveforms`，并读取显式 `run_id` 对应的数据。
2. 准备检测信号：`use_derivative=True` 时检测波形一阶差分的负值，否则使用基线减波形的直接信号。
3. 调用 `scipy.signal.find_peaks`，按 `height`、`distance`、`prominence`、`width` 和可选 `threshold` 筛选候选峰。
4. 按 `height_method` 计算峰高，并将峰位置、左右边缘、采样间隔、绝对时间、board、channel 和 record_id 写入 `HIT_DTYPE`。
5. 小数据量自动串行，大数据量按 `chunk_size` 和 `parallel_min_events` 使用配置的并行策略，最后返回结构化 `hit` 数组。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `use_filtered` | `bool` | `True` | - | yes | no | 是否优先使用 filtered_waveforms；启用时需注册 FilteredWaveformsPlugin。 |
| `wave_source` | `str` | `auto` | - | yes | no | 波形来源：auto、records、st_waveforms 或 filtered_waveforms。 |
| `use_derivative` | `bool` | `True` | - | yes | no | 是否检测一阶导数信号；当前负脉冲数据通常保持 True。 |
| `height` | `float` | `30.0` | - | yes | no | 峰值最小高度阈值。 |
| `distance` | `int` | `2` | - | yes | no | 相邻峰之间的最小采样点距离。 |
| `prominence` | `float` | `0.7` | - | yes | no | 峰值最小显著性。 |
| `width` | `int` | `4` | - | yes | no | 峰值最小宽度，单位为采样点。 |
| `threshold` | `any` | `None` | - | yes | no | 可选的 scipy 峰值阈值条件。 |
| `height_method` | `str` | `minmax` | - | yes | no | diff 或 minmax，分别表示差分积分或窗口最大最小值差。 |
| `height_window_extension` | `int` | `4` | - | yes | no | minmax 模式下向峰窗口两侧扩展的采样点数。 |
| `dt` | `int` | `None` | - | yes | no | 输入缺少 dt 时的兼容采样间隔，单位为 ns。 |
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
ctx.set_config(
    {
        "use_derivative": True,
        "height": 30.0,
        "distance": 2,
        "prominence": 0.7,
        "width": 4,
        "height_method": "minmax",
    },
    plugin_name="hit",
)
hits = ctx.get_data("run_001", "hit")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- `use_derivative=True` 适合当前负脉冲检测约定；`False` 时直接在基线减波形上找峰。
- `height_method='diff'` 使用差分积分计算峰高，`'minmax'` 使用峰窗口内最大最小值差；后者可由 `height_window_extension` 扩展窗口。
- `dt` 只在输入数据缺少采样间隔字段时作为兼容补充；输出时间戳统一使用 ps，`dt` 字段单位为 ns。
- 默认 `use_filtered=True`，但实际依赖由 `wave_source` 和 Context 中可用的数据源动态解析；请求 filtered 波形前必须注册 `FilteredWaveformsPlugin`。
- 旧版 `SignalPeaksPlugin`/`signal_peaks` 教程接口已退出当前插件契约；新代码使用 `HitFinderPlugin`/`hit`。
### Failure Modes

- 动态解析的波形依赖缺失、字段不完整或波形池切片越界时，插件无法生成有效 `hit` 输出。
- 峰值检测参数不满足 scipy 或本插件的约束时，执行会抛出配置校验错误。
- 输入时间戳或采样间隔不合法时，无法构造统一 ps 时间戳。
### Downstream Impact

直接消费者：`waveform_width`- `waveform_width` 使用 `hit` 的位置和边缘字段计算波形宽度；峰值筛选参数变化会改变下游宽度样本。
- 需要跨通道峰级分析时，应继续使用 `peaklets`/`peaks` 链，而不是把 `hit` 当作最终 peak 表。

## Maintenance

### Change Playbook

1. 修改寻峰参数、波形来源或 HIT_DTYPE 字段时，应同步检查 waveform_width 和相关兼容 shim，并重新生成 Auto、Agent 与 HTML 文档。
### Validation

```bash
waveform-docs generate plugins-agent --plugin hit
waveform-docs check coverage --strict --fail-on-warning
```
