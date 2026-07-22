---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "raw_files"
plugin_class: "RawFileNamesPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.waveforms"
version: "0.0.2"
summary: "Scan the data directory and group raw CSV files by channel number."
depends_on: []
output_kind: "list"
generated: true
---
# raw_files

## Overview

Scan the data directory and group raw CSV files by channel number.

| Item | Value |
| --- | --- |
| Provides | `raw_files` |
| Plugin Class | `RawFileNamesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.waveforms` |
| Version | `0.0.2` |
| Category | 数据加载 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `list` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `data_root` | `str` | `DAQ` | - | yes | no | Root directory for data |
| `daq_adapter` | `str` | `vx2730` | - | yes | no | DAQ adapter name (e.g., 'vx2730') |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| - | `list` | - | Scan the data directory and group raw CSV files by channel number. |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import RawFileNamesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(RawFileNamesPlugin())
data = ctx.get_data("run_001", "raw_files")
```

## Operational Notes

### Behavior

- Waveforms Plugin - 波形提取与结构化插件

**加速器**: CPU (NumPy)
**功能**: 从原始 CSV 文件中提取波形数据并结构化为 NumPy 结构化数组

本模块包含：
1. RawFileNamesPlugin: 扫描数据目录并按通道分组原始 CSV 文件
2. WaveformsPlugin: 从原始 CSV 文件中提取波形数据并结构化
3. WaveformStructConfig: 波形结构化配置类
4. WaveformStruct: 波形结构化处理器

WaveformsPlugin 支持双层并行处理加速：
- 通道级并行：多个通道同时处理
- 文件级并行：单个通道内的多个文件并行处理

性能优化特性：
- 自动使用 PyArrow 引擎（如果已安装）
- 自动计算最优并行数
- 支持线程池和进程池两种并行方式
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

-
## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin raw_files
waveform-docs check coverage --strict --fail-on-warning
```
