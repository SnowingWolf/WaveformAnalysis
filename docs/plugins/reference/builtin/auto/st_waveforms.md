---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "st_waveforms"
plugin_class: "WaveformsPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.waveforms"
version: "0.10.0"
summary: "Extract waveforms from raw CSV files and structure them into NumPy structured arrays."
depends_on: []
output_kind: "structured_array"
generated: true
---
# st_waveforms

## Overview

Extract waveforms from raw CSV files and structure them into NumPy structured arrays.
| Item | Value |
| --- | --- |
| Provides | `st_waveforms` |
| Plugin Class | `WaveformsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.waveforms` |
| Version | `0.10.0` |
| Category | 波形处理 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `daq_adapter` | `str` | `vx2730` | - | yes | no | DAQ adapter name (e.g., 'vx2730') |
| `wave_length` | `int` | `None` | - | yes | no | Waveform length (number of sampling points). Automatically detect from the data when None。 |
| `dt` | `int` | `None` | - | yes | no | Sampling interval in ns for st_waveforms.dt (None=auto from adapter). |
| `n_jobs` | `int` | `None` | - | no | no | Number of parallel workers for file-level processing (None=auto, uses min(total_files, 50)) |
| `use_process_pool` | `bool` | `False` | - | no | no | Whether to use process pool for file-level parallelism (False=thread pool for I/O, True=process pool for CPU-intensive) |
| `chunksize` | `int` | `None` | - | no | no | Chunk size for CSV reading (None=read entire file, enables PyArrow; set value to enable chunked reading but disables PyArrow) |
| `parse_engine` | `str` | `auto` | - | no | no | CSV engine: auto \| polars \| pyarrow \| pandas |
| `use_upstream_baseline` | `bool` | `False` | - | yes | no | Whether to use baseline from upstream plugin (requires 'baseline' data). |
| `baseline_samples` | `any` | `None` | - | yes | no | Baseline range: int (sample count from adapter start) or tuple (start, end) relative to samples_start. JSON lists like [0, 800] are also accepted. None=adapter default. |
| `streaming_mode` | `bool` | `False` | - | no | no | Enable streaming mode: read files and structure waveforms incrementally to reduce memory usage. When enabled, uses memmap for output to avoid full vstack memory overhead. |
## Output

structured_array output with fields: baseline, baseline_upstream, polarity, timestamp, record_id, dt, event_length, board, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `baseline` | `float64` | - | - |
| `baseline_upstream` | `float64` | - | - |
| `polarity` | `<U8` | - | - |
| `timestamp` | `int64` | - | - |
| `record_id` | `int64` | - | - |
| `dt` | `int32` | - | - |
| `event_length` | `int32` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `wave` | `('<i2', (1500,))` | - | - |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WaveformsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(WaveformsPlugin())
data = ctx.get_data("run_001", "st_waveforms")
```
### Downstream Consumers

- `filtered_waveforms`
