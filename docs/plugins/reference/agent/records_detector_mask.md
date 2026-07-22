# records_detector_mask (RecordsDetectorMaskPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `records_detector_mask` |
| Depends On | `records`, `records_asymmetry_mask` |
| Output Kind | `array` |
| Version | `0.1.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.records_channel_role` |
| Accelerator | `cpu` |

## Source Notes

Records-backed channel role masks for detector/veto splitting.

## Inputs

- `records`
- `records_asymmetry_mask`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `value` | `bool` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `channel_config` | `dict` | `None` | 按 (board, channel) 的通道角色配置；role='detector' 进入正常 hit，role='veto' 仅作为 veto 通道保留。 |

## Execution Path

`records_detector_mask` 依赖链入口：
`records -> records_asymmetry_mask -> records_detector_mask`

## Failure Modes

- 依赖数据缺失或字段不匹配，导致 compute 阶段报错
- 配置值类型/范围不合法，触发参数校验异常
- 输出 dtype 变更但版本未升级，可能导致缓存命中异常

## Change Playbook

1. 修改 `options`/`output_dtype`/核心算法后同步提升 `version`
2. 保持 `provides` 稳定；若必须变更，更新依赖插件与文档索引
3. 新增/删除输出字段时，同时更新消费方插件和回归测试

## Validation

```bash
# 单插件文档再生成
waveform-docs generate plugins-agent --plugin records_detector_mask

# 覆盖率检查
waveform-docs check coverage --strict
```
