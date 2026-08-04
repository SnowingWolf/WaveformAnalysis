---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "records_veto_mask"
plugin_class: "RecordsVetoMaskPlugin"
module: "waveform_analysis.core.plugins.builtin.records_veto_mask.plugin"
version: "0.1.0"
summary: "Bool mask for veto-channel records after channel-role splitting."
depends_on: ["records", "records_asymmetry_mask"]
output_kind: "array"
generated: true
---
# records_veto_mask

## Overview

Bool mask for veto-channel records after channel-role splitting.
`records_veto_mask` 输出一个与 `records` 等长的布尔掩码，标记哪些记录应被视为 veto 通道信号而被排除在正常 hit 检测之外。它解决的是物理层面的通道角色问题：实验中部分通道被定义为 veto 通道（例如宇宙线或噪声监测），这些通道检测到信号时，同一触发窗口内的正常事件应被当作干扰丢弃。

该插件不会丢弃任何数据，而是产出一个可供下游分析阶段查询的掩码。掩码由两部分合成：首先按 (board, channel) 从 `channel_config` 解析每个通道的角色（`role='veto'`），再把角色掩码与 `records_asymmetry_mask` 按位与——即只有『既是 veto 通道、又通过了波形不对称性筛选』的记录才被置为 True。

它与 `records_detector_mask` 是互补的兄弟产物，二者共享同一套角色解析逻辑，仅 `role` 不同；`records_veto_mask` 专门服务于 veto 剔除需求。

| Item | Value |
| --- | --- |
| Provides | `records_veto_mask` |
| Plugin Class | `RecordsVetoMaskPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.records_veto_mask.plugin` |
| Version | `0.1.0` |
| Category | 记录处理 |
| Output Kind | `array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | declared | - | Build records (event index table) from the shared internal records bundle. |
| `records_asymmetry_mask` | - | declared | - | Bool mask for waveform asymmetry selection. |
### How It Works

1. 读取 records：从 context 获取 `records` 结构化数组，并校验其必须包含 `board` 与 `channel` 字段，缺失即抛错。
2. 解析通道角色：按 (board, channel) 遍历（带 rule_cache 缓存），调用 `channel_config` 解析每个通道的 `role`，非法值抛错。
3. 构建角色掩码：将 `role='veto'` 的通道所对应的所有 records 行标记为 True，其余为 False。
4. 合成不对称掩码：读取 `records_asymmetry_mask`，与角色掩码按位与，得到『veto 且通过不对称筛选』的最终掩码；长度不一致时抛错。
5. 返回结果：输出与 records 等长的 bool 数组。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `channel_config` | `dict` | `None` | - | yes | no | 按 (board, channel) 的通道角色配置；`role='detector'` 进入正常 hit，`role='veto'` 作为 veto 通道保留。不配置的通道默认为 detector。 |
## Output

array output with fields: value.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `value` | `bool` | None | Boolean veto mask, one entry per `records` row: True marks a record that belongs to a veto channel (role='veto' in channel_config) and passed the waveform asymmetry selection, so it should be excluded from normal detector hit finding. |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.records_veto_mask import RecordsVetoMaskPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(RecordsVetoMaskPlugin())
data = ctx.get_data("run_001", "records_veto_mask")
```

## Operational Notes

### Behavior

- Only `(board, channel)` pairs present in the channel role config are affected; any channel without an explicit `role` stays `detector`.
- The output is the AND of the veto-channel role mask and `records_asymmetry_mask`, so a veto-role record that fails asymmetry selection is NOT masked.
- `records` missing `board` or `channel` fields raises `ValueError` explicitly.
- Records and `records_asymmetry_mask` must be equal length, otherwise `ValueError` is raised.
### Failure Modes

- `records` 不是结构化数组，或其缺少 `board`/`channel` 字段时抛出 `ValueError`。
- `channel_config` 中某通道的 `role` 不是 `detector`/`veto` 时抛出 `ValueError`。
- `records_asymmetry_mask` 与 `records` 长度不一致时抛出 `ValueError`。
### Downstream Impact

Terminal output; no direct builtin consumer is declared.


## Maintenance

### Change Playbook

1. 修改角色解析或掩码合成逻辑会同时影响 `records_detector_mask`，请一起回归测试。
### Validation

```bash
waveform-docs generate plugins-agent --plugin records_veto_mask
waveform-docs check coverage --strict --fail-on-warning
```
