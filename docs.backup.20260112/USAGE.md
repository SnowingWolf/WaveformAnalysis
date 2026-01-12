# 使用指南

## 目录

- [安装](#安装)
- [基本用法](#基本用法)
- [高级功能](#高级功能)
- [API 参考](#api-参考)
- [常见问题](#常见问题)

## 安装

### 方法 1: 使用安装脚本（推荐）

## 📢 最近更新

- `dataset.get_data(run_id, "df" / "df_events" / "df_paired")` 会自动触发构建 DataFrame、分组事件、配对事件等 `_ensure_*` 步骤，较少手动步骤调用。
- `Context` 不再把 `stream` 插件的生成器绑定成类属性，多次获取 `waveforms_stream`、`st_waveforms_stream` 或 `hits_stream` 时会重新构建迭代器，保障流式分析可以多次运行。

```bash
./install.sh
```

### 方法 2: 手动安装

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装包
pip install -e .

# 安装开发依赖（可选）
pip install -e ".[dev]"
```

## 基本用法

### 1. 导入包

```python
from waveform_analysis import WaveformDataset
```

### 2. 创建数据集并处理

```python
# 创建数据集实例
dataset = WaveformDataset(
    run_name="50V_OV_circulation_20thr",  # 默认 Run ID
    n_channels=2,                      # 通道数
    start_channel_slice=6              # 起始通道
)

# 链式调用处理流程 (默认作用于 self.char)
(dataset
    .load_raw_data()                    # 加载原始文件
    .extract_waveforms()                # 提取波形
    .structure_waveforms()              # 结构化数据
    .build_waveform_features()          # 计算特征
    .build_dataframe()                  # 构建 DataFrame
    .group_events()                     # 事件分组
    .pair_events()                      # 事件配对
    .save_results())                    # 保存结果

# 显式指定 Run ID (支持在同一个实例中处理多个 Run)
dataset.load_raw_data(run_id="another_run_001")
dataset.extract_waveforms(run_id="another_run_001")
```

### 3. 访问结果

```python
# 获取默认 Run 的配对事件
df_paired = dataset.get_paired_events()

# 获取特定 Run 的数据
df_another = dataset.get_data("another_run_001", "df_paired")

# 获取摘要信息
summary = dataset.summary()
print(summary)
```

### 4. 访问波形数据

```python
# 获取特定事件的波形
wave, baseline = dataset.get_waveform_at(event_idx=0, channel=0)

# 转换为 mV
wave_mv = (wave - baseline) * 0.024
```

### 5. Generator 语义与一次性消费

为了处理大规模数据，某些插件（如 `extract_waveforms`）可能返回 `generator`。

- **一次性消费**：Generator 只能被迭代一次。如果尝试第二次迭代，系统会抛出 `RuntimeError`。
- **自动缓存**：当您迭代 Generator 时，系统会自动将其内容保存到磁盘缓存中。
- **持久化访问**：一旦 Generator 被消费完，后续通过 `get_data()` 获取的将是磁盘上的 `memmap` 对象，支持多次随机访问。

```python
# 第一次获取：返回 OneTimeGenerator
gen = dataset.get_data(run_id="run1", name="waveforms")
for chunk in gen:
    process(chunk) # 此时数据正在被写入磁盘

# 第二次获取：返回 np.memmap (支持多次访问)
data = dataset.get_data(run_id="run1", name="waveforms")
print(data[0]) 
```

## 高级功能

### 自定义特征

```python
import numpy as np

# 定义特征计算函数
def compute_rise_time(waveforms, start=40, threshold=0.1):
    rise_times = []
    for wave in waveforms:
        peak = np.max(wave['wave'][start:])
        thresh_val = peak * threshold
        idx = np.where(wave['wave'][start:] > thresh_val)[0]
        rise_times.append(idx[0] if len(idx) > 0 else -1)
    return [np.array(rise_times)]

# 注册特征
dataset.register_feature('rise_time', compute_rise_time)

# 计算特征
dataset.compute_registered_features()

# 添加到 DataFrame
dataset.add_features_to_dataframe(['rise_time'])
```

### 自定义配对策略

```python
def custom_pairing(df_events):
    \"\"\"只配对高能量事件\"\"\"
    df = df_events[
        (df_events['n_hits'] == 2) & 
        (df_events['channels'].apply(lambda x: np.array_equal(x, [0, 1])))
    ]
    # 添加能量筛选
    df['total_charge'] = df['charges'].apply(lambda x: sum(x))
    return df[df['total_charge'] > 5000]

# 使用自定义策略
df_custom = dataset.pair_events_with(custom_pairing)
```

### 数据可视化

```python
import matplotlib.pyplot as plt

# 峰值分布
plt.hist(df_paired['peak_ch6'], bins=50, alpha=0.7, label='CH6')
plt.hist(df_paired['peak_ch7'], bins=50, alpha=0.7, label='CH7')
plt.xlabel('Peak [ADC]')
plt.ylabel('Count')
plt.legend()
plt.show()

# 绘制波形
result_ch6 = dataset.get_waveform_at(0, channel=0)
result_ch7 = dataset.get_waveform_at(0, channel=1)

if result_ch6 and result_ch7:
    wave6, baseline6 = result_ch6
    wave7, baseline7 = result_ch7
    
    plt.plot((wave6 - baseline6) * 0.024, label='CH6')
    plt.plot((wave7 - baseline7) * 0.024, label='CH7')
    plt.xlabel('Sample')
    plt.ylabel('Amplitude [mV]')
    plt.legend()
    plt.show()
```

## API 参考

### WaveformDataset

主数据集类，提供完整的数据处理流程。

#### 构造函数

```python
WaveformDataset(
    char: str = "50V_OV_circulation_20thr",
    n_channels: int = 2,
    start_channel_slice: int = 6,
    data_root: str = "DAQ"
)
```

#### 主要方法

- `load_raw_data()`: 加载原始数据文件
- `extract_waveforms()`: 提取波形数据
- `structure_waveforms()`: 结构化波形
- `build_waveform_features()`: 计算波形特征
- `build_dataframe()`: 构建 DataFrame
- `group_events()`: 事件分组
- `pair_events()`: 事件配对
- `save_results()`: 保存结果

#### 数据访问方法

- `get_raw_events()`: 获取原始事件 DataFrame
- `get_grouped_events()`: 获取分组事件 DataFrame
- `get_paired_events()`: 获取配对事件 DataFrame
- `get_waveform_at(event_idx, channel)`: 获取特定波形
- `summary()`: 获取处理摘要

#### 扩展方法

- `register_feature(name, fn, **params)`: 注册自定义特征
- `compute_registered_features(verbose=False)`: 计算注册的特征
- `add_features_to_dataframe(names, verbose=False)`: 添加特征到 DataFrame
- `pair_events_with(strategy, verbose=False)`: 使用自定义配对策略

## 命令行工具

```bash
# 基本用法
waveform-process --char 50V_OV_circulation_20thr

# 指定参数
waveform-process \\
    --char 50V_OV_circulation_20thr \\
    --n-channels 2 \\
    --start-channel 6 \\
    --time-window 100 \\
    --output results.csv \\
    --verbose

# 查看帮助
waveform-process --help
```

## 内存优化

如果您的系统内存有限，或者只需要特征数据（峰值、电荷等）而不需要原始波形，可以使用 `load_waveforms=False` 参数：

```python
# 不加载波形数据以节省内存
dataset = WaveformDataset(
    run_name="50V_OV_circulation_20thr",
    n_channels=2,
    load_waveforms=False  # 关键：不加载原始波形
)

# 处理流程保持不变
(dataset
    .load_raw_data()
    .extract_waveforms()      # 此步骤会被跳过
    .structure_waveforms()    # 此步骤会被跳过
    .build_waveform_features()  # 仍会运行，从 CSV 直接读取特征
    .build_dataframe()
    .group_events()
    .pair_events()
    .save_results())

# 可以访问特征数据
df = dataset.get_paired_events()  # 可以访问所有统计特征
peaks = dataset.get_peaks()       # 可以访问峰值

# 但不能访问原始波形
dataset.get_waveform_at(0)  # 返回 None 并显示警告
```

**权衡**:
- ✅ 优点：显著降低内存使用（通常减少 70-80%）
- ✅ 优点：加速处理（跳过 CSV→数组转换）
- ✅ 优点：仍然保留所有统计特征
- ❌ 缺点：无法进行需要原始波形的分析

查看 [skip_waveforms.py](../WaveformAnalysis/examples/skip_waveforms.py) 获取完整示例。

## 常见问题

### Q: 如何处理大数据集？

A: 可以使用以下策略：
- 使用 `load_waveforms=False` 只加载特征（**推荐**）
- 分批处理数据
- 只加载需要的通道
- 使用 Parquet 格式存储中间结果
- 限制内存中的事件数量

### Q: 如何添加新的物理量？

A: 使用特征注册系统：

```python
dataset.register_feature('my_feature', compute_function, **params)
dataset.compute_registered_features()
```

### Q: 配对失败怎么办？

A: 检查：
- 时间窗口是否合适
- 数据是否正确加载
- 通道配置是否正确
- 使用 `verbose=True` 查看详细信息

### Q: 如何调试？

A: 
```python
# 启用详细输出
dataset.compute_registered_features(verbose=True)
dataset.pair_events_with(strategy, verbose=True)

# 检查中间结果
print(dataset.summary())
print(dataset.get_raw_events().head())
```

## 性能优化

1. **使用 timestamp 索引缓存**: 自动启用，加速波形查找
2. **限制事件数量**: 在可视化时只处理部分数据
3. **批量处理**: 使用 Pandas 向量化操作
4. **并行处理**: 考虑使用 Dask 处理大数据集

## 更多示例

查看 `examples/` 目录获取更多示例：

- `basic_analysis.py`: 基本分析流程
- `advanced_features.py`: 高级功能演示

## 支持

如有问题，请：
- 查看文档
- 在 GitHub 上提 Issue
- 联系维护者
