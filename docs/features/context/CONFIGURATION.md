# 配置管理

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 配置管理

本文档介绍如何在 Context 中管理插件配置。[^source]

## 配置概述

WaveformAnalysis 提供灵活的配置系统：

- **全局配置** - 所有插件共享的配置
- **插件特定配置** - 只对特定插件生效的配置
- **配置优先级** - 插件特定配置 > 全局配置 > 默认值

---

## 配置类型

配置主要分为三类：

1. **全局配置**：在 `Context(config=...)` 或 `ctx.set_config({...})` 中设置，供所有插件共享。
2. **插件特定配置**：通过 `plugin_name` 或嵌套字典指定，仅影响单一插件。
3. **适配器推断配置**：由 DAQ 适配器推断得到的配置值（如采样率、时间间隔）。
4. **Run 级配置文件**：每个 run 可放置 `run_config.json`，用于运行级别参数（如增益标定）。

---

## Channel Config 分层模型

当插件需要按硬件通道覆盖 `polarity`、`threshold`、`fixed_baseline`、
`gain_adc_per_pe` 等行为参数时，统一使用该插件自己的 `channel_config`。

核心规则：

- **唯一键**：硬件通道以 `(board, channel)` 表示
- **推荐写法**：配置键使用 `"board:channel"`，例如 `"0:3"`
- **分层顺序**：`defaults` < `groups` < `channels`
- **行为来源**：插件行为只应由插件标量默认值 + `channel_config` 决定
- **非法旧写法**：不再接受 boardless key，例如 `1`、`"1"`、`{1: 12.5}`

典型结构：

```python
ctx.set_config(
    {
        "defaults": {
            "polarity": "negative",
            "threshold": 20.0,
        },
        "groups": [
            {
                "name": "outer_ring",
                "channels": ["0:0", "0:1", "1:0", "1:1"],
                "config": {"threshold": 28.0},
            }
        ],
        "channels": {
            "0:7": {"threshold": 16.0},
            "1:3": {"polarity": "positive", "threshold": 40.0},
        },
    },
    plugin_name="hit",
)
```

适用建议：

- `basic_features.channel_config`：按硬件通道覆盖 `polarity`、`fixed_baseline`
- `hit.channel_config`：按硬件通道覆盖 `polarity`、`threshold`
- `filtered_waveforms.channel_config` / `wave_pool_filtered.channel_config`：按硬件通道覆盖 `filter_type`、截止频率、SG 参数
- `waveform_width_integral.channel_config`：按硬件通道覆盖 `polarity`
- `df.gain_adc_per_pe` 或 run 级 `calibration.gain_adc_per_pe`：按硬件通道配置增益，键同样必须是 `"board:channel"`

`channel_metadata` 现在只保留描述性/兼容语义，不再作为行为配置来源。

### 配置分层职责

- `Context.config`：分析会话级默认策略，适合放全局插件默认值和常用 `channel_config`
- `run_config.json`：run 级覆盖，适合放当次采集特有的插件行为覆盖和标定
- `plugins.<plugin>`：插件行为配置命名空间
- `plugins.<plugin>.channel_config`：按硬件通道覆盖行为参数
- `calibration`：标定参数命名空间，例如 `gain_adc_per_pe`
- `meta`：run 描述信息，不参与插件行为决策

### 完整优先级关系

插件行为参数建议按下面的顺序理解：

```text
plugin option default
  < Context.config[plugin]
  < Context.config[plugin].channel_config.defaults
  < Context.config[plugin].channel_config.groups
  < Context.config[plugin].channel_config.channels
  < run_config.json.plugins[plugin]
  < run_config.json.plugins[plugin].channel_config.defaults
  < run_config.json.plugins[plugin].channel_config.groups
  < run_config.json.plugins[plugin].channel_config.channels
```

其中：

- `channel_config` 内部始终按 `defaults < groups < channels` 合并
- `meta` 不参与上面的行为优先级链
- `calibration` 走独立标定链，不和 `threshold`/`polarity` 等行为参数混用

### 字段归属建议

| 字段类别 | 推荐位置 |
| --- | --- |
| `threshold` / `polarity` / `fixed_baseline` | `plugins.<plugin>.channel_config` |
| 通道硬件事实 truth（`polarity` / `geometry` / `adc_bits`） | 顶层 `channel_metadata` |
| `gain_adc_per_pe` | `calibration.gain_adc_per_pe` |
| `operator` / `sample` / `comment` / `firmware_version` | `meta.*` |

### `channel_metadata` 分层模型

顶层 `channel_metadata` 用于表达通道硬件事实 truth，不直接驱动插件行为。推荐结构为：

```json
{
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
  }
}
```

对应规则：

- `defaults`：所有通道共享的 hardware truth 默认值
- `groups`：一组通道共享的 truth
- `channels`：单通道最终 truth
- merge 顺序：`defaults < groups < channels`
- `channel_metadata.polarity` 是 hardware truth
- `plugins.<plugin>.channel_config.polarity` 是插件运行时行为配置

### `groups` 是否支持

支持。`channel_config` 的标准结构就是：

```json
{
  "defaults": {...},
  "groups": [...],
  "channels": {...}
}
```

其中：

- `defaults`：所有通道共享的默认值
- `groups`：一批硬件通道共享的覆盖
- `channels`：单通道最终覆盖

合并顺序固定为：

```text
defaults < groups < channels
```

因此 `groups` 很适合：

- 一整板卡共享同一组参数
- 一组正极性通道共享相同 `threshold`
- 一片几何区域共享 `fixed_baseline`

### `groups` 示例

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

对应结果：

- `hit(1:1)`：来自 `positive_board1`，结果为 `polarity=positive, threshold=35.0`
- `hit(1:0)`：先命中 `positive_board1`，再被 `channels["1:0"]` 覆盖，结果为 `polarity=positive, threshold=40.0`
- `basic_features(0:1)`：先命中 `board0_baseline`，再被单通道覆盖，结果为 `fixed_baseline=8200.0`

### Context.config 示例

```python
ctx = Context(
    config={
        "data_root": "/data/DAQ",
        "run_config_path": "{data_root}/{run_id}/run_config.json",
        "daq_adapter": "vx2730",
        "hit": {
            "threshold": 20.0,
            "channel_config": {
                "defaults": {"polarity": "negative"},
                "groups": [
                    {
                        "name": "outer_ring",
                        "channels": ["0:0", "0:1", "0:2", "0:3"],
                        "config": {"threshold": 24.0},
                    }
                ],
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
                    "1:7": {"polarity": "positive"},
                },
            },
        },
    }
)
```

---

## Context 初始化配置参考

`Context(config=...)` 中的全局配置会被 Context 或核心模块直接读取。插件级配置请使用
`ctx.list_plugin_configs()` 查看。

| 配置键 | 默认值 | 说明 |
| --- | --- | --- |
| `data_root` | `"DAQ"` | DAQ 根目录，同时作为默认缓存目录 `storage_dir` |
| `daq_adapter` | `None` | 默认 DAQ 适配器名称（RawFiles/Waveforms/StWaveforms/Records/Events 可用） |
| `wave_source` | `"auto"` | 波形源选择：`auto`/`records`/`st_waveforms`/`filtered_waveforms`（支持被插件同名配置覆盖） |
| `n_channels` | `None` | 通道数；为空时尽量通过扫描自动推断 |
| `show_progress` | `True` | 是否显示加载/处理进度条 |
| `start_channel_slice` | `0` | 兼容旧流程的通道偏移（新流程不再使用） |
| `plugin_backends` | `None` | 按数据名指定存储后端：`{"st_waveforms": MemmapStorage(...), ...}` |
| `compression` | `None` | 默认存储压缩后端（如 `"blosc2"`, `"zstd"`, `"lz4"`, `"gzip"` 或实例） |
| `compression_kwargs` | `None` | 传给压缩后端的参数（如 `{"level": 3}`） |
| `enable_checksum` | `False` | 写入时生成校验和 |
| `verify_on_load` | `False` | 读取时校验数据完整性 |
| `checksum_algorithm` | `"xxhash64"` | 校验算法（`xxhash64` / `sha256` / `md5`） |

### data_root 与 storage_dir 的关系

- `data_root`：**原始数据根目录**。RawFilesPlugin 等插件会从这里读取原始数据，
  默认路径为 `{data_root}/{run_id}/RAW`（或由 DAQ adapter 决定）。
- `storage_dir`：**缓存/结果目录**。MemmapStorage 会写入
  `storage_dir/{run_id}/_cache/`（以及 parquet/元数据等）。
- 若不显式传 `storage_dir`，Context 会使用 `data_root` 作为默认缓存目录。
- 若显式传 `storage_dir`，仍需在 `config` 中设置 `data_root` 指向原始数据目录，
  否则原始数据会从默认 `DAQ` 读取。
```python
from waveform_analysis.core.context import Context

ctx = Context(config={"data_root": "/data/DAQ"}, storage_dir="./cache")

# 全局配置
ctx.set_config({'daq_adapter': 'vx2730'})

# 插件特定配置
ctx.set_config({'threshold': 50}, plugin_name='basic_features')
```

## 设置配置

### 全局配置

```python
ctx.set_config({
    'data_root': 'DAQ',
    'daq_adapter': 'vx2730',
    'wave_source': 'records',
    'threshold': 50,
})
```

### `wave_source` 与 `use_filtered` 的 records 语义

当插件支持 `wave_source` 与 `use_filtered` 时，推荐按下列规则理解：

| `wave_source` | `use_filtered` | 实际波形来源 |
| --- | --- | --- |
| `st_waveforms` | `False` | `st_waveforms` |
| `filtered_waveforms` | `False/True` | `filtered_waveforms` |
| `records` | `False` | `records + wave_pool` |
| `records` | `True` | `records + wave_pool_filtered` |

补充说明：
- 在 `wave_source="records"` 路径下，`use_filtered=True` 的含义不是改读
  `filtered_waveforms`，而是改用 `wave_pool_filtered`。
- 这种设计可统一支持直接走 records 路径的适配器（例如 `v1725`）。
- `records` 元数据保持不变，变化的只有用于计算的波形池。

也可以把 JSON 文件中的配置加载到当前 `Context`，效果等同于一次 `ctx.set_config(...)`：

```python
from waveform_analysis.core.context import Context

ctx = Context(storage_dir="./cache")
ctx.from_config_json("configs/context.json")
```

- `config_json_path` 支持相对路径，相对于当前工作目录解析。
- JSON 顶层必须是对象（`dict`）。
- 加载结果会直接并入当前 `ctx.config`，并触发与 `set_config()` 相同的缓存清理逻辑。
- 可选传入 `plugin_name`，把 JSON 内容作为某个插件的命名空间配置导入。
- 同时兼容两种 JSON 格式：
  - 纯配置文件：顶层直接是配置对象
  - 运行时快照文件：若顶层包含 `custom_config`，会自动提取该字段作为配置导入
- 对于原本在 Python 中常写成 tuple 的配置项，JSON 中可使用数组表示；
  例如 `st_waveforms.baseline_samples` 可写成 `[0, 800]`。

## Run 级配置文件（run_config.json）

当通道很多时，推荐把 run 专属参数放进 `run_config.json`：

- 默认路径：`{data_root}` 的同级目录下，即 `{data_root_parent}/{run_id}/run_config.json`
  - 例如原始数据在 `/data/DAQ/<run_id>/RAW`，则默认读取 `/data/<run_id>/run_config.json`
  - 若目录结构是 `/data/<run_id>/DAQ/RAW`，默认路径不一定符合预期，建议显式设置 `run_config_path`
- 推荐统一使用：
  - `run_config_path`（支持 `{run_id}`, `{run_name}`, `{data_root}`, `{data_root_parent}`, `{filename}`）
- 兼容旧配置：
  - `run_config_filename`（默认 `run_config.json`，主要用于兼容旧配置）
  - `run_config_path_template`（旧字段，仍兼容，但建议迁移到 `run_config_path`）

当目录结构为 `run_id/DAQ` 时，可这样显式配置：

```python
ctx.set_config({
    "data_root": "/data",
    "run_config_path": "{data_root}/{run_id}/run_config.json",
})
```

示例：

```json
{
  "meta": {
    "operator": "alice",
    "updated_at": "2026-03-09T10:20:00Z"
  },
  "calibration": {
    "gain_adc_per_pe": {
      "0:0": 12.5,
      "0:1": 13.2,
      "1:0": 12.7
    }
  },
  "plugins": {
    "basic_features": {
      "channel_config": {
        "defaults": {"polarity": "negative"},
        "channels": {
          "0:1": {"fixed_baseline": 8192.0}
        }
      }
    },
    "hit": {
      "channel_config": {
        "defaults": {"threshold": 22.0, "polarity": "negative"},
        "channels": {
          "1:0": {"polarity": "positive", "threshold": 35.0}
        }
      }
    }
  }
}
```

当前 `df` 会读取 `calibration.gain_adc_per_pe`。
若同时设置了显式配置 `gain_adc_per_pe`，显式配置优先。
注意这里的 key 必须是 `"board:channel"`；裸通道号已不再支持。

### 逐步 merge 示例

以上面的 `Context.config` 和本节 `run_config.json` 为例：

- `hit(1:7)`：
  - 插件默认值
  - 被 `Context.config["hit"]["threshold"] = 20.0` 覆盖
  - 再被 `Context.config["hit"]["channel_config"]["channels"]["1:7"]` 覆盖为
    `polarity=positive, threshold=36.0`
  - 再被 `run_config.json["plugins"]["hit"]["threshold"] = 22.0` 覆盖 threshold
  - 最后被 `run_config.json["plugins"]["hit"]["channel_config"]["channels"]["1:7"]`
    覆盖为 `threshold=42.0`
  - 最终结果：`polarity=positive, threshold=42.0`

- `basic_features(0:3)`：
  - `Context.config["basic_features"]["channel_config"]["defaults"]` 给出
    `polarity=negative`
  - `Context.config["basic_features"]["channel_config"]["channels"]["0:3"]` 给出
    `fixed_baseline=8192.0`
  - `run_config.json["plugins"]["basic_features"]["channel_config"]["channels"]["0:3"]`
    覆盖 `fixed_baseline=8300.0`
  - 最终结果：`polarity=negative, fixed_baseline=8300.0`

- `df.gain_adc_per_pe`：
  - 若显式配置 `df.gain_adc_per_pe`，则优先使用显式配置
  - 否则读取 `run_config.json["calibration"]["gain_adc_per_pe"]`
  - 因此在本例中，若未显式配置，则 `df(1:7)` 使用 `9.5`

### 插件特定配置（推荐）

```python
# 方式 1: 使用 plugin_name 参数（推荐）
ctx.set_config({'threshold': 50}, plugin_name='basic_features')
ctx.set_config({'filter_type': 'SG'}, plugin_name='filtered_waveforms')

# 方式 2: 嵌套字典格式
ctx.set_config({
    'peaks': {'threshold': 50},
    'filtered_waveforms': {'filter_type': 'SG'}
})

# 方式 3: 点分隔格式
ctx.set_config({
    'peaks.threshold': 50,
    'filtered_waveforms.filter_type': 'SG'
})
```

对于按硬件通道差异化的插件，推荐直接把 `channel_config` 放在对应插件命名空间内：

```python
ctx.set_config(
    {
        "hit": {
            "threshold": 24.0,
            "channel_config": {
                "defaults": {"polarity": "negative"},
                "channels": {
                    "0:0": {"threshold": 18.0},
                    "1:0": {"polarity": "positive", "threshold": 36.0},
                },
            },
        },
        "basic_features": {
            "channel_config": {
                "channels": {
                    "0:0": {"fixed_baseline": 8192.0},
                }
            }
        },
        "filtered_waveforms": {
            "filter_type": "SG",
            "channel_config": {
                "channels": {
                    "1:3": {"filter_type": "BW", "lowcut": 0.08, "highcut": 0.18, "fs": 1.0},
                }
            },
        },
    }
)
```

### 批量设置

```python
ctx.set_config({
    'data_root': 'DAQ',        # 全局
    'daq_adapter': 'vx2730',   # 全局
    'peaks': {
        'threshold': 50,
        'min_distance': 10
    },
    'filtered_waveforms': {
        'filter_type': 'BW',
        'lowcut': 1e6,
        'highcut': 1e8
    }
})
```

## 查看配置

```python
# 显示全局配置
ctx.show_config()

# 显示特定插件的详细配置
ctx.show_config('filtered_waveforms')

# 简洁模式
ctx.show_config(show_usage=False)
```

`ctx.show_config()` 中的 `Context 配置项` 表会把 Context 自身消费的路径类配置单独列出，
并在 `note` 列中直接说明用途，而不是仅标注“由 Context 自身消费”。

常见条目说明：

| key | note 含义 |
| --- | --- |
| `custom_config_json_path` | 分析配置快照 JSON 输出路径 |
| `data_root` | 原始 DAQ 数据根目录 |
| `run_config_path` | run 级配置文件路径模板 |
| `storage_dir` | 缓存与处理产物存储目录 |

若某项当前未显式设置、但 Context 会使用默认值，`note` 会追加 `（默认值）`。

## 查询配置选项

```python
# 列出所有插件的配置选项
ctx.list_plugin_configs()

# 只查看特定插件的配置选项
ctx.list_plugin_configs(plugin_name='filtered_waveforms')

# 获取配置字典而不打印
config_info = ctx.list_plugin_configs(verbose=False)
```

## 配置优先级

配置查找顺序（从高到低）：

1. 插件特定配置（嵌套字典）: `config['plugin_name']['option']`
2. 插件特定配置（点分隔）: `config['plugin_name.option']`
3. 全局配置: `config['option']`
4. 插件默认值: `plugin.options['option'].default`

```python
ctx.set_config({
    'threshold': 10,           # 全局默认
    'peaks': {
        'threshold': 50        # peaks 插件特定
    }
})

# peaks 插件获取到 50（插件特定）
# 其他插件获取到 10（全局）
```

## 适配器推断

当设置了 `daq_adapter` 时，系统会从适配器元数据推断部分配置，常见包括：
- 采样率（`sampling_rate_hz`）
- 采样间隔（`dt` / `dt_ps`，兼容层仍可从历史 `dt_ns` 推断）
- 时间戳单位（`timestamp_unit`，仅描述原生物理单位）
- 原生时间戳语义（`raw_timestamp_mode`，如 `unit` / `sample_index`）

推断配置在解析优先级中低于显式配置，高于插件默认值。最终生效值可通过
`ctx.get_resolved_config()` 或 `ctx.show_resolved_config()` 查看。

如需适配器细节与扩展方法，参考 [DAQ 适配器使用指南](../../plugins/guides/DAQ_ADAPTER_GUIDE.md)。

## 兼容层

配置系统提供兼容层用于处理历史配置名称的迁移：

- **别名映射**：旧配置名会被自动映射到新名称。
- **弃用提示**：使用已弃用配置时会给出警告，过期后报错。

若你在升级后遇到配置不生效，建议通过 `ctx.show_config()` 或
`ctx.get_resolved_config()` 检查最终生效的配置来源。

### compat.py 与 CompatManager 的区别

- `waveform_analysis/core/compat.py`：旧式兼容工具，提供单位转换与旧名称映射的基础函数，
  主要为历史逻辑保留；不参与新配置解析流程。
- `waveform_analysis/core/config/compat.py`（CompatManager）：新配置兼容层，专门处理参数别名、
  弃用策略与提示，并在 `ConfigResolver` 中生效。

如果你的需求是**配置别名/弃用管理**，应优先使用 `CompatManager`。

### CompatManager 快速上手

`CompatManager` 用于管理配置别名与弃用信息，避免升级后配置名变化导致行为不一致。

```python
from waveform_analysis.core.config import CompatManager, DeprecationInfo

# 注册参数别名
CompatManager.register_alias("old_param", "new_param", plugin_name="peaks")

# 注册弃用信息
CompatManager.register_deprecation(DeprecationInfo(
    old_name="break_threshold_ns",
    new_name="break_threshold_ps",
    deprecated_in="1.1.0",
    removed_in="2.0.0",
    message="Use break_threshold_ps instead."
))
```

提示：
- 兼容规则会在 `ConfigResolver` 中生效，`ctx.get_resolved_config()` 可查看解析后的来源。
- 当当前版本 >= `removed_in` 时，使用旧参数会抛出 `ValueError`。

## 常用配置项

### 信号处理配置

```python
# Butterworth 滤波器
ctx.set_config({
    'filter_type': 'BW',
    'lowcut': 1e6,
    'highcut': 1e8,
    'order': 4
}, plugin_name='filtered_waveforms')

# Savitzky-Golay 滤波器
ctx.set_config({
    'filter_type': 'SG',
    'sg_window_size': 15,
    'sg_poly_order': 3
}, plugin_name='filtered_waveforms')
```

### 峰值检测配置

```python
ctx.set_config({
    'height': 0.1,
    'distance': 10,
    'prominence': 0.05,
    'use_derivative': True
}, plugin_name='signal_peaks')
```

### 多板卡通道配置

```python
ctx.set_config(
    {
        "polarity": "negative",
        "channel_config": {
            "defaults": {"threshold": 20.0},
            "groups": [
                {
                    "name": "board1",
                    "channels": ["1:0", "1:1", "1:2", "1:3"],
                    "config": {"threshold": 32.0},
                }
            ],
            "channels": {
                "0:5": {"threshold": 14.0},
                "1:7": {"polarity": "positive", "threshold": 45.0},
            },
        },
    },
    plugin_name="hit",
)
```

要点：

- `channel` 字段现在只表示板内通道号，不再代表全局唯一通道
- 多板卡数据筛选/配置时请始终显式提供 `board`
- 若旧配置仍写成 `{0: 12.5, 1: 13.2}` 这类 boardless map，需要先迁移成 `"board:channel"` 键

## 最佳实践

### 1. 优先使用插件特定配置

```python
# 推荐：明确指定插件
ctx.set_config({'threshold': 50}, plugin_name='basic_features')

# 不推荐：全局配置可能影响多个插件
ctx.set_config({'threshold': 50})
```

### 2. 在数据获取前设置配置

```python
# 正确顺序
ctx.set_config({'filter_type': 'BW'}, plugin_name='filtered_waveforms')
data = ctx.get_data("run_001", "filtered_waveforms")
```

### 3. 使用 preview_execution 确认配置

```python
ctx.set_config({'filter_type': 'BW'}, plugin_name='filtered_waveforms')
ctx.preview_execution("run_001", "filtered_waveforms")  # 预览确认
data = ctx.get_data("run_001", "filtered_waveforms")
```

## 常见问题

### Q1: 配置不生效怎么办？

```python
# 1. 确认插件已注册
print(ctx.list_provided_data())

# 2. 确认配置选项名称正确
ctx.list_plugin_configs(plugin_name='your_plugin')

# 3. 查看当前配置
ctx.show_config('your_plugin')

# 4. 清除缓存重新计算
ctx.clear_data("run_001", "your_plugin")
```

### Q2: 配置会影响缓存吗？

是的，配置是 lineage 的一部分。配置变更会导致缓存失效：

```python
ctx.set_config({'threshold': 100}, plugin_name='basic_features')
data = ctx.get_data("run_001", "basic_features")  # 重新计算
```

补充：`run_config.json` 内容变化会自动触发该 run 的相关缓存失效（`df` 及其下游）。

### Q3: 如何导出/保存配置？

```python
import json

# 导出配置
with open('config_backup.json', 'w') as f:
    json.dump(ctx.config.copy(), f, indent=2)

# 恢复配置
with open('config_backup.json', 'r') as f:
    ctx.set_config(json.load(f))
```

## 相关文档

- [插件管理](PLUGIN_MANAGEMENT.md) - 注册和管理插件
- [数据访问](DATA_ACCESS.md) - 获取数据
- [执行预览](PREVIEW_EXECUTION.md) - 确认配置生效
- [内置插件文档](../../plugins/reference/builtin/auto/INDEX.md) - 插件配置选项列表
- [Agent 入口](../../../AGENTS.md) - 任务导航与约束
- [Agent 文档索引](../../agents/INDEX.md) - agent 专题说明

[^source]: 来源：`waveform_analysis/core/context.py`、`waveform_analysis/core/config/`。
