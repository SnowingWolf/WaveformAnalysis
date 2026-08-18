---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "peaklet_channels"
plugin_class: "PeakletChannelsPlugin"
module: "waveform_analysis.core.plugins.builtin.peaklet_channels.plugin"
version: "2.0.3"
summary: "Reconstruct deduplicated per-peaklet channel waveform contributions."
depends_on: ["peaklets", "peaklet_components", "hit_merged", "hit_merged_components", "hit_threshold", "hit_merged_features", "peaklet_features", "records", "wave_pool"]
output_kind: "structured_array"
generated: true
---
# peaklet_channels

## Overview

Reconstruct deduplicated per-peaklet channel waveform contributions.
Reconstruct peaklets into deduplicated per-board/channel contribution rows.

| Item | Value |
| --- | --- |
| Provides | `peaklet_channels` |
| Plugin Class | `PeakletChannelsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaklet_channels.plugin` |
| Version | `2.0.3` |
| Category | 峰构建 |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaklets` | - | dynamic | - | Build lightweight cross-channel peaklets from hit_merged intervals. |
| `peaklet_components` | - | dynamic | - | Return per-peaklet component hit_merged indices. |
| `hit_merged` | - | dynamic | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
| `hit_merged_components` | - | dynamic | - | Return per-cluster component hit indices for hit_merged rows. |
| `hit_threshold` | - | dynamic | - | Threshold-only hit detector with THRESHOLD_HIT_DTYPE output. |
| `hit_merged_features` | - | dynamic | - | Compute per-hit_merged local waveform features from records-backed samples. |
| `peaklet_features` | - | dynamic | - | Compute peaklet waveform features from ragged signal pools. |
| `records` | - | dynamic | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | dynamic | - | Build wave_pool from the shared internal records bundle. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `wave_source` | `str` | `records` | - | yes | no | 波形来源；peaklet_channels 当前正式支持 records。 |
| `use_filtered` | `bool` | `False` | - | yes | no | 是否从 wave_pool_filtered 重建通道波形。 |
| `clip_negative_signal` | `bool` | `False` | - | yes | no | 是否在通道波形合并与积分前把负采样裁剪为 0。 |
## Output

structured_array output with fields: peaklet_id, board, channel, area, height, n_hits, area_fraction.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peaklet_id` | `int64` | None | Peaklet identifier |
| `board` | `int16` | None | Hardware board index |
| `channel` | `int16` | None | Physical channel number |
| `area` | `float32` | ADC counts | Total area contribution from this channel |
| `height` | `float32` | ADC counts | Maximum height contribution from this channel |
| `n_hits` | `int32` | None | Number of component hits from this channel |
| `area_fraction` | `float32` | None | Fraction of the peaklet total area contributed by this channel |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.peaklet_channels import PeakletChannelsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletChannelsPlugin())
data = ctx.get_data("run_001", "peaklet_channels")
```

## Operational Notes

### Behavior

### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `peaks`, `position_reconstruction`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin peaklet_channels
waveform-docs check coverage --strict --fail-on-warning
```
