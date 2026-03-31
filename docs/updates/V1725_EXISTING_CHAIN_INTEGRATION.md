# V1725 接入现有链路（st_waveforms 兼容）

**日期**: 2026-03-06
**状态**: ✅ 已完成

## 背景

`v1725` 适配器已支持 `raw_files -> records/events` 分支，但在 `st_waveforms` 路径下曾直接返回读取器原始结构化数组，导致与现有默认链路的数据契约不完全一致。

受影响链路：

`raw_files -> st_waveforms -> basic_features -> df -> df_events -> df_paired`

## 本次变更

在 `WaveformsPlugin` 中为 `daq_adapter == "v1725"` 增加标准化转换：

1. 将 `V1725Reader` 输出转换为标准 `st_waveforms` dtype（包含 `baseline/baseline_upstream/timestamp/dt/event_length/channel/wave`）。
2. `wave` 字段由 object 波形列表统一为固定长度 `int16` 二维数组（按最大长度或 `wave_length` 配置对齐）。
3. `timestamp` 统一转为 ps 标尺（按 `timestamp_ticks * dt * 1000`，其中 `dt` 以 ns 表示）。
4. `event_length` 保留每条记录真实采样长度（不足处零填充）。
5. `baseline_upstream` 统一填充 `NaN`（与现有链路语义一致）。

## 结果

`v1725` 现在可以直接接入现有 `st_waveforms` 生态插件，不再需要额外的专用分支才能使用 `basic_features/df/df_events/df_paired`。

## 代码与测试

- 代码：
  - `waveform_analysis/core/plugins/builtin/cpu/waveforms.py`
- 测试：
  - `tests/plugins/test_plugin_auto_config.py`
  - 新增 `test_waveforms_plugin_v1725_outputs_standard_st_waveforms`

## 已知说明

- 本次改动保持 `records/events` 的 `v1725` 专用优化路径不变，仅补齐 `st_waveforms` 兼容。
- 若后续需要更细的 `trunc/flags` 语义映射，可在 records/events 层继续增强，不影响本次链路兼容目标。
