# waveform-process 命令参考

**导航**: [文档中心](../README.md) > [cli](README.md) > waveform-process 命令参考

`waveform-process` 是 WaveformAnalysis 的主要命令行工具，用于处理波形数据和扫描 DAQ 目录。

---

## 命令概述

`waveform-process` 提供以下功能：
- 处理单个数据集（提取波形、计算特征、配对事件）
- 扫描 DAQ 目录并导出 JSON 报告
- 显示指定运行的 DAQ 通道详情

> ✅ 本命令基于 `Context` 和插件系统。

---

## 基本用法

```bash
waveform-process [选项]
```

---

## 参数说明

### 数据处理参数

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--run-name` | `--char` | str | - | 数据集标识符（目录名）。当使用 `--show-daq` 时可省略 |
| `--n-channels` | - | int | 2 | 处理的通道数 |
| `--start-channel` | - | int | 6 | 起始通道索引 |
| `--time-window` | - | float | 100 | 事件配对时间窗口（ns） |
| `--output` | - | str | - | 输出文件路径（可选）。支持 `.csv` 和 `.parquet` 格式 |
| `--verbose` | - | flag | False | 显示详细信息 |

### DAQ 扫描参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--scan-daq` | flag | False | 扫描 DAQ 目录并导出 JSON 报告（会忽略其它处理选项） |
| `--daq-root` | str | "DAQ" | DAQ 根目录 |
| `--daq-out` | str | "daq_analysis.json" | DAQ 扫描结果输出路径 |

### DAQ 显示参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--show-daq` | str | - | 显示指定运行的 DAQ 通道详情（run name） |
| `--show-daq-files` | flag | False | 在显示中包含每个通道的文件明细 |

### 其他参数

| 参数 | 说明 |
|------|------|
| `--version` | 显示版本信息 |
| `--help` | 显示帮助信息 |

---

## 使用示例

### 1. 处理单个数据集

```bash
# 基本处理
waveform-process --run-name 50V_OV_circulation_20thr

# 指定输出文件
waveform-process --run-name 50V_OV_circulation_20thr --output results.csv

# 使用 Parquet 格式
waveform-process --run-name 50V_OV_circulation_20thr --output results.parquet

# 自定义参数
waveform-process \
  --run-name 50V_OV_circulation_20thr \
  --n-channels 4 \
  --start-channel 0 \
  --time-window 200 \
  --verbose
```

### 2. 扫描 DAQ 目录

```bash
# 扫描默认 DAQ 目录
waveform-process --scan-daq

# 指定 DAQ 根目录
waveform-process --scan-daq --daq-root /path/to/DAQ

# 指定输出文件
waveform-process --scan-daq --daq-out daq_report.json --verbose
```

### 3. 显示 DAQ 信息

```bash
# 显示运行的基本信息
waveform-process --show-daq 50V_OV_circulation_20thr

# 包含文件明细
waveform-process --show-daq 50V_OV_circulation_20thr --show-daq-files
```

---

## 输出说明

### 数据处理输出

- **默认输出**: 结果保存到 `outputs/{run_name}_paired.csv`
- **指定输出**: 使用 `--output` 参数指定路径
- **支持格式**: CSV (`.csv`) 和 Parquet (`.parquet`)

### DAQ 扫描输出

- **JSON 格式**: 包含所有运行的通道信息和文件列表
- **默认路径**: `daq_analysis.json`
- **可自定义**: 使用 `--daq-out` 指定输出路径

---

## 退出码

| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 错误（文件未找到、处理失败等） |
| 2 | 参数错误（缺少必需参数） |

---

## 错误处理

### 常见错误

1. **缺少 --run-name**
   ```
   错误: --run-name 是必需的（除非使用 --show-daq）
   ```
   解决: 提供 `--run-name` 参数或使用 `--show-daq`

2. **数据文件未找到**
   ```
   错误: 数据文件未找到 - ...
   ```
   解决: 检查数据目录是否存在，确认 `--run-name` 正确

3. **DAQ 扫描失败**
   ```
   DAQ 扫描或保存失败
   ```
   解决: 检查 `--daq-root` 目录是否存在且可读

### 调试技巧

使用 `--verbose` 选项查看详细错误信息：

```bash
waveform-process --run-name run_001 --verbose
```

---

## 注意事项

1. **推荐路径**: CLI 与 `Context` API 保持一致
2. **参数互斥**: `--scan-daq` 会忽略其他处理选项
3. **文件格式**: 输出文件格式由文件扩展名决定（`.csv` 或 `.parquet`）
4. **默认行为**: 如果不指定 `--output`，结果会保存到 `outputs/` 目录

---

## 使用 Context API

CLI 与 `Context` 的执行路径一致，下面是对应的最简代码：

```python
from waveform_analysis.core import Context
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

ctx = Context()
ctx.register(*standard_plugins)
ctx.set_config({'data_root': 'DAQ', 'daq_adapter': 'vx2730'})
peaks = ctx.get_data('run_001', 'peaks')
```

更多信息请参考 [用户指南](../user-guide/README.md)。

---

**相关文档**: 
[CLI 工具总览](README.md) | 
[用户指南](../user-guide/README.md) | 
[快速开始](../user-guide/QUICKSTART_GUIDE.md)
