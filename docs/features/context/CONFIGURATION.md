# 配置管理

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 配置管理

本文档介绍如何在 Context 中管理插件配置。

## 配置概述

WaveformAnalysis 提供灵活的配置系统：

- **全局配置** - 所有插件共享的配置
- **插件特定配置** - 只对特定插件生效的配置
- **配置优先级** - 插件特定配置 > 全局配置 > 默认值

```python
from waveform_analysis.core.context import Context

ctx = Context(storage_dir="./cache")

# 全局配置
ctx.set_config({'daq_adapter': 'vx2730'})

# 插件特定配置
ctx.set_config({'threshold': 50}, plugin_name='basic_features')
```

## Context 初始化配置

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `data_root` | `"DAQ"` | DAQ 根目录 |
| `daq_adapter` | `None` | 默认 DAQ 适配器名称 |
| `n_channels` | `None` | 通道数（为空时自动推断） |
| `show_progress` | `True` | 是否显示进度条 |
| `compression` | `None` | 存储压缩后端（如 `"blosc2"`, `"zstd"`） |
| `enable_checksum` | `False` | 写入时生成校验和 |
| `verify_on_load` | `False` | 读取时校验数据完整性 |

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
- [配置参考](../../api/config_reference.md) - 完整配置选项列表
