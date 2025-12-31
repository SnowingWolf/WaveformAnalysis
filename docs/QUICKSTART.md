# 快速开始指南

## 5 分钟快速上手

### 1. 安装

```bash
# 使用安装脚本
./install.sh

# 或手动安装
pip install -e .
```

### 2. 核心概念

- **Context**: 管理所有配置和插件的中心对象。
- **Plugin**: 独立的处理单元（如：找文件、提波形、找 Hit）。
- **Data Name**: 插件产出的数据标识（如：`raw_files`, `hits`）。

### 3. 运行第一个流式处理任务

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.standard_plugins import RawFilesPlugin
from waveform_analysis.core.streaming_plugins import (
    StreamingWaveformsPlugin, 
    StreamingStWaveformsPlugin, 
    StreamingHitsPlugin
)

# 1. 初始化 Context
ctx = Context(storage_dir="./strax_data")

# 2. 注册你需要的插件
ctx.register_plugin(RawFilesPlugin())
ctx.register_plugin(StreamingWaveformsPlugin())
ctx.register_plugin(StreamingStWaveformsPlugin())
ctx.register_plugin(StreamingHitsPlugin())

# 3. 设置配置参数
ctx.set_config({
    "data_root": "DAQ",
    "n_channels": 2,
    "threshold": 15.0,
    "chunksize": 1000
})

# 4. 获取数据
# 第一次运行会触发计算并保存缓存
hits = ctx.get_data("run_001", "hits")

# hits 是一个 numpy.memmap 对象，支持切片访问而不占用大量内存
print(f"Found {len(hits)} hits")
print(hits[0])
```

### 4. 可视化结果

```python
from waveform_analysis.utils.visualizer import plot_waveforms

# 获取一波结构化波形（流式）
st_waves_gen = ctx.get_data("run_001", "st_waveforms_stream")
first_chunk = next(st_waves_gen)

# 绘制第一个 Event
fig = plot_waveforms(first_chunk, hits, event_index=0)
fig.show()
```

### 4. 内存优化：只加载特征，跳过原始波形

如果内存有限或只需要统计特征，使用 `load_waveforms=False`：

```python
# 创建数据集，不加载原始波形
dataset = WaveformDataset(
    char="50V_OV_circulation_20thr",
    n_channels=2,
    load_waveforms=False  # 关键：节省内存
)

# 处理流程相同，但会跳过波形提取和结构化
(dataset
    .load_raw_data()
    .extract_waveforms()          # ← 被跳过（因为 load_waveforms=False）
    .structure_waveforms()        # ← 被跳过
    .build_waveform_features()    # ← 仍会运行
    .build_dataframe()
    .group_events()
    .pair_events())

# 可以访问所有特征数据
df = dataset.get_paired_events()
print(f"事件数: {len(df)}")
print(f"峰值: {df['peak_ch6'].mean():.2f}")

# 但不能访问原始波形
result = dataset.get_waveform_at(0)  # 返回 None，显示警告
```

**内存节省**: 通常减少 70-80% 的内存使用

### 5. 使用命令行工具

```bash
waveform-process --char 50V_OV_circulation_20thr --verbose
```

### 6. 运行示例脚本

```bash
# 基础分析
python examples/basic_analysis.py

# 高级功能
python examples/advanced_features.py

# 跳过波形演示
python examples/skip_waveforms.py
```

### 缓存与自动失效（可选）

为了加速重复运行，你可以为某个 pipeline 步骤启用缓存（内存或磁盘持久化）。当原始文件改变时，也可以自动使磁盘缓存失效并强制重新计算。

示例：为 `load_raw_data` 启用持久化缓存并监视 `raw_files`（文件的 mtime/size 变化将触发失效）。

```python
from waveform_analysis import WaveformDataset

ds = WaveformDataset(char='my_run', data_root='DAQ', use_daq_scan=True)
# 启用缓存：保存 attrs 到磁盘，并监视 raw_files（文件变化时自动失效）
ds.set_step_cache(
    'load_raw_data',
    enabled=True,
    attrs=['raw_files'],
    persist_path='/tmp/my_run_load_cache.pkl',
    watch_attrs=['raw_files']
)

# 第一次会执行并写入缓存
ds.load_raw_data()

# 修改原始 CSV（或在新进程中）再次调用，若文件 mtime/size 发生改变，磁盘缓存会被认为失效并重新生成
ds.load_raw_data()

# 若要手动清除缓存：
ds.clear_cache('load_raw_data')
ds.clear_cache()  # 清空所有步骤缓存
```

注意：默认不会监视文件变更，需通过 `watch_attrs` 指定要监视的属性（通常是 `raw_files` 或包含路径的属性）。

关于 WATCH_SIG_KEY

当你启用持久化缓存并配置了 `watch_attrs` 时，系统会将用于验证缓存的签名写入持久化文件，键名为包级常量 `WATCH_SIG_KEY`（值：`"__watch_sig__"`）。
你可以从包顶层导入并在脚本或测试中引用它：

```python
from waveform_analysis import WATCH_SIG_KEY
print(WATCH_SIG_KEY)  # "__watch_sig__"
```

更多实现细节与实践建议请参阅文档：`docs/CACHE.md`。

### DAQ 扫描概览

如果你使用 `DAQAnalyzer` 扫描 DAQ 根目录，新增了兼容方法 `display_overview()` 用来快速打印/展示扫描到的 runs 概览：

```python
from waveform_analysis.utils.daq import DAQAnalyzer

analyzer = DAQAnalyzer('DAQ')
analyzer.scan_all_runs()
analyzer.display_overview()  # Notebook 中会用 Styler 展示，终端中打印表格
```


## 常用操作

### 加载和查看数据

```python
from waveform_analysis import WaveformDataset

dataset = WaveformDataset(char="your_dataset")
dataset.load_raw_data().extract_waveforms()

# 查看摘要
print(dataset.summary())
```

### 获取波形

```python
# 获取特定事件的波形
wave, baseline = dataset.get_waveform_at(event_idx=0, channel=0)

# 转换为物理单位
wave_mv = (wave - baseline) * 0.024
print(f"波形长度: {len(wave)}")
```

### 数据分析

```python
import matplotlib.pyplot as plt

# 获取配对数据
df = dataset.get_paired_events()

# 绘制峰值分布
plt.hist(df['peak_ch6'], bins=50, alpha=0.7, label='CH6')
plt.hist(df['peak_ch7'], bins=50, alpha=0.7, label='CH7')
plt.xlabel('Peak [ADC]')
plt.legend()
plt.show()

# 查看时间差
plt.hist(df['delta_t'], bins=50)
plt.xlabel('Time Difference [ns]')
plt.show()
```

### 保存结果

```python
# 自动保存到 outputs/ 目录
dataset.save_results()

# 或手动保存
df.to_csv('my_results.csv', index=False)
df.to_parquet('my_results.parquet')
```

## 下一步

- 阅读完整文档：[docs/USAGE.md](USAGE.md)
- 查看更多示例：[examples/](../WaveformAnalysis/examples)
- 了解项目结构：[docs/PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- 学习贡献指南：[CONTRIBUTING.md](../CONTRIBUTING.md)

## 遇到问题？

1. 检查 [常见问题](USAGE.md#常见问题)
2. 查看 [GitHub Issues](https://github.com/yourusername/waveform-analysis/issues)
3. 联系维护者

## 更新笔记本代码

如果你有现有的 Jupyter 笔记本，只需更新导入语句：

```python
# 旧代码
from data import WaveformDataset
from load import get_raw_files

# 新代码
from waveform_analysis import WaveformDataset
from waveform_analysis.core import get_raw_files
```

其他代码保持不变！
