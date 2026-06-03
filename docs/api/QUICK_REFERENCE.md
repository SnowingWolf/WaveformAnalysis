# API 快速参考

**导航**: [文档中心](../README.md) > [API 参考](README.md) > 快速参考

本文档提供 WaveformAnalysis 核心 API 的快速查找表。

---

## 核心类

### Context

数据处理的主入口，负责插件编排和数据存储/缓存管理。

```python
from waveform_analysis import Context

# 创建 Context
ctx = Context(
    storage_dir='./strax_data',  # 存储目录
    config={'some_option': value},  # 全局配置
    auto_discover_plugins=True,  # 自动发现插件
    enable_stats=True  # 启用统计
)

# 获取数据
data = ctx.get_array(run_id='run_001', targets='records')

# 获取单个数据类型
df = ctx.get_df(run_id='run_001', targets='basic_features')
```

**常用方法**：
- `get_array(run_id, targets, **kwargs)` - 获取 NumPy 数组
- `get_df(run_id, targets, **kwargs)` - 获取 Pandas DataFrame
- `get_iter(run_id, targets, **kwargs)` - 获取迭代器（流式处理）
- `register(plugin_class)` - 注册插件
- `set_config(config_dict)` - 设置配置
- `search_field(pattern)` - 搜索字段名

**详细文档**: [配置管理](../features/context/CONFIGURATION.md)

---

### Plugin

所有插件的基类，定义数据处理逻辑。

```python
from waveform_analysis import Plugin, Option
import numpy as np

class MyPlugin(Plugin):
    """自定义插件示例"""

    # 定义依赖
    depends_on = ('raw_files',)

    # 定义输出数据类型
    dtype = [
        ('time', np.int64),
        ('value', np.float32)
    ]

    # 定义配置选项
    my_option = Option(
        default=10,
        help='示例配置选项'
    )

    def compute(self, raw_files):
        """计算逻辑"""
        # 处理数据
        result = process_data(raw_files, self.config['my_option'])
        return result
```

**关键属性**：
- `depends_on` - 依赖的数据类型（tuple）
- `provides` - 提供的数据类型（str 或 tuple）
- `dtype` - 输出数据的 NumPy dtype
- `data_kind` - 数据类别（默认自动推断）

**关键方法**：
- `compute(**kwargs)` - 核心计算逻辑（必须实现）
- `setup()` - 初始化逻辑（可选）
- `infer_dtype()` - 推断输出 dtype（可选）

**详细文档**: [插件开发指南](../plugins/guides/PLUGIN_AUTHORING_GUIDE.md)

---

### Option

插件配置选项定义。

```python
from waveform_analysis import Option

# 基础选项
threshold = Option(
    default=100,
    help='阈值参数'
)

# 带类型的选项
window_size = Option(
    default=10,
    type=int,
    help='窗口大小（样本数）'
)

# 带验证的选项
sample_rate = Option(
    default=1000,
    type=float,
    help='采样率（Hz）',
    validator=lambda x: x > 0
)
```

**参数**：
- `default` - 默认值
- `type` - 类型约束（可选）
- `help` - 帮助文本
- `validator` - 验证函数（可选）

---

## 数据访问

### 基础数据获取

```python
# 获取 NumPy 数组
records = ctx.get_array(run_id='run_001', targets='records')

# 获取 DataFrame
df = ctx.get_df(run_id='run_001', targets='basic_features')

# 获取多个数据类型
data = ctx.get_array(run_id='run_001', targets=['records', 'hits'])
```

### 时间范围查询

```python
# 使用相对时间（秒）
data = ctx.get_array(
    run_id='run_001',
    targets='records',
    time_range=(0, 100)  # 前 100 秒
)

# 使用绝对时间（纳秒）
data = ctx.get_array(
    run_id='run_001',
    targets='records',
    time_range=(start_ns, end_ns),
    time_selection='absolute'
)
```

**详细文档**: [数据访问指南](../features/context/DATA_ACCESS.md)

### 流式处理

```python
# 使用迭代器处理大数据集
for chunk in ctx.get_iter(run_id='run_001', targets='records'):
    process_chunk(chunk)

# 使用 StreamingContext
from waveform_analysis import get_streaming_context

stream_ctx = get_streaming_context(ctx)
for batch in stream_ctx.stream(run_id='run_001', targets='records'):
    process_batch(batch)
```

**详细文档**: [流式插件指南](../plugins/guides/STREAMING_PLUGINS_GUIDE.md)

---

## 执行器管理

### 并行处理

```python
from waveform_analysis import parallel_map, parallel_apply

# 并行映射
results = parallel_map(
    func=process_item,
    items=data_list,
    max_workers=4
)

# 并行应用
parallel_apply(
    func=process_item,
    items=data_list,
    max_workers=4
)
```

### 执行器配置

```python
from waveform_analysis import get_executor, EXECUTOR_CONFIGS

# 获取执行器
executor = get_executor(
    executor_type='thread',
    max_workers=4
)

# 查看可用配置
print(EXECUTOR_CONFIGS)
```

**详细文档**: [执行器管理指南](../features/advanced/EXECUTOR_MANAGER_GUIDE.md)

---

## 存储与缓存

### 存储后端

```python
from waveform_analysis import Context, MemmapStorage

# 使用默认存储
ctx = Context(storage_dir='./strax_data')

# 使用自定义存储
storage = MemmapStorage(base_dir='./custom_storage')
ctx = Context(storage=storage)
```

### 缓存管理

```python
# 清理缓存
ctx.clear_cache(run_id='run_001')

# 查看缓存状态
cache_info = ctx.get_cache_info(run_id='run_001')
```

**详细文档**: [数据访问与缓存](../features/context/DATA_ACCESS.md)

---

## 工具函数

### DAQ 分析

```python
from waveform_analysis import DAQAnalyzer, DAQRun

# 分析 DAQ 文件
analyzer = DAQAnalyzer(daq_dir='./DAQ')
runs = analyzer.list_runs()

# 获取 run 信息
run = DAQRun(run_id='run_001', daq_dir='./DAQ')
print(run.get_info())
```

**详细文档**: [DAQ 分析器指南](../features/utils/DAQ_ANALYZER_GUIDE.md)

### 波形预览

```python
from waveform_analysis import preview_waveforms, plot_records_waveforms

# 预览波形
preview_waveforms(
    records=records_data,
    n_waveforms=10,
    save_path='preview.png'
)

# 绘制 records 波形
plot_records_waveforms(
    records=records_data,
    time_range=(0, 1000),
    channels=[0, 1, 2]
)
```

**详细文档**: [波形预览指南](../features/utils/waveform_preview.md)

### 事件分组

```python
from waveform_analysis import group_multi_channel_hits

# 多通道 hit 分组
grouped_hits = group_multi_channel_hits(
    hits=hits_data,
    time_window=100,  # 纳秒
    min_channels=2
)
```

**详细文档**: [事件筛选指南](../features/utils/EVENT_FILTERS_GUIDE.md)

---

## 异常处理

### 插件错误

```python
from waveform_analysis import PluginError, ErrorSeverity, ErrorContext

# 抛出插件错误
raise PluginError(
    message="处理失败",
    severity=ErrorSeverity.ERROR,
    context=ErrorContext(
        plugin_name='MyPlugin',
        run_id='run_001',
        data_type='records'
    )
)

# 捕获插件错误
try:
    data = ctx.get_array(run_id='run_001', targets='records')
except PluginError as e:
    print(f"错误: {e.message}")
    print(f"严重程度: {e.severity}")
    print(f"上下文: {e.context}")
```

---

## 配置管理

### 全局配置

```python
# 设置全局配置
ctx.set_config({
    'sample_rate': 1000,
    'baseline_samples': 100,
    'threshold': 50
})

# 获取配置
config = ctx.config
print(config['sample_rate'])
```

### 插件特定配置

```python
# 为特定插件设置配置
ctx.set_config({
    'MyPlugin.my_option': 20,
    'AnotherPlugin.threshold': 100
})
```

**详细文档**: [配置管理](../features/context/CONFIGURATION.md)

---

## 常用数据类型

### records

原始波形记录，所有处理的起点。

**字段**：
- `time` (int64) - 时间戳（纳秒）
- `length` (int32) - 波形长度（样本数）
- `channel` (int16) - 通道号
- `data` (int16, shape=(length,)) - 波形数据

### hits

检测到的信号脉冲。

**字段**：
- `time` (int64) - 起始时间（纳秒）
- `endtime` (int64) - 结束时间（纳秒）
- `channel` (int16) - 通道号
- `area` (float32) - 积分面积
- `height` (float32) - 峰值高度

### basic_features

基础波形特征。

**字段**：
- `time` (int64) - 时间戳
- `channel` (int16) - 通道号
- `area` (float32) - 面积
- `height` (float32) - 高度
- `width` (float32) - 宽度
- `rise_time` (float32) - 上升时间
- `fall_time` (float32) - 下降时间

**详细文档**: [内置插件索引](../plugins/reference/builtin/auto/INDEX.md)

---

## 相关资源

- [API 使用示例](EXAMPLES.md) - 完整代码示例
- [插件开发教程](../plugins/tutorials/SIMPLE_PLUGIN_GUIDE.md) - 从零开始
- [配置管理](../features/context/CONFIGURATION.md) - 配置系统详解
- [内置插件文档](../plugins/reference/builtin/auto/INDEX.md) - 所有内置插件
