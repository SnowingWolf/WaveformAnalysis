# Agent Configuration Guide

## 配置优先级
显式配置 > adapter 推断 > 插件默认值

## 推荐实践
- 全局设置 `daq_adapter`，减少链路配置漂移
- 使用 `ctx.get_resolved_config()` 检查配置来源
- 参数重命名要走兼容层并评估弃用窗口
- 若目录结构为 `/data/<run_id>/DAQ/RAW`，建议显式设置 `run_config_path`，避免默认 run 级配置路径不匹配：
  - `ctx.set_config({"data_root": "/data", "run_config_path": "{data_root}/{run_id}/run_config.json"})`

## 风险点
- 配置字段更名但未加兼容映射
- 插件与全局配置同名造成语义冲突
