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

---

## Context 初始化配置参考

`Context(config=...)` 中的全局配置会被 Context 或核心模块直接读取。插件级配置请使用
`ctx.list_plugin_configs()` 查看。

| 配置键 | 默认值 | 说明 |
| --- | --- | --- |
| `data_root` | `"DAQ"` | DAQ 根目录，同时作为默认缓存目录 `storage_dir` |
| `daq_adapter` | `None` | 默认 DAQ 适配器名称（RawFiles/Waveforms/StWaveforms/Records/Events 可用） |
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
    'threshold': 50,
})
```

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
- [内置插件文档](../../plugins/builtin/auto/INDEX.md) - 插件配置选项列表

[^source]: 来源：`waveform_analysis/core/context.py`、`waveform_analysis/core/config/`。
