---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "cache_analysis"
plugin_class: "CacheAnalysisPlugin"
module: "waveform_analysis.core.plugins.builtin.cache_analysis.plugin"
version: "0.1.0"
summary: "Analyze cache usage and return summary, entries, and diagnostics."
depends_on: []
declared_depends_on: []
resolved_depends_on: []
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "dict"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "0e275469219f1f0328e79f16aa264f923b719e6a085096c3ea27b1269c03d44f"
generated: true
---
# cache_analysis

## Overview

Analyze cache usage and return summary, entries, and diagnostics.
Analyze cache usage and return a structured report.

| Item | Value |
| --- | --- |
| Provides | `cache_analysis` |
| Plugin Class | `CacheAnalysisPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cache_analysis.plugin` |
| Version | `0.1.0` |
| Category | 缓存分析 |
| Output Container | `dict` |
| Execution Mode | `static` |
| Save Policy | `never` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | yes |
| Narrative Source | `source` |
| Source Fingerprint | `0e275469219f1f0328e79f16aa264f923b719e6a085096c3ea27b1269c03d44f` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | declared | - | 无输入依赖。 |
### How It Works

1. Analyze cache usage and return a structured report.

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `scan_all_runs` | `bool` | `False` | - | yes | no | Scan all runs instead of only the requested run_id. |
| `data_name` | `str` | `None` | - | yes | no | Optional data name filter for cache entries. |
| `min_size_bytes` | `int` | `None` | - | yes | no | Minimum cache entry size in bytes for filtering. |
| `max_size_bytes` | `int` | `None` | - | yes | no | Maximum cache entry size in bytes for filtering. |
| `min_age_days` | `float` | `None` | - | yes | no | Minimum cache entry age in days for filtering. |
| `max_age_days` | `float` | `None` | - | yes | no | Maximum cache entry age in days for filtering. |
| `compressed_only` | `bool` | `None` | - | yes | no | Filter entries by compression state (True/False). |
| `include_entries` | `bool` | `True` | - | yes | no | Include per-entry details in the result payload. |
| `max_entries` | `int` | `None` | - | yes | no | Limit the number of entries returned (largest by size). |
| `include_metadata` | `bool` | `False` | - | yes | no | Include full metadata dict for each cache entry. |
| `include_diagnostics` | `bool` | `False` | - | yes | no | Run cache diagnostics and include issue list. |
| `export_format` | `str` | `None` | - | yes | no | Export report to output_dir as 'json' or 'csv'. |
| `export_name` | `str` | `cache_analysis` | - | yes | no | Base filename for exported report. |
| `export_path` | `str` | `None` | - | yes | no | Explicit export path. Overrides export_name/output_dir. |
| `verbose` | `bool` | `False` | - | yes | no | Print scan and diagnostic progress. |
## Output

Cache summary, entries, and diagnostics.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| container | `dict` | - | Cache summary, entries, and diagnostics. |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cache_analysis.plugin import CacheAnalysisPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(CacheAnalysisPlugin())
result = ctx.get_data("run_001", "cache_analysis")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- Cache analysis plugin.
- Collects cache statistics and optionally returns filtered cache entries and diagnostic issues. This is meant for interactive inspection and does not write to the main cache by default.
### Failure Modes

- 配置校验失败或输入数据不满足插件实现的前置条件时，执行会失败。
- 输出不符合声明的 dtype/schema 时，结果不会被视为有效插件产物。
### Downstream Impact

没有声明直接的内置消费者。

## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin cache_analysis
waveform-docs check coverage --strict --fail-on-warning
```
