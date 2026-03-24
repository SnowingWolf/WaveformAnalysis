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

## 配置分层职责
- `Context.config`：分析会话级默认策略，适合放通用插件默认值和常用 `channel_config`
- `run_config.json`：run 级覆盖，适合放某次采集特有的行为差异与标定结果
- `plugins.<plugin>`：插件行为配置命名空间
- `plugins.<plugin>.channel_config`：按硬件通道覆盖插件行为
- `calibration`：通道标定参数，如 `gain_adc_per_pe`
- `meta`：run 描述信息，不参与插件行为决策

## 推荐优先级
- 插件行为参数：`plugin option default` < `Context.config` < `run_config.json.plugins.<plugin>`
- 单通道行为参数：先按来源覆盖，再在每个 `channel_config` 内按 `defaults < groups < channels` 合并
- 标定参数：推荐放在 `run_config.json.calibration`；若插件提供显式标定覆盖入口，则显式插件配置优先
- `meta` 只用于描述 run，不应作为 `threshold`、`polarity`、`fixed_baseline` 等行为参数来源

## 推荐放置规则
- `threshold`、`polarity`、`fixed_baseline`：放 `plugins.<plugin>.channel_config`
- `gain_adc_per_pe`：放 `calibration`
- `operator`、`sample`、`comment`、`firmware_version`：放 `meta`
- 通道硬件事实 truth：放顶层 `channel_metadata`

## Channel Metadata 分层模型
- 顶层 `channel_metadata` 用于表达通道硬件事实，例如 `polarity`、`geometry`、`adc_bits`
- 推荐结构与 `channel_config` 一致：`defaults < groups < channels`
- `channel_metadata.polarity` 是 hardware truth；`plugins.*.channel_config.polarity` 是插件运行时行为配置
- 所有通道键仍统一使用 `"board:channel"`

示例：

```json
{
  "meta": {
    "operator": "alice"
  },
  "channel_metadata": {
    "defaults": {
      "adc_bits": 14
    },
    "groups": [
      {
        "name": "board0_negative",
        "channels": ["0:0", "0:1", "0:2", "0:3"],
        "metadata": {
          "polarity": "negative",
          "geometry": "bottom"
        }
      }
    ],
    "channels": {
      "1:2": {
        "geometry": "special_probe"
      }
    }
  },
  "calibration": {
    "gain_adc_per_pe": {
      "0:0": 12.5
    }
  },
  "plugins": {
    "hit": {
      "channel_config": {
        "channels": {
          "1:2": {
            "polarity": "positive",
            "threshold": 35.0
          }
        }
      }
    }
  }
}
```

## 简化示例

```python
ctx = Context(
    config={
        "data_root": "/data/DAQ",
        "run_config_path": "{data_root}/{run_id}/run_config.json",
        "hit": {
            "threshold": 20.0,
            "channel_config": {
                "defaults": {"polarity": "negative"},
                "channels": {
                    "1:7": {"polarity": "positive", "threshold": 36.0},
                },
            },
        },
        "basic_features": {
            "channel_config": {
                "defaults": {"polarity": "negative"},
                "channels": {
                    "0:3": {"fixed_baseline": 8192.0},
                },
            },
        },
    }
)
```

```json
{
  "meta": {
    "operator": "alice",
    "sample": "led_run",
    "comment": "board 1 ch7 switched to positive polarity"
  },
  "calibration": {
    "gain_adc_per_pe": {
      "0:0": 12.5,
      "0:3": 12.9,
      "1:7": 9.5
    }
  },
  "plugins": {
    "hit": {
      "threshold": 22.0,
      "channel_config": {
        "channels": {
          "1:7": {"threshold": 42.0}
        }
      }
    },
    "basic_features": {
      "channel_config": {
        "channels": {
          "0:3": {"fixed_baseline": 8300.0}
        }
      }
    }
  }
}
```

上述示例下：
- `hit(1:7)` 最终为 `polarity=positive, threshold=42.0`
- `basic_features(0:3)` 最终为 `polarity=negative, fixed_baseline=8300.0`
- `df` 若未显式设置 `df.gain_adc_per_pe`，则读取 `calibration.gain_adc_per_pe`

## Groups 用法
- `channel_config` 支持 `groups`
- 推荐位置：`plugins.<plugin>.channel_config.groups`
- 合并顺序始终为：`defaults < groups < channels`
- 适合“同一批硬件通道共享配置，少数通道再单独修正”的场景

示例：

```json
{
  "plugins": {
    "basic_features": {
      "channel_config": {
        "defaults": {
          "polarity": "negative"
        },
        "groups": [
          {
            "name": "board0_baseline",
            "channels": ["0:0", "0:1", "0:2", "0:3"],
            "config": {
              "fixed_baseline": 8192.0
            }
          }
        ],
        "channels": {
          "0:1": {
            "fixed_baseline": 8200.0
          }
        }
      }
    },
    "hit": {
      "channel_config": {
        "defaults": {
          "threshold": 22.0,
          "polarity": "negative"
        },
        "groups": [
          {
            "name": "positive_board1",
            "channels": ["1:0", "1:1", "1:2"],
            "config": {
              "polarity": "positive",
              "threshold": 35.0
            }
          }
        ],
        "channels": {
          "1:0": {
            "threshold": 40.0
          }
        }
      }
    }
  }
}
```

在这个例子里：
- `hit(1:1)` 命中 `positive_board1`，最终为 `polarity=positive, threshold=35.0`
- `hit(1:0)` 先命中 `positive_board1`，再被 `channels["1:0"]` 覆盖，最终为 `polarity=positive, threshold=40.0`
- `basic_features(0:1)` 先命中 `board0_baseline`，再被单通道覆盖，最终 `fixed_baseline=8200.0`

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
