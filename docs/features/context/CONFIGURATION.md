**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 配置管理

---

# 配置管理

本文档介绍如何在 Context 中管理插件配置。

---

## 📋 目录

1. [配置概述](#配置概述)
2. [设置配置](#设置配置)
3. [查看配置](#查看配置)
4. [查询配置选项](#查询配置选项)
5. [配置优先级](#配置优先级)
6. [最佳实践](#最佳实践)
7. [常见问题](#常见问题)

---

## 配置概述

WaveformAnalysis 提供灵活的配置系统，支持：

- **全局配置** - 所有插件共享的配置
- **插件特定配置** - 只对特定插件生效的配置
- **配置优先级** - 插件特定配置 > 全局配置 > 默认值

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

```python
from waveform_analysis.core.context import Context

ctx = Context(storage_dir="./cache")

# 全局配置
ctx.set_config({'daq_adapter': 'vx2730'})

# 插件特定配置
ctx.set_config({'threshold': 50}, plugin_name='peaks')
```

---

## 设置配置

### set_config() 方法

```python
def set_config(
    config: Dict[str, Any],         # 配置字典
    plugin_name: Optional[str] = None  # 可选，插件名称
)
```

### 全局配置

```python
# 设置全局配置（所有插件都能访问）
ctx.set_config({
    'data_root': 'DAQ',
    'daq_adapter': 'vx2730',
    'threshold': 50,
})
```

### 插件特定配置（推荐）

```python
# 方式 1: 使用 plugin_name 参数（推荐）
ctx.set_config({'threshold': 50}, plugin_name='peaks')
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
# 一次设置多个插件的配置
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

---

## 查看配置

### show_config() 方法

```python
# 显示全局配置（包含使用情况分析）
ctx.show_config()
```

**展示说明**:
- 未指定插件时，显示三张表：全局配置、插件特定配置、未使用配置
- 缓存目录会显示为 `storage_dir/{run_name}/{data_subdir}` 的形式
- 插件特定配置表包含 `status`（默认/已修改）并在 notebook 中高亮已修改项

### 查看特定插件配置

```python
# 显示特定插件的详细配置
ctx.show_config('filtered_waveforms')
```

**展示说明**:
- 会复用 `list_plugin_configs` 的表格样式
- 使用两张表：插件概览 / 配置明细
- 配置明细按“已修改优先，再按插件/选项”排序

### 不显示使用情况

```python
# 简洁模式，不分析配置使用情况
ctx.show_config(show_usage=False)
```

### 显示完整 help

```python
ctx.show_config(show_full_help=True)
```

---

## 查询配置选项

### list_plugin_configs() 方法

```python
# 列出所有插件的配置选项
ctx.list_plugin_configs()
```

**展示说明**:
- 两张表：插件概览（每插件一行）+ 配置明细（每选项一行）
- 配置明细包含 `status`（默认/已修改），并在 notebook 中高亮已修改项与 `track=False`
- 默认将 `default/current/help` 截断显示，避免表格过长

### 查看特定插件选项

```python
# 只查看特定插件的配置选项
ctx.list_plugin_configs(plugin_name='filtered_waveforms')
```

### 程序化获取配置信息

```python
# 获取配置字典而不打印
config_info = ctx.list_plugin_configs(verbose=False)

# 访问特定插件的配置信息
waveforms_opts = config_info.get('waveforms', {})
for opt_name, opt_info in waveforms_opts.items():
    print(f"{opt_name}: {opt_info['default']} ({opt_info['type']})")
```

### 显示完整 help

```python
ctx.list_plugin_configs(show_full_help=True)
```

### 与 show_config 的关系

- `list_plugin_configs` 是“配置选项清单视图”（默认/当前/状态）
- `show_config` 是“当前配置汇总视图”，但在指定插件名时会复用 `list_plugin_configs` 的表格样式

---

## 配置优先级

配置查找顺序（从高到低）：

```
1. 插件特定配置（嵌套字典）: config['plugin_name']['option']
2. 插件特定配置（点分隔）: config['plugin_name.option']
3. 全局配置: config['option']
4. 插件默认值: plugin.options['option'].default
```

### 示例

```python
# 设置不同级别的配置
ctx.set_config({
    'threshold': 10,           # 全局默认
    'peaks': {
        'threshold': 50        # peaks 插件特定
    }
})

# peaks 插件获取到 50（插件特定）
# 其他插件获取到 10（全局）
```

---

## 常用配置项

### 通用配置

```python
ctx.set_config({
    'data_root': 'DAQ',        # 数据根目录
    'daq_adapter': 'vx2730',   # DAQ 适配器
    'show_progress': True,     # 显示进度条
})
```

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

### 事件分组配置

```python
ctx.set_config({
    'time_window_ns': 100,
    'use_numba': True
}, plugin_name='grouped_events')
```

---

## 最佳实践

### 1. 优先使用插件特定配置

```python
# ✅ 推荐：明确指定插件
ctx.set_config({'threshold': 50}, plugin_name='peaks')

# ⚠️ 不推荐：全局配置可能影响多个插件
ctx.set_config({'threshold': 50})
```

### 2. 在数据获取前设置配置

```python
# ✅ 正确顺序
ctx.set_config({'filter_type': 'BW'}, plugin_name='filtered_waveforms')
data = ctx.get_data("run_001", "filtered_waveforms")

# ⚠️ 配置可能不生效
data = ctx.get_data("run_001", "filtered_waveforms")
ctx.set_config({'filter_type': 'BW'}, plugin_name='filtered_waveforms')  # 太晚了
```

### 3. 使用 preview_execution 确认配置

```python
# 设置配置
ctx.set_config({'filter_type': 'BW'}, plugin_name='filtered_waveforms')

# 预览确认配置正确
ctx.preview_execution("run_001", "filtered_waveforms")

# 确认无误后执行
data = ctx.get_data("run_001", "filtered_waveforms")
```

### 4. 配置变更后清除缓存

```python
# 修改配置
ctx.set_config({'threshold': 100}, plugin_name='peaks')

# 清除相关缓存（配置变更会自动使缓存失效）
# 但如果需要强制重新计算：
ctx.clear_data("run_001", "peaks")
```

---

## 常见问题

### Q1: 配置不生效怎么办？

**A**: 检查以下几点：
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

### Q2: 如何重置为默认配置？

**A**:
```python
# 清除插件特定配置
if 'plugin_name' in ctx.config:
    del ctx.config['plugin_name']

# 或者重新设置为默认值
ctx.set_config({'threshold': 10}, plugin_name='peaks')  # 假设默认是 10
```

### Q3: 如何查看插件的默认值？

**A**:
```python
# 方式 1: 使用 list_plugin_configs
ctx.list_plugin_configs(plugin_name='peaks')

# 方式 2: 直接访问插件
plugin = ctx._plugins['peaks']
for name, opt in plugin.options.items():
    print(f"{name}: {opt.default}")
```

### Q4: 配置会影响缓存吗？

**A**: 是的，配置是 lineage 的一部分。配置变更会导致缓存失效：
```python
# 修改配置后，缓存自动失效
ctx.set_config({'threshold': 100}, plugin_name='peaks')

# 下次 get_data 会重新计算
data = ctx.get_data("run_001", "peaks")  # 重新计算
```

### Q5: 如何导出/保存配置？

**A**:
```python
import json

# 导出配置
config_backup = ctx.config.copy()
with open('config_backup.json', 'w') as f:
    json.dump(config_backup, f, indent=2)

# 恢复配置
with open('config_backup.json', 'r') as f:
    saved_config = json.load(f)
ctx.set_config(saved_config)
```

---

## 相关文档

- [插件管理](PLUGIN_MANAGEMENT.md) - 注册和管理插件
- [数据获取](DATA_ACCESS.md) - 获取数据
- [预览执行](PREVIEW_EXECUTION.md) - 确认配置生效
- [配置参考](../../api/config_reference.md) - 完整配置选项列表

---

**快速链接**: [插件管理](PLUGIN_MANAGEMENT.md) | [数据获取](DATA_ACCESS.md) | [预览执行](PREVIEW_EXECUTION.md)
