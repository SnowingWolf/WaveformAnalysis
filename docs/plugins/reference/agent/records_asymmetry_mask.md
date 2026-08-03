---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "records_asymmetry_mask"
plugin_class: "RecordsAsymmetryMaskPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.records_asymmetry"
version: "0.2.0"
summary: "Bool mask for waveform asymmetry selection."
depends_on: ["records", "wave_pool"]
output_kind: "array"
generated: true
---
# records_asymmetry_mask

## Overview

Bool mask for waveform asymmetry selection.
Return a bool mask aligned with the original records array.

| Item | Value |
| --- | --- |
| Provides | `records_asymmetry_mask` |
| Plugin Class | `RecordsAsymmetryMaskPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.records_asymmetry` |
| Version | `0.2.0` |
| Category | 记录处理 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | declared | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | declared | - | Build wave_pool from the shared internal records bundle. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `asymmetry_cut_min` | `float` | `0.7` | - | yes | no | Keep records with asymmetry >= this value. |
| `asymmetry_parallel` | `bool` | `True` | - | no | no | Use Numba prange parallel loop. |
| `asymmetry_chunk_size` | `int` | `200000` | - | no | no | Number of records processed per Numba call. |
| `asymmetry_num_threads` | `int` | `0` | - | no | no | Numba thread count. <=0 keeps current Numba default. |
| `asymmetry_polarity_mode` | `str` | `auto` | - | yes | no | Polarity handling mode: 'auto' (extract from records['polarity']), 'negative' (baseline - w_min), 'positive' (w_max - baseline). |
## Output

array output with fields: value.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `value` | `bool` | - | Boolean mask: True for records passing waveform asymmetry selection |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import RecordsAsymmetryMaskPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(RecordsAsymmetryMaskPlugin())
data = ctx.get_data("run_001", "records_asymmetry_mask")
```

## Operational Notes

### Behavior

### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `records_detector_mask`, `records_veto_mask`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin records_asymmetry_mask
waveform-docs check coverage --strict --fail-on-warning
```
