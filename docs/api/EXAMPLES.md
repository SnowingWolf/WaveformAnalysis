# API 使用示例

**导航**: [文档中心](../README.md) > [API 参考](README.md) > 使用示例

本文档提供 WaveformAnalysis 常见使用场景的完整代码示例。

---

## 目录

- [基础使用](#基础使用)
- [数据访问](#数据访问)
- [插件开发](#插件开发)
- [流式处理](#流式处理)
- [并行处理](#并行处理)
- [自定义存储](#自定义存储)
- [高级用法](#高级用法)

---

## 基础使用

### 示例 1: 快速开始

```python
from waveform_analysis import Context

# 创建 Context
ctx = Context(
    storage_dir='./strax_data',
    auto_discover_plugins=True
)

# 获取数据
records = ctx.get_array(run_id='run_001', targets='records')
print(f"获取到 {len(records)} 条 records")

# 获取 DataFrame
df = ctx.get_df(run_id='run_001', targets='basic_features')
print(df.head())
```

### 示例 2: 配置管理

```python
from waveform_analysis import Context

# 创建带配置的 Context
ctx = Context(
    storage_dir='./strax_data',
    config={
        'sample_rate': 1000,  # 采样率 1 kHz
        'baseline_samples': 100,  # 基线样本数
        'hit_threshold': 50  # hit 检测阈值
    }
)

# 动态修改配置
ctx.set_config({
    'hit_threshold': 100  # 提高阈值
})

# 获取配置
print(f"当前阈值: {ctx.config['hit_threshold']}")
```

---

## 数据访问

### 示例 3: 时间范围查询

```python
from waveform_analysis import Context

ctx = Context(storage_dir='./strax_data')

# 相对时间查询（秒）
records = ctx.get_array(
    run_id='run_001',
    targets='records',
    time_range=(0, 100)  # 前 100 秒
)

# 绝对时间查询（纳秒）
start_ns = 1234567890000000000
end_ns = start_ns + 100_000_000_000  # +100 秒
records = ctx.get_array(
    run_id='run_001',
    targets='records',
    time_range=(start_ns, end_ns),
    time_selection='absolute'
)

print(f"时间范围: {records['time'].min()} - {records['time'].max()}")
```

### 示例 4: 多数据类型获取

```python
from waveform_analysis import Context

ctx = Context(storage_dir='./strax_data')

# 获取多个数据类型
data = ctx.get_array(
    run_id='run_001',
    targets=['records', 'hits', 'basic_features']
)

# 访问各个数据类型
records = data['records']
hits = data['hits']
features = data['basic_features']

print(f"Records: {len(records)}")
print(f"Hits: {len(hits)}")
print(f"Features: {len(features)}")
```

### 示例 5: 字段搜索

```python
from waveform_analysis import Context

ctx = Context(storage_dir='./strax_data')

# 搜索包含 "time" 的字段
time_fields = ctx.search_field('time')
print("时间相关字段:", time_fields)

# 搜索包含 "area" 的字段
area_fields = ctx.search_field('area')
print("面积相关字段:", area_fields)
```

---

## 插件开发

### 示例 6: 简单插件

```python
from waveform_analysis import Plugin, Option
import numpy as np

class SimpleThresholdPlugin(Plugin):
    """简单的阈值检测插件"""

    # 定义依赖
    depends_on = ('records',)

    # 定义提供的数据类型
    provides = 'simple_hits'

    # 定义输出 dtype
    dtype = [
        ('time', np.int64, 'Hit 起始时间 (ns)'),
        ('endtime', np.int64, 'Hit 结束时间 (ns)'),
        ('channel', np.int16, '通道号'),
        ('area', np.float32, '积分面积'),
        ('height', np.float32, '峰值高度')
    ]

    # 定义配置选项
    threshold = Option(
        default=50,
        help='检测阈值（ADC 单位）'
    )

    def compute(self, records):
        """检测超过阈值的信号"""
        hits = []

        for record in records:
            # 找到超过阈值的区域
            above_threshold = record['data'] > self.config['threshold']

            if np.any(above_threshold):
                # 计算 hit 属性
                start_idx = np.argmax(above_threshold)
                end_idx = len(record['data']) - np.argmax(above_threshold[::-1])

                hit_data = record['data'][start_idx:end_idx]

                hits.append({
                    'time': record['time'] + start_idx,
                    'endtime': record['time'] + end_idx,
                    'channel': record['channel'],
                    'area': np.sum(hit_data),
                    'height': np.max(hit_data)
                })

        return np.array(hits, dtype=self.dtype)

# 使用插件
from waveform_analysis import Context

ctx = Context(storage_dir='./strax_data')
ctx.register(SimpleThresholdPlugin)

# 获取数据
hits = ctx.get_array(
    run_id='run_001',
    targets='simple_hits',
    config={'threshold': 100}
)
print(f"检测到 {len(hits)} 个 hits")
```

### 示例 7: 多依赖插件

```python
from waveform_analysis import Plugin
import numpy as np

class HitPairingPlugin(Plugin):
    """配对两个通道的 hits"""

    depends_on = ('hits', 'basic_features')
    provides = 'paired_hits'

    dtype = [
        ('time', np.int64, '配对时间'),
        ('ch0_area', np.float32, '通道 0 面积'),
        ('ch1_area', np.float32, '通道 1 面积'),
        ('time_diff', np.float32, '时间差 (ns)')
    ]

    time_window = Option(
        default=1000,
        help='配对时间窗口 (ns)'
    )

    def compute(self, hits, basic_features):
        """配对逻辑"""
        paired = []

        # 分离通道
        ch0_hits = hits[hits['channel'] == 0]
        ch1_hits = hits[hits['channel'] == 1]

        # 配对
        for h0 in ch0_hits:
            # 找到时间窗口内的 ch1 hits
            time_diff = ch1_hits['time'] - h0['time']
            in_window = np.abs(time_diff) < self.config['time_window']

            if np.any(in_window):
                h1 = ch1_hits[in_window][0]
                paired.append({
                    'time': h0['time'],
                    'ch0_area': h0['area'],
                    'ch1_area': h1['area'],
                    'time_diff': h1['time'] - h0['time']
                })

        return np.array(paired, dtype=self.dtype)
```

### 示例 8: 带初始化的插件

```python
from waveform_analysis import Plugin, Option
import numpy as np

class FilteredPlugin(Plugin):
    """带滤波器初始化的插件"""

    depends_on = ('records',)
    provides = 'filtered_records'

    dtype = [
        ('time', np.int64),
        ('channel', np.int16),
        ('data', np.float32, 1000)
    ]

    filter_order = Option(default=4, help='滤波器阶数')
    cutoff_freq = Option(default=100, help='截止频率 (Hz)')

    def setup(self):
        """初始化滤波器"""
        from scipy import signal

        # 设计 Butterworth 滤波器
        self.filter_b, self.filter_a = signal.butter(
            self.config['filter_order'],
            self.config['cutoff_freq'],
            fs=self.config['sample_rate'],
            btype='low'
        )

        print(f"滤波器初始化完成: order={self.config['filter_order']}, "
              f"cutoff={self.config['cutoff_freq']} Hz")

    def compute(self, records):
        """应用滤波器"""
        from scipy import signal

        filtered = np.zeros(len(records), dtype=self.dtype)

        for i, record in enumerate(records):
            # 应用滤波器
            filtered_data = signal.filtfilt(
                self.filter_b,
                self.filter_a,
                record['data']
            )

            filtered[i]['time'] = record['time']
            filtered[i]['channel'] = record['channel']
            filtered[i]['data'] = filtered_data

        return filtered
```

---

## 流式处理

### 示例 9: 迭代器处理大数据集

```python
from waveform_analysis import Context

ctx = Context(storage_dir='./strax_data')

# 使用迭代器逐块处理
total_hits = 0
for chunk in ctx.get_iter(run_id='run_001', targets='hits'):
    # 处理每个 chunk
    total_hits += len(chunk)

    # 示例：统计每个通道的 hits
    for channel in np.unique(chunk['channel']):
        ch_hits = chunk[chunk['channel'] == channel]
        print(f"通道 {channel}: {len(ch_hits)} hits")

print(f"总计: {total_hits} hits")
```

### 示例 10: StreamingPlugin

```python
from waveform_analysis import StreamingPlugin
import numpy as np

class StreamingAveragePlugin(StreamingPlugin):
    """流式计算平均值"""

    depends_on = ('records',)
    provides = 'streaming_average'

    dtype = [
        ('time', np.int64),
        ('channel', np.int16),
        ('average', np.float32)
    ]

    def compute_chunk(self, records_chunk):
        """处理单个 chunk"""
        result = []

        for channel in np.unique(records_chunk['channel']):
            ch_records = records_chunk[records_chunk['channel'] == channel]

            for record in ch_records:
                result.append({
                    'time': record['time'],
                    'channel': record['channel'],
                    'average': np.mean(record['data'])
                })

        return np.array(result, dtype=self.dtype)

# 使用流式插件
ctx = Context(storage_dir='./strax_data')
ctx.register(StreamingAveragePlugin)

# 流式获取数据
for chunk in ctx.get_iter(run_id='run_001', targets='streaming_average'):
    print(f"处理了 {len(chunk)} 条记录")
```

---

## 并行处理

### 示例 11: 并行映射

```python
from waveform_analysis import parallel_map
import numpy as np

def process_waveform(waveform):
    """处理单个波形"""
    # 计算特征
    return {
        'mean': np.mean(waveform),
        'std': np.std(waveform),
        'max': np.max(waveform),
        'min': np.min(waveform)
    }

# 准备数据
waveforms = [np.random.randn(1000) for _ in range(100)]

# 并行处理
results = parallel_map(
    func=process_waveform,
    items=waveforms,
    max_workers=4,
    desc="处理波形"
)

print(f"处理了 {len(results)} 个波形")
print(f"平均值范围: {min(r['mean'] for r in results):.2f} - "
      f"{max(r['mean'] for r in results):.2f}")
```

### 示例 12: 自定义执行器

```python
from waveform_analysis import get_executor
import time

# 获取线程池执行器
executor = get_executor(executor_type='thread', max_workers=4)

def slow_task(x):
    time.sleep(0.1)
    return x ** 2

# 提交任务
futures = [executor.submit(slow_task, i) for i in range(10)]

# 获取结果
results = [f.result() for f in futures]
print(f"结果: {results}")

# 关闭执行器
executor.shutdown()
```

---

## 自定义存储

### 示例 13: 自定义存储后端

```python
from waveform_analysis import StorageBackend, Context
import numpy as np
import os

class CustomStorage(StorageBackend):
    """自定义存储后端示例"""

    def __init__(self, base_dir):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def save(self, run_id, data_type, data):
        """保存数据"""
        path = os.path.join(self.base_dir, f"{run_id}_{data_type}.npy")
        np.save(path, data)
        print(f"保存到: {path}")

    def load(self, run_id, data_type):
        """加载数据"""
        path = os.path.join(self.base_dir, f"{run_id}_{data_type}.npy")
        if os.path.exists(path):
            return np.load(path)
        return None

    def exists(self, run_id, data_type):
        """检查数据是否存在"""
        path = os.path.join(self.base_dir, f"{run_id}_{data_type}.npy")
        return os.path.exists(path)

    def delete(self, run_id, data_type):
        """删除数据"""
        path = os.path.join(self.base_dir, f"{run_id}_{data_type}.npy")
        if os.path.exists(path):
            os.remove(path)

# 使用自定义存储
storage = CustomStorage(base_dir='./custom_storage')
ctx = Context(storage=storage)

# 正常使用
data = ctx.get_array(run_id='run_001', targets='records')
```

---

## 高级用法

### 示例 14: 插件热重载

```python
from waveform_analysis import Context, enable_hot_reload

# 启用热重载
ctx = Context(storage_dir='./strax_data')
enable_hot_reload(ctx, watch_dirs=['./my_plugins'])

# 修改插件文件后，自动重新加载
# 无需重启程序
```

### 示例 15: 依赖分析

```python
from waveform_analysis import Context

ctx = Context(storage_dir='./strax_data')

# 获取依赖树
deps = ctx.get_dependency_tree('basic_features')
print("依赖树:")
for level, plugins in enumerate(deps):
    print(f"  Level {level}: {plugins}")

# 获取所有可用数据类型
available = ctx.list_available_data_types()
print(f"可用数据类型: {available}")
```

### 示例 16: 批量处理多个 runs

```python
from waveform_analysis import Context, parallel_map

ctx = Context(storage_dir='./strax_data')

def process_run(run_id):
    """处理单个 run"""
    try:
        data = ctx.get_df(run_id=run_id, targets='basic_features')
        return {
            'run_id': run_id,
            'n_events': len(data),
            'total_area': data['area'].sum(),
            'status': 'success'
        }
    except Exception as e:
        return {
            'run_id': run_id,
            'status': 'failed',
            'error': str(e)
        }

# 批量处理
run_ids = ['run_001', 'run_002', 'run_003', 'run_004']
results = parallel_map(
    func=process_run,
    items=run_ids,
    max_workers=2,
    desc="处理 runs"
)

# 汇总结果
for result in results:
    if result['status'] == 'success':
        print(f"{result['run_id']}: {result['n_events']} events, "
              f"total area = {result['total_area']:.2e}")
    else:
        print(f"{result['run_id']}: 失败 - {result['error']}")
```

### 示例 17: 错误处理

```python
from waveform_analysis import Context, PluginError, ErrorSeverity

ctx = Context(storage_dir='./strax_data')

try:
    data = ctx.get_array(run_id='run_001', targets='records')
except PluginError as e:
    print(f"插件错误: {e.message}")
    print(f"严重程度: {e.severity}")

    if e.severity == ErrorSeverity.WARNING:
        print("警告，继续处理")
    elif e.severity == ErrorSeverity.ERROR:
        print("错误，停止处理")
    elif e.severity == ErrorSeverity.CRITICAL:
        print("严重错误，需要人工介入")

    # 打印上下文信息
    if e.context:
        print(f"插件: {e.context.plugin_name}")
        print(f"Run ID: {e.context.run_id}")
        print(f"数据类型: {e.context.data_type}")
except Exception as e:
    print(f"未知错误: {e}")
```

### 示例 18: 性能分析

```python
from waveform_analysis import Context
import time

ctx = Context(
    storage_dir='./strax_data',
    enable_stats=True,  # 启用统计
    stats_mode='detailed'  # 详细模式
)

# 执行操作
start = time.time()
data = ctx.get_array(run_id='run_001', targets='basic_features')
elapsed = time.time() - start

print(f"处理时间: {elapsed:.2f} 秒")
print(f"数据量: {len(data)} 条记录")
print(f"吞吐量: {len(data) / elapsed:.0f} 记录/秒")

# 获取统计信息
stats = ctx.get_stats()
print("\n性能统计:")
for plugin, plugin_stats in stats.items():
    print(f"  {plugin}:")
    print(f"    执行时间: {plugin_stats['compute_time']:.3f} 秒")
    print(f"    缓存命中: {plugin_stats['cache_hits']}")
    print(f"    缓存未命中: {plugin_stats['cache_misses']}")
```

---

## 完整示例：端到端分析流程

```python
from waveform_analysis import Context, Plugin, Option
import numpy as np
import matplotlib.pyplot as plt

# 1. 创建 Context
ctx = Context(
    storage_dir='./strax_data',
    config={
        'sample_rate': 1000,
        'baseline_samples': 100
    },
    auto_discover_plugins=True,
    enable_stats=True
)

# 2. 获取原始数据
records = ctx.get_array(
    run_id='run_001',
    targets='records',
    time_range=(0, 60)  # 前 60 秒
)
print(f"获取到 {len(records)} 条 records")

# 3. 获取处理后的数据
hits = ctx.get_df(run_id='run_001', targets='hits')
features = ctx.get_df(run_id='run_001', targets='basic_features')

print(f"检测到 {len(hits)} 个 hits")
print(f"提取了 {len(features)} 个特征")

# 4. 数据分析
print("\n基础统计:")
print(f"  平均面积: {features['area'].mean():.2f}")
print(f"  平均高度: {features['height'].mean():.2f}")
print(f"  平均宽度: {features['width'].mean():.2f}")

# 5. 可视化
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# 面积分布
axes[0, 0].hist(features['area'], bins=50)
axes[0, 0].set_xlabel('Area')
axes[0, 0].set_ylabel('Count')
axes[0, 0].set_title('Area Distribution')

# 高度分布
axes[0, 1].hist(features['height'], bins=50)
axes[0, 1].set_xlabel('Height')
axes[0, 1].set_ylabel('Count')
axes[0, 1].set_title('Height Distribution')

# 面积 vs 高度
axes[1, 0].scatter(features['area'], features['height'], alpha=0.5)
axes[1, 0].set_xlabel('Area')
axes[1, 0].set_ylabel('Height')
axes[1, 0].set_title('Area vs Height')

# 时间分布
axes[1, 1].hist(features['time'] / 1e9, bins=50)  # 转换为秒
axes[1, 1].set_xlabel('Time (s)')
axes[1, 1].set_ylabel('Count')
axes[1, 1].set_title('Event Rate')

plt.tight_layout()
plt.savefig('analysis_results.png', dpi=150)
print("\n结果已保存到 analysis_results.png")

# 6. 性能统计
stats = ctx.get_stats()
print("\n性能统计:")
for plugin, plugin_stats in stats.items():
    print(f"  {plugin}: {plugin_stats['compute_time']:.3f} 秒")
```

---

## 相关资源

- [API 快速参考](QUICK_REFERENCE.md) - API 速查表
- [插件开发教程](../plugins/tutorials/SIMPLE_PLUGIN_GUIDE.md) - 从零开始
- [配置管理](../features/context/CONFIGURATION.md) - 配置系统详解
- [快速开始](../user-guide/QUICKSTART_GUIDE.md) - 基础使用指南
