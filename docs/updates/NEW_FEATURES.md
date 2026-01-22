**导航**: [文档中心](../README.md) > [更新记录](README.md) > 新功能文档

---

# 新功能文档 (Phase 2 & 3)

本文档描述WaveformAnalysis框架Phase 2和Phase 3新增的高级功能。

---

## 目录

- [Phase 2: 核心增强](#phase-2-核心增强)
  - [2.1 插件性能统计和监控](#21-插件性能统计和监控)
  - [2.2 数据时间范围查询优化](#22-数据时间范围查询优化)
  - [2.3 Strax插件适配器](#23-strax插件适配器)
  - [2.4 时间字段统一方案](#24-时间字段统一方案)
- [Phase 3: 高级功能](#phase-3-高级功能)
  - [3.1 多运行批量处理](#31-多运行批量处理)
  - [3.2 数据导出统一接口](#32-数据导出统一接口)
  - [3.3 插件热重载](#33-插件热重载)

---

## Phase 2: 核心增强

### 2.1 插件性能统计和监控

**状态:** ✅ 已完成（在之前的开发中）

**模块:** `waveform_analysis.core.plugin_stats`

**功能:**
- 执行时间统计
- 内存使用监控
- 缓存命中率
- 调用计数和失败统计
- 自动日志记录

**使用示例:**
```python
from waveform_analysis.core.context import Context

# 创建Context时启用统计
ctx = Context(
    enable_stats=True,
    stats_mode='detailed',  # 'off', 'basic', or 'detailed'
    stats_log_file='./logs/plugins.log'
)

# 正常使用Context
data = ctx.get_data('run_001', 'peaks')

# 获取统计信息
if ctx.stats_collector:
    stats = ctx.stats_collector.get_statistics('peaks')
    print(f"Cache hit rate: {stats['peaks'].cache_hit_rate():.1%}")
    print(f"Average time: {stats['peaks'].mean_time:.3f}s")

    # 生成报告
    report = ctx.stats_collector.generate_report(format='text')
    print(report)
```

---

### 2.2 数据时间范围查询优化

**状态:** ✅ 新实现

**模块:** `waveform_analysis.core.time_range_query`

**核心类:**
- `TimeIndex`: 高效时间索引（二分查找，O(log n)复杂度）
- `TimeRangeQueryEngine`: 索引管理器
- `TimeRangeCache`: 查询结果缓存

**功能特性:**
- 快速时间范围查询
- 自动索引构建
- 结果缓存
- 支持endtime计算
- 时间点查询和范围查询

**使用示例:**

#### 基础查询
```python
from waveform_analysis.core.context import Context

ctx = Context()
# ... 注册插件和配置 ...

# 查询特定时间范围（默认使用 time 字段，ns）
data = ctx.get_data_time_range(
    'run_001',
    'st_waveforms',
    start_time=1000000,  # 起始时间（包含）
    end_time=2000000     # 结束时间（不包含）
)

print(f"Found {len(data)} records in time range")
```

#### 预构建索引
```python
# 预先构建索引以提高性能（如需按 timestamp 查询，显式指定 time_field='timestamp'）
ctx.build_time_index(
    'run_001',
    'st_waveforms',
    time_field='time',
    endtime_field='computed',  # 'computed'表示从dt*length计算
    force_rebuild=False
)

# 后续查询会使用索引，速度更快
data = ctx.get_data_time_range('run_001', 'st_waveforms', start_time=5000000)
```

#### 索引管理
```python
# 获取索引统计信息
stats = ctx.get_time_index_stats()
print(f"Total indices: {stats['total_indices']}")
for key, info in stats['indices'].items():
    print(f"{key}: {info['n_records']} records, "
          f"range [{info['time_range'][0]}, {info['time_range'][1]}]")

# 清除索引
ctx.clear_time_index('run_001', 'st_waveforms')  # 清除特定索引
ctx.clear_time_index('run_001')  # 清除该run的所有索引
ctx.clear_time_index()  # 清除所有索引
```

#### 性能对比
```python
import time

# 不使用索引（直接过滤）
start = time.time()
data1 = ctx.get_data('run_001', 'st_waveforms')
mask = (data1['time'] >= 1000000) & (data1['time'] < 2000000)
filtered = data1[mask]
print(f"Direct filtering: {time.time() - start:.3f}s")

# 使用索引
ctx.build_time_index('run_001', 'st_waveforms')
start = time.time()
data2 = ctx.get_data_time_range('run_001', 'st_waveforms', 1000000, 2000000)
print(f"Index query: {time.time() - start:.3f}s")
```

**性能优势:**
- 查询复杂度: O(log n)（二分查找）vs O(n)（直接过滤）
- 大数据集上性能提升显著
- 结果缓存避免重复查询

---

### 2.3 Strax插件适配器

**状态:** ✅ 新实现

**模块:** `waveform_analysis.core.strax_adapter`

**核心类:**
- `StraxPluginAdapter`: strax插件包装器
- `StraxContextAdapter`: strax风格API适配器

**功能特性:**
- 无缝集成现有strax插件
- 自动元数据提取
- 配置选项兼容
- 智能参数映射
- strax风格API支持

**使用示例:**

#### 包装strax插件
```python
from waveform_analysis.core.strax_adapter import wrap_strax_plugin
from waveform_analysis.core.context import Context

# 假设有一个strax插件
class MyStraxPlugin:
    provides = 'my_data'
    depends_on = ('raw_records',)
    dtype = [('time', 'i8'), ('value', 'f4')]
    __version__ = '1.0.0'

    def compute(self, raw_records):
        # strax插件的处理逻辑
        return processed_data

# 包装并注册
ctx = Context()
adapter = wrap_strax_plugin(MyStraxPlugin)
ctx.register_plugin(adapter)

# 正常使用
data = ctx.get_data('run_001', 'my_data')
```

#### 使用strax风格API
```python
from waveform_analysis.core.strax_adapter import create_strax_context

# 创建strax兼容的context
strax_ctx = create_strax_context('./data')

# 注册strax插件
strax_ctx.register(MyStraxPlugin)
strax_ctx.register(AnotherStraxPlugin)

# 使用strax风格的API
# get_array - 获取numpy数组
peaks = strax_ctx.get_array('run_001', 'peaks')
multi_data = strax_ctx.get_array('run_001', ['peaks', 'hits'])

# get_df - 获取DataFrame
df = strax_ctx.get_df('run_001', 'peaks')
multi_df = strax_ctx.get_df('run_001', ['peaks', 'hits'])

# 设置配置
strax_ctx.set_config({'peak_threshold': 50.0})

# 搜索字段
results = strax_ctx.search_field('peak')  # 查找包含'peak'的数据
```

#### 配置映射
```python
# strax插件的配置会自动映射
class StraxPluginWithConfig:
    provides = 'processed_data'
    depends_on = ('raw_data',)
    takes_config = [
        ('threshold', 10.0),
        'baseline_samples',  # 默认值为None
    ]

    def compute(self, raw_data, threshold=10.0):
        # 使用配置
        return processed

# 包装后，配置会正确传递
adapter = wrap_strax_plugin(StraxPluginWithConfig)
ctx.register_plugin(adapter)
ctx.set_config({'threshold': 20.0})
data = ctx.get_data('run_001', 'processed_data')  # 使用threshold=20.0
```

---

### 2.4 时间字段统一方案

**状态:** ✅ 新实现

**核心变化:**
- `RECORD_DTYPE` 新增 `time` 字段（绝对时间，ns），`timestamp` 统一为 ps
- 时间转换公式：`time = epoch_ns + timestamp // 1000`
- `st_waveforms.timestamp` 按 `FormatSpec.timestamp_unit` 统一转换为 ps
- 流式处理默认 `time_field="timestamp"`，断点阈值使用 `break_threshold_ps`

**使用示例:**
```python
st_waveforms = ctx.get_data('run_001', 'st_waveforms')
print(st_waveforms[0]['timestamp'][0])  # ps
print(st_waveforms[0]['time'][0])       # ns
```

更多细节请参考 [TIME_FIELD_UNIFICATION.md](../features/core/TIME_FIELD_UNIFICATION.md)。

---

## Phase 3: 高级功能

### 3.1 多运行批量处理

**状态:** ✅ 新实现

**模块:** `waveform_analysis.core.batch_export`

**核心类:**
- `BatchProcessor`: 批量处理器

**功能特性:**
- 并行/串行处理
- 进度跟踪
- 灵活的错误处理
- 自定义处理函数

**使用示例:**

#### 基础批量处理
```python
from waveform_analysis.core.batch_export import BatchProcessor
from waveform_analysis.core.context import Context

ctx = Context()
# ... 注册插件 ...

processor = BatchProcessor(ctx)

# 批量处理多个run
results = processor.process_runs(
    run_ids=['run_001', 'run_002', 'run_003'],
    data_name='peaks',
    max_workers=4,        # 并行度
    show_progress=True,   # 显示进度
    on_error='continue'   # 错误处理: 'continue', 'stop', 'raise'
)

# 访问结果
print(f"Successful: {len(results['results'])}")
print(f"Failed: {len(results['errors'])}")

for run_id, data in results['results'].items():
    print(f"{run_id}: {len(data)} events")

# 检查错误
for run_id, error in results['errors'].items():
    print(f"{run_id} failed: {error}")
```

#### 自定义处理函数
```python
def custom_process(ctx, run_id):
    """自定义处理逻辑"""
    # 获取数据
    peaks = ctx.get_data(run_id, 'peaks')
    hits = ctx.get_data(run_id, 'hits')

    # 自定义处理
    result = {
        'n_peaks': len(peaks),
        'n_hits': len(hits),
        'peak_areas': peaks['area'].sum(),
    }
    return result

# 批量执行自定义函数
results = processor.process_with_custom_func(
    run_ids=['run_001', 'run_002'],
    func=custom_process,
    max_workers=2,
    show_progress=True
)

# 结果是字典
for run_id, result in results.items():
    print(f"{run_id}: {result['n_peaks']} peaks, {result['n_hits']} hits")
```

#### 串行 vs 并行
```python
# 串行处理（调试时有用）
results_serial = processor.process_runs(
    run_ids=run_ids,
    data_name='peaks',
    max_workers=1  # 串行
)

# 并行处理（生产环境）
results_parallel = processor.process_runs(
    run_ids=run_ids,
    data_name='peaks',
    max_workers=None  # 使用默认线程数
)
```

---

### 3.2 数据导出统一接口

**状态:** ✅ 新实现

**模块:** `waveform_analysis.core.batch_export`

**核心类:**
- `DataExporter`: 统一导出器

**支持格式:**
- `parquet`: Apache Parquet（推荐，高性能）
- `hdf5/h5`: HDF5格式
- `csv`: CSV文本格式
- `json`: JSON格式
- `npy`: NumPy二进制格式
- `npz`: NumPy压缩格式

**使用示例:**

#### 单文件导出
```python
from waveform_analysis.core.batch_export import DataExporter
import numpy as np
import pandas as pd

exporter = DataExporter()

# 导出DataFrame
df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
exporter.export(df, 'output.parquet')  # 自动推断格式
exporter.export(df, 'output.csv')
exporter.export(df, 'output.json')

# 导出NumPy数组
data = np.array([1, 2, 3, 4, 5])
exporter.export(data, 'output.npy')

# 导出结构化数组
structured_data = np.zeros(10, dtype=[('time', 'i8'), ('value', 'f4')])
exporter.export(structured_data, 'output.parquet')

# 导出字典
data_dict = {'array1': np.array([1, 2, 3]), 'array2': np.array([4, 5, 6])}
exporter.export(data_dict, 'output.npz')
```

#### 格式特定选项
```python
# Parquet with compression
exporter.export(df, 'output.parquet', compression='snappy')

# HDF5 with custom key
exporter.export(df, 'output.hdf5', key='my_data')

# CSV with custom delimiter
exporter.export(df, 'output.csv', sep='\t')

# JSON with indentation
exporter.export(df, 'output.json', indent=2)
```

#### 批量导出
```python
from waveform_analysis.core.batch_export import batch_export

# 批量导出多个run的数据
batch_export(
    ctx,
    run_ids=['run_001', 'run_002', 'run_003'],
    data_name='peaks',
    output_dir='./exports',
    format='parquet',
    max_workers=4
)

# 输出文件:
# ./exports/run_001_peaks.parquet
# ./exports/run_002_peaks.parquet
# ./exports/run_003_peaks.parquet
```

#### 完整工作流
```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.batch_export import BatchProcessor, DataExporter

ctx = Context()
processor = BatchProcessor(ctx)
exporter = DataExporter()

# 1. 批量处理
run_ids = ['run_001', 'run_002', 'run_003']
results = processor.process_runs(run_ids, 'peaks', max_workers=4)

# 2. 导出每个结果
import os
os.makedirs('./exports', exist_ok=True)

for run_id, data in results['results'].items():
    output_path = f'./exports/{run_id}_peaks.parquet'
    exporter.export(data, output_path)
    print(f"Exported {run_id} to {output_path}")
```

---

### 3.3 插件热重载

**状态:** ✅ 新实现

**模块:** `waveform_analysis.core.hot_reload`

**核心类:**
- `PluginHotReloader`: 热重载管理器

**功能特性:**
- 文件变化监控（mtime + MD5）
- 自动模块重载
- 缓存一致性维护
- 守护线程自动检查

**使用示例:**

#### 快速启用
```python
from waveform_analysis.core.hot_reload import enable_hot_reload
from waveform_analysis.core.context import Context

ctx = Context()
# ... 注册插件 ...

# 启用自动热重载
reloader = enable_hot_reload(
    ctx,
    plugin_names=['my_plugin'],  # None表示所有插件
    auto_reload=True,
    interval=2.0  # 每2秒检查一次
)

# 现在修改插件文件，会自动重载！
```

#### 手动控制
```python
from waveform_analysis.core.hot_reload import PluginHotReloader

reloader = PluginHotReloader(ctx)

# 添加插件到监控
reloader.watch_plugin('my_plugin', plugin_path='./my_plugin.py')

# 检查更新
updated = reloader.check_updates()
if updated:
    print(f"Updated plugins: {updated}")

# 手动重载
reloader.reload_plugin('my_plugin', clear_cache=True)

# 重载所有有更新的插件
reloader.reload_all_updated(clear_cache=True)
```

#### 开发工作流
```python
# 1. 启动开发环境
ctx = Context()
ctx.register_plugin(MyPlugin())

reloader = enable_hot_reload(
    ctx,
    plugin_names=['my_plugin'],
    auto_reload=True,
    interval=1.0  # 快速响应
)

# 2. 修改插件文件
# 编辑 my_plugin.py ...

# 3. 插件会自动重载，缓存会清除

# 4. 测试新功能
data = ctx.get_data('run_001', 'my_plugin')  # 使用新代码

# 5. 完成后禁用
reloader.disable_auto_reload()
```

#### 生产环境注意事项
```python
# ⚠️ 热重载仅用于开发！
# 生产环境应该禁用

import os

if os.getenv('ENV') == 'development':
    enable_hot_reload(ctx, auto_reload=True)
else:
    # 生产环境：不启用热重载
    pass
```

---

## 性能建议

### 时间范围查询
- 对于频繁查询的数据，预先构建索引
- 使用`endtime_field='computed'`可以支持范围查询
- 索引会占用额外内存，按需构建

### 批量处理
- 根据任务类型选择合适的`max_workers`
  - I/O密集: 更多workers（4-8）
  - CPU密集: workers ≈ CPU核心数
  - 内存受限: 减少workers
- 使用`on_error='continue'`避免单个失败影响整体

### 数据导出
- Parquet格式最快，最节省空间
- CSV适合人类阅读和导入其他工具
- HDF5适合大型数组和科学计算
- NumPy格式最快，但缺乏元数据

### 热重载
- 仅在开发时使用
- 较大项目设置较长的检查间隔
- 重载后测试功能是否正常

---

## 常见问题

### Q: 时间范围查询比直接过滤慢？
A: 首次查询需要构建索引，之后会快很多。使用`build_time_index()`预先构建。

### Q: Strax插件无法注册？
A: 确保插件有`provides`和`compute`方法。使用`adapter.is_compatible()`检查兼容性。

### Q: 批量处理中途失败？
A: 使用`on_error='continue'`继续处理其他run，在`results['errors']`中查看失败原因。

### Q: 导出的文件太大？
A: 使用Parquet格式并启用压缩：`exporter.export(data, 'out.parquet', compression='snappy')`

### Q: 热重载后插件行为异常？
A: 检查是否有模块级变量或单例模式。热重载只更新类定义，不重置模块状态。

---

## 下一步

- 查看`tests/test_time_range_query.py`了解时间查询的详细测试
- 查看`tests/test_strax_adapter.py`了解strax适配器的使用
- 参考`CLAUDE.md`获取完整的开发指南
- 阅读源码中的docstring获取更多细节

---

**文档版本:** 1.0.0
**最后更新:** 2026-01-09
**作者:** Claude Code
