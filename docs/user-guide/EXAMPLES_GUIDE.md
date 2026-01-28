# 常见场景示例

**导航**: [文档中心](../README.md) > [用户指南](README.md) > 常见场景示例


本文档汇集常见的使用场景和代码示例。

---

## 📋 目录

1. [基础操作示例](#基础操作示例)
2. [高级场景示例](#高级场景示例)
3. [完整示例程序](#完整示例程序)
4. [常见问题](#常见问题)

---

## 基础操作示例

### 1. 基础分析流程

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

# 初始化
ctx = Context(storage_dir='./strax_data')
ctx.register(standard_plugins)
ctx.set_config({'data_root': 'DAQ', 'daq_adapter': 'vx2730'})

# 获取数据
basic_features = ctx.get_data('run_001', 'basic_features')
heights = [ch['height'] for ch in basic_features]
areas = [ch['area'] for ch in basic_features]
print(f"Found {len(heights)} height arrays")
```

### 2. 时间范围查询

查询特定时间范围内的数据：

```python
# 使用时间范围查询（默认 time 字段，ns）
data = ctx.get_data_time_range(
    'run_001',
    'st_waveforms',
    start_time=1000000,  # 起始时间（ns）
    end_time=2000000     # 结束时间（ns）
)
print(f"Found {len(data)} events in time range")

# 预构建索引以提高性能（如需按 timestamp 查询，显式指定 time_field='timestamp'）
ctx.build_time_index('run_001', 'st_waveforms', endtime_field='computed')

# 获取索引统计
stats = ctx.get_time_index_stats()
print(f"Total indices: {stats['total_indices']}")
```

### 3. 血缘可视化

可视化数据处理流程：

```python
# LabVIEW 风格（Matplotlib）
ctx.plot_lineage('df_paired', kind='labview')

# 交互式模式
ctx.plot_lineage('df_paired', kind='labview', interactive=True)

# Plotly 高级交互式
ctx.plot_lineage('df_paired', kind='plotly', verbose=2)

# 自定义样式
from waveform_analysis.core.foundation.utils import LineageStyle
style = LineageStyle(node_width=4.0, node_height=2.0, verbose=2)
ctx.plot_lineage('df_paired', kind='plotly', style=style)
```

### 4. 配置管理

```python
# 查看可用配置选项
ctx.list_plugin_configs()
ctx.list_plugin_configs('waveforms')  # 特定插件

# 查看当前配置
ctx.show_config()
ctx.show_config('waveforms')

# 设置配置
ctx.set_config({'daq_adapter': 'vx2730', 'threshold': 50})

# 插件特定配置（推荐，避免冲突）
ctx.set_config({'height_range': (0, None)}, plugin_name='basic_features')
```

### 6. 预览执行计划

在执行前预览：

```python
# 预览执行计划
ctx.preview_execution('run_001', 'signal_peaks')

# 输出包含:
# - 执行计划（插件执行顺序）
# - 依赖关系树
# - 自定义配置参数
# - 缓存状态

# 不同详细程度
ctx.preview_execution('run_001', 'signal_peaks', verbose=0)  # 简洁
ctx.preview_execution('run_001', 'signal_peaks', verbose=1)  # 标准
ctx.preview_execution('run_001', 'signal_peaks', verbose=2)  # 详细

# 程序化使用
result = ctx.preview_execution('run_001', 'signal_peaks')
needs_compute = [p for p, s in result['cache_status'].items() if s['needs_compute']]
print(f"需要计算 {len(needs_compute)} 个插件")
pruned = [p for p, s in result['cache_status'].items() if s.get('pruned')]
print(f"缓存剪枝 {len(pruned)} 个插件")
```

---

## 高级场景示例

### 1. Strax 插件集成

将现有的 Strax 插件集成到 WaveformAnalysis：

```python
from waveform_analysis.core.plugins.core.adapters import (
    wrap_strax_plugin,
    create_strax_context
)

# 方式 1: 包装单个插件
adapter = wrap_strax_plugin(MyStraxPlugin)
ctx.register(adapter)

# 方式 2: 使用 Strax 风格 API
strax_ctx = create_strax_context('./data')
strax_ctx.register(MyStraxPlugin)
data = strax_ctx.get_array('run_001', 'peaks')
df = strax_ctx.get_df('run_001', ['peaks', 'hits'])

# 搜索字段
strax_ctx.search_field('time')
```

### 2. 批量导出数据

导出到多种格式：

```python
from waveform_analysis.core.data.export import DataExporter, batch_export

# 单个数据集导出
exporter = DataExporter()
exporter.export(data, 'output.parquet')  # 自动检测格式
exporter.export(data, 'output.hdf5', key='waveforms')
exporter.export(data, 'output.csv')
exporter.export(data, 'output.json')
exporter.export(data, 'output.npy')

# 批量导出多个 run
batch_export(
    ctx,
    run_ids=['run_001', 'run_002', 'run_003'],
    data_name='basic_features',
    output_dir='./exports',
    format='parquet',
    max_workers=4
)
```

### 3. 热重载插件（开发模式）

开发时自动重载插件：

```python
from waveform_analysis.core.plugins.core.hot_reload import enable_hot_reload

# 启用自动重载
reloader = enable_hot_reload(
    ctx,
    plugin_names=['my_plugin'],
    auto_reload=True,
    interval=2.0  # 每 2 秒检查
)

# 手动重载
reloader.reload_plugin('my_plugin', clear_cache=True)

# 禁用自动重载
reloader.disable_auto_reload()
```

### 4. 性能分析

启用性能统计：

```python
# 启用统计收集
ctx = Context(enable_stats=True, stats_mode='detailed')

# 执行操作
basic_features = ctx.get_data('run_001', 'basic_features')
df = ctx.get_data('run_001', 'dataframe')

# 查看性能报告
print(ctx.get_performance_report())

# 获取详细统计
stats = ctx.stats_collector.get_summary()
for plugin_name, plugin_stats in stats.items():
    print(f"{plugin_name}: {plugin_stats['total_time']:.2f}s")
```

### 5. 信号处理

使用信号处理插件：

```python
from waveform_analysis.core.plugins.builtin.cpu import (
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)

# 注册信号处理插件
ctx.register(FilteredWaveformsPlugin())
ctx.register(SignalPeaksPlugin())

# 配置滤波器
ctx.set_config({
    'filter_type': 'butterworth',
    'lowcut': 1e6,
    'highcut': 10e6,
    'order': 4,
}, plugin_name='filtered_waveforms')

# 配置寻峰
ctx.set_config({
    'height': 10.0,
    'distance': 5,
    'prominence': 5.0,
}, plugin_name='signal_peaks')

# 获取处理结果
filtered = ctx.get_data('run_001', 'filtered_waveforms')
peaks = ctx.get_data('run_001', 'signal_peaks')
```

---

## 完整示例程序

项目 `examples/` 目录包含更多完整示例：

| 文件 | 说明 |
|------|------|
| `examples/config_management_example.py` | 配置管理示例 |
| `examples/signal_processing_example.py` | 信号处理示例 |
| `examples/streaming_plugins_demo.py` | 流式插件演示 |
| `examples/preview_quickstart.md` | 预览工具快速指南 |

### 运行示例

```bash
# 配置管理示例
python examples/config_management_example.py

# 流式插件演示
python examples/streaming_plugins_demo.py
```

---

## 常见问题

### Q1: 如何查看所有可用的数据类型？

```python
ctx.list_provided_data()
# ['raw_files', 'waveforms', 'st_waveforms', 'basic_features', ...]
```

### Q2: 如何清除缓存？

```python
# 清除特定数据的缓存
ctx.clear_cache('run_001', 'basic_features')

# 清除所有缓存
import shutil
shutil.rmtree('./strax_data')
```

### Q3: 如何查看插件依赖关系？

```python
# 打印依赖树
ctx.print_dependency_tree('df_paired')

# 可视化
ctx.plot_lineage('df_paired', kind='labview')
```

### Q4: 如何调试插件执行？

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 使用预览模式
ctx.preview_execution('run_001', 'basic_features', verbose=2)
```

### Q5: 数据文件找不到怎么办？

检查以下设置：

```python
# 确认 data_root 配置正确
ctx.show_config()

# 默认路径是 DAQ/<run_name>
# 确保目录结构正确
```

---

## 🔗 相关资源

- [快速开始](QUICKSTART_GUIDE.md) - 入门教程
- [配置管理](../features/context/CONFIGURATION.md) - 详细配置说明
- [插件教程](../features/plugin/SIMPLE_PLUGIN_GUIDE.md) - 自定义插件开发
- [API 参考](../api/README.md) - API 文档

---

**快速链接**:
[快速开始](QUICKSTART_GUIDE.md) |
[配置管理](../features/context/CONFIGURATION.md) |
[血缘可视化](../features/context/LINEAGE_VISUALIZATION_GUIDE.md)
