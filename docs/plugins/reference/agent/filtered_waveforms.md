---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "filtered_waveforms"
plugin_class: "FilteredWaveformsPlugin"
module: "waveform_analysis.core.plugins.builtin.filtered_waveforms.plugin"
version: "3.0.0"
summary: "Apply filtering to waveforms using Butterworth or Savitzky-Golay filters."
depends_on: ["st_waveforms"]
declared_depends_on: ["st_waveforms"]
resolved_depends_on: ["st_waveforms"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "fe489329b697bfe507578d9732c1009231142d4907e2aefa01ab6a2f4bcc7e7c"
generated: true
---
# filtered_waveforms

## Overview

Apply filtering to waveforms using Butterworth or Savitzky-Golay filters.
FilteredWaveformsPlugin 对 `st_waveforms` 中每个事件的波形应用数字滤波，输出与输入同构、仅将 `wave` 字段替换为 float32 的结构化数组。它支持两种滤波引擎：Butterworth 带通滤波（'BW'，先经 `scipy.signal.butter` 设计 SOS 再 `sosfiltfilt` 零相位滤波）与 Savitzky-Golay 平滑（'SG'，`savgol_filter`），并按 (board, channel) 分组、可选分批与并行地处理。

该插件与 records-backed 的 `wave_pool_filtered`（WavePoolFilteredPlugin）共享 filtering 模块的配置解析与通道覆盖逻辑；`channel_config` 可按 (board, channel) 覆盖滤波参数，`max_workers`/`batch_size` 控制并行与分批策略。

输出保留 st_waveforms 的所有非 wave 字段（baseline、timestamp、record_id、board、channel 等），保持行语义不变；`save_when='target'` 意味着它只在被目标消费时物化，例如 `signal_peaks_stream` 流式峰值检测与 `waveform_width`（use_filtered=True 时）都以 `filtered_waveforms` 作为滤波波形源。

| Item | Value |
| --- | --- |
| Provides | `filtered_waveforms` |
| Plugin Class | `FilteredWaveformsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.filtered_waveforms.plugin` |
| Version | `3.0.0` |
| Category | 波形处理 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `target` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `fe489329b697bfe507578d9732c1009231142d4907e2aefa01ab6a2f4bcc7e7c` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `st_waveforms` | - | declared | - | Extract waveforms from raw CSV files and structure them into NumPy structured arrays. |
### How It Works

1. 读取输入：从 context 获取 `st_waveforms`，校验其为结构化数组且包含 `channel` 与 `wave` 字段。
2. 确定输出 dtype：按输入 dtype 构造 `wave` 为 float32 的滤波 dtype（`create_filtered_waveform_dtype`）；空输入直接返回空数组。
3. 复制非波字段：将 `st_waveforms` 除 `wave` 外的所有字段原样复制到输出，保持行对齐。
4. 解析滤波配置：按 (board, channel) 分组（`build_filter_batches`，可含 `channel_config` 通道覆盖），对每个批次解析并校验 BW/SG 参数。
5. 执行滤波：`max_workers` 允许且批次多于 1 时用线程池 `parallel_map` 并行，否则串行；对每个批次的 `wave` 应用 `_filter_channel`（sosfiltfilt / savgol_filter）。
6. 写回输出：将滤波后的 float32 波形写回 `output['wave']` 的对应批次切片，返回结果。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `filter_type` | `str` | `SG` | - | yes | no | 滤波器类型：'BW'（Butterworth 带通）或 'SG'（Savitzky-Golay）。 |
| `lowcut` | `float` | `0.1` | - | yes | no | BW 低频截止频率。 |
| `highcut` | `float` | `0.5` | - | yes | no | BW 高频截止频率，必须小于奈奎斯特频率 fs/2。 |
| `fs` | `float` | `0.5` | - | yes | no | BW 采样率（GHz）。 |
| `filter_order` | `int` | `4` | - | yes | no | BW 滤波器阶数。 |
| `sg_window_size` | `int` | `11` | - | yes | no | SG 窗口大小（奇数；偶数会自动上取整）。 |
| `sg_poly_order` | `int` | `2` | - | yes | no | SG 多项式阶数，必须小于窗口大小。 |
| `max_workers` | `int` | `None` | - | yes | no | 并行工作线程数；None 使用 CPU 核心数，1 或 0 禁用并行。 |
| `batch_size` | `int` | `0` | - | yes | no | 每批次事件数（0 表示不分批，整个通道一次处理）。 |
| `channel_config` | `dict` | `None` | - | yes | no | 按 (board, channel) 的插件通道覆盖配置，可覆盖滤波参数。 |
## Output

structured_array output with fields: baseline, baseline_upstream, polarity, timestamp, record_id, dt, event_length, board, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `baseline` | `float64` | ADC counts | Computed global waveform baseline for this record |
| `baseline_upstream` | `float64` | ADC counts | Upstream baseline value from preceding processing, optional |
| `polarity` | `<U8` | None | Hardware-truth signal polarity: positive \| negative \| unknown |
| `timestamp` | `int64` | ps | ADC raw timestamp in picoseconds |
| `record_id` | `int64` | None | Sequential record identifier within the structured waveform array |
| `dt` | `int32` | ns | Sample interval in nanoseconds, aligned to time |
| `event_length` | `int32` | samples | Waveform length in samples |
| `board` | `int16` | None | Hardware board index |
| `channel` | `int16` | None | Physical channel number |
| `wave` | `('<f4', (1500,))` | ADC counts | Filtered ADC sample data as 1-D float32 array |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "filtered_waveforms")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- `filter_type` only accepts `'BW'` (Butterworth bandpass) or `'SG'` (Savitzky-Golay); any other value raises `ValueError`.
- `channel_config` provides (board, channel)-scoped overrides of the global filter parameters; resolution lives in `resolve_filter_config`.
- `save_when='target'`: the output is materialized only when a downstream consumer requests it, unlike always-save products.
- An even `sg_window_size` is auto-adjusted to the next odd value with a warning.
- `max_workers` of `None` uses CPU-core count, `1` or `0` disables parallelism; parallelism only engages when there is more than one batch.
### Failure Modes

- `st_waveforms` 不是结构化数组、或缺 `channel`/`wave` 字段时抛出 `ValueError`。
- `st_waveforms['wave']` 不是 2D (n_events, n_samples) 时抛出 `ValueError`。
- `batch_size < 0` 时抛出 `ValueError`。
- BW 参数非法（fs<=0、order<=0、截止频率<=0、lowcut>=highcut、highcut>=fs/2）时抛出 `ValueError`。
- SG 参数非法（window<=0、poly_order<0、poly_order>=window）时抛出 `ValueError`。
### Downstream Impact

直接消费者：`signal_peaks_stream`、`waveform_width`- `signal_peaks_stream` 以 `filtered_waveforms` 为波形源做流式峰值检测，输出字段或 dtype 变化会影响其解析。
- `waveform_width` 在 `use_filtered=True` 时经 `resolve_depends_on` 动态依赖 `filtered_waveforms`，依赖 `wave` 字段与行对齐。

## Maintenance

### Change Playbook

1. 滤波参数语义变更会影响 BW/SG 输出特性并级联到 `signal_peaks_stream`、`waveform_width` 与共享的 records 侧 `wave_pool_filtered`，请同步运行对应定向测试并重新生成文档。
### Validation

```bash
waveform-docs generate plugins-agent --plugin filtered_waveforms
waveform-docs check coverage --strict --fail-on-warning
```
