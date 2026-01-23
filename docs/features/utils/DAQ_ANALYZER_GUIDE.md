# 📊 DAQ 运行分析器

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [工具函数](README.md) > DAQ 运行分析器

`DAQAnalyzer` 用于扫描 DAQ 目录下的所有运行，快速汇总文件规模、通道统计和采集时长，并支持终端/Notebook 展示与 JSON 导出。

---

## 📋 概述

`DAQAnalyzer` 适合做以下事情：

- 快速了解 DAQ 根目录下有哪些 run
- 查看每个 run 的文件数、通道数、总大小
- 查看单个 run 的每通道统计（文件数、时间范围、时长）
- 导出结构化 JSON，便于二次处理

该工具基于 `DAQRun` 聚合统计，默认使用 `RAW` 目录结构（向后兼容）。如果你使用自定义目录布局或适配器，可以在初始化时传入 `daq_adapter` 或 `directory_layout`。

---

## 🚀 快速开始

### 扫描全部运行并显示概览

```python
from waveform_analysis.utils.daq.daq_analyzer import DAQAnalyzer

analyzer = DAQAnalyzer(daq_root="DAQ")
analyzer.scan_all_runs()
analyzer.display_overview()
```

### 使用 DAQ 适配器或自定义目录布局

```python
from waveform_analysis.utils.daq.daq_analyzer import DAQAnalyzer
from waveform_analysis.utils.formats import get_adapter

adapter = get_adapter("vx2730")
analyzer = DAQAnalyzer(daq_root="DAQ", daq_adapter=adapter)
analyzer.scan_all_runs().display_overview()
```

```python
from waveform_analysis.utils.daq.daq_analyzer import DAQAnalyzer
from waveform_analysis.utils.formats import DirectoryLayout

layout = DirectoryLayout(raw_subdir="RAW")
analyzer = DAQAnalyzer(daq_root="DAQ", directory_layout=layout)
analyzer.scan_all_runs()
```

### 查看单个运行的通道统计

```python
analyzer.display_run_channel_details("run_001")
```

### 导出 JSON

```python
analyzer.save_to_json("outputs/daq_analysis.json", include_file_details=True)
```

---

## 🧩 核心方法

| 方法 | 说明 |
|------|------|
| `__init__(daq_root="DAQ")` | 设置 DAQ 根目录 |
| `scan_all_runs()` | 扫描所有 run 并构建统计 |
| `display_overview()` | 显示 run 总览（终端/Notebook 自适应） |
| `display_run_channel_details(run_name, show_files=False)` | 显示单个 run 的通道统计 |
| `get_run(run_name)` / `get_all_runs()` | 获取 `DAQRun` 实例 |
| `save_to_json(output_path, include_file_details=True)` | 导出 JSON 报告 |

---

## 📦 输出结构

### DataFrame (`df_runs`)

`scan_all_runs()` 会生成 `df_runs`，常用字段包括：

- `run_name`：运行名称
- `description`：描述（来自 `{run_name}_info.txt`）
- `file_count`：文件数量
- `total_size_mb` / `total_bytes`：数据大小
- `channel_count` / `channels` / `channel_str`：通道信息
- `path`：运行目录路径

### JSON 导出结构

`save_to_json()` 输出包含：

- `metadata`：扫描时间、run 数、总大小
- `runs[]`：每个 run 的统计
  - `channel_details`：每通道的时间范围、文件列表（可选）

---

## ⚠️ 注意事项

- 依赖 `pandas`；Notebook 下会自动使用富文本表格样式（可选依赖 `IPython`）。
- 默认使用 `RAW` 目录结构扫描。如需自定义布局，传入 `daq_adapter` 或 `directory_layout`。

---

## 🔗 相关资源

- [DAQ 适配器指南](DAQ_ADAPTER_GUIDE.md) - 目录结构与格式适配
- [waveform-process CLI](../../cli/WAVEFORM_PROCESS.md) - `--show-daq` 查看 DAQ 概览
