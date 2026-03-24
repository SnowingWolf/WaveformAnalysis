# Agent Configuration Guide

## 配置优先级
显式配置 > adapter 推断 > 插件默认值

## Channel Config 分层模型
- 涉及硬件通道差异的行为配置，统一放到插件自己的 `channel_config`
- 硬件通道唯一键统一为 `(board, channel)`，文档/配置中推荐写成字符串键 `"board:channel"`
- `channel_config` 采用三层覆盖：`defaults` < `groups` < `channels`
- `groups[].channels` 中可以列出多个硬件通道选择器，但最终落到单通道覆盖时仍以 `(board, channel)` 为准
- 不再接受 boardless key，例如裸 `1` 或 `"1"`；这类配置现在应视为非法
- `channel_metadata` 仅保留描述性/兼容用途，不再参与插件行为决策

示例：

```python
ctx.set_config(
    {
        "defaults": {"polarity": "negative", "threshold": 24.0},
        "groups": [
            {
                "name": "top",
                "channels": ["0:0", "0:1", "1:0"],
                "config": {"threshold": 30.0},
            }
        ],
        "channels": {
            "0:3": {"threshold": 18.0},
            "1:7": {"polarity": "positive", "threshold": 42.0},
        },
    },
    plugin_name="hit",
)
```

## 推荐实践
- 全局设置 `daq_adapter`，减少链路配置漂移
- 使用 `ctx.get_resolved_config()` 检查配置来源
- 参数重命名要走兼容层并评估弃用窗口
- 当同一插件需要按极性、板卡或通道做差异化控制时，优先在该插件的 `channel_config` 内分层表达，不要再拆多套 context
- 若目录结构为 `/data/<run_id>/DAQ/RAW`，建议显式设置 `run_config_path`，避免默认 run 级配置路径不匹配：
  - `ctx.set_config({"data_root": "/data", "run_config_path": "{data_root}/{run_id}/run_config.json"})`

## 风险点
- 配置字段更名但未加兼容映射
- 插件与全局配置同名造成语义冲突
- 在多板卡数据上继续把 `channel` 当作全局唯一键
- 在 `run_config.json` 或插件配置里继续使用 boardless 通道键
