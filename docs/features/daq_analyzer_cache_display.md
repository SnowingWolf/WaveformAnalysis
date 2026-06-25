# DAQAnalyzer 缓存状态显示功能

## 功能概述

`DAQAnalyzer.display_overview()` 方法新增了缓存状态显示功能，可以在运行概览表格中显示每个运行的缓存数据统计信息。

## 新增参数

```python
def display_overview(
    self,
    sort_by: str | None = None,
    ascending: bool = True,
    max_rows: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    show_cache: bool = False,              # 新增
    cache_storage_dir: str | None = None,  # 新增
    cache_data_types: list[str] | None = None,  # 新增
) -> DAQAnalyzer:
```

### 参数说明

- **`show_cache`** (bool, 默认 False)
  - 是否显示缓存状态列
  - 默认为 False，保持向后兼容性

- **`cache_storage_dir`** (str | None, 默认 None)
  - 缓存存储目录的路径（例如 `"./strax_data"`）
  - 如果为 None，则不显示缓存列（即使 `show_cache=True`）
  - 必须指向包含 `{run_id}/_cache/` 结构的目录

- **`cache_data_types`** (list[str] | None, 默认 None)
  - 要显示的数据类型列表
  - 默认值：`["records", "hits", "peaks"]`
  - 可以自定义为任何有效的数据类型名称

## 使用示例

### 1. 基本用法（向后兼容）

```python
from waveform_analysis.utils.daq.daq_analyzer import DAQAnalyzer

da = DAQAnalyzer(daq_root="DAQ", daq_adapter="vx2730")
da.scan_all_runs()

# 不显示缓存列（默认行为）
da.display_overview()
```

### 2. 显示缓存状态

```python
# 显示缓存列（使用默认数据类型）
da.display_overview(
    show_cache=True,
    cache_storage_dir="./strax_data"
)
```

**输出示例（终端）：**
```
45V_OV_circulation_CH0_Coincidence_20dB  files=   7  boards= 0  channels= 3  size=4.34 GB  cache=[records: 1.2M, hits: 340K, peaks: 58K]  start=2025-12-25 20:36:27  end=2025-12-25 20:53:07  path=/mnt/data/Run3/DAQ/45V_OV_circulation_CH0_Coincidence_20dB
```

### 3. 自定义数据类型

```python
# 仅显示 st_waveforms 和 basic_features
da.display_overview(
    show_cache=True,
    cache_storage_dir="./strax_data",
    cache_data_types=["st_waveforms", "basic_features", "pulse_width"]
)
```

### 4. 结合其他过滤和排序选项

```python
# 按大小降序排列，显示前 20 个运行的缓存状态
da.display_overview(
    sort_by="size",
    ascending=False,
    max_rows=20,
    show_cache=True,
    cache_storage_dir="./strax_data",
    cache_data_types=["st_waveforms", "basic_features"]
)
```

### 5. 在 Jupyter Notebook 中使用

在笔记本环境中，缓存状态列会自动添加到样式化的 DataFrame 表格中：

```python
da = DAQAnalyzer(daq_root="/mnt/data/Run3/DAQ", daq_adapter="vx2730")
da.scan_all_runs()

# 在笔记本中显示带缓存状态的表格
da.display_overview(
    sort_by="name",
    show_cache=True,
    cache_storage_dir="./strax_data"
)
```

表格将包含一个新的 **"缓存状态"** 列，显示格式化的缓存信息。

## 缓存状态格式

缓存状态以紧凑的格式显示每种数据类型的记录数：

| 记录数范围 | 显示格式 | 示例 |
|-----------|---------|------|
| < 1,000 | 原始数字 | `records: 999` |
| 1,000 - 999,999 | K（千） | `records: 340K` |
| ≥ 1,000,000 | M（百万） | `records: 1.2M` |

**完整示例：**
- `records: 1.2M, hits: 340K, peaks: 58K` - 所有三种类型都已缓存
- `records: 1.2M, hits: 340K` - 仅 records 和 hits 已缓存
- `N/A` - 没有缓存或缓存目录不存在

## 缓存目录结构

该功能要求缓存遵循以下目录结构：

```
{cache_storage_dir}/
├── {run_id_1}/
│   └── _cache/
│       ├── {run_id_1}-{data_name_1}-{hash}.json
│       ├── {run_id_1}-{data_name_1}-{hash}.bin
│       ├── {run_id_1}-{data_name_2}-{hash}.json
│       └── {run_id_1}-{data_name_2}-{hash}.bin
├── {run_id_2}/
│   └── _cache/
│       └── ...
└── ...
```

缓存扫描逻辑：
1. 扫描 `{cache_storage_dir}/{run_id}/_cache/` 目录
2. 读取所有 `.json` 元数据文件
3. 从文件名提取 `data_name`（格式：`{run_id}-{data_name}-{hash}.json`）
4. 从 JSON 文件中读取 `count` 字段（记录数）
5. 如果同一数据类型有多个版本（不同的 lineage hash），保留记录数最大的

## 性能考虑

- **扫描开销**：每次调用 `display_overview()` 时都会扫描文件系统
- **预计耗时**：
  - 10-50 个运行：< 100ms
  - 100+ 个运行：可能需要更长时间
- **优化建议**：
  - 使用 `max_rows` 限制显示的运行数量
  - 结合时间过滤（`start_time`, `end_time`）减少扫描范围

## 边界情况处理

该功能已对以下边界情况进行了测试：

1. **缓存目录不存在**：显示 `N/A`
2. **空缓存目录**：显示 `N/A`
3. **缓存文件格式错误**：跳过无效文件，记录调试日志
4. **数据类型不匹配**：仅显示 `cache_data_types` 中指定的类型
5. **同一数据类型多个版本**：自动选择记录数最大的版本

## 实现细节

### 新增方法

#### 1. `_scan_cache_for_run(run_name, storage_dir) -> dict[str, int]`

静态方法，扫描指定运行的缓存目录并返回统计信息。

```python
cache_stats = DAQAnalyzer._scan_cache_for_run(
    "45V_OV_circulation_CH0_Coincidence_20dB",
    "./strax_data"
)
# 返回: {'st_waveforms': 1160523, 'basic_features': 1160523, ...}
```

#### 2. `_format_cache_status(cache_stats, target_types) -> str`

静态方法，将缓存统计格式化为显示字符串。

```python
formatted = DAQAnalyzer._format_cache_status(
    {"records": 1234567, "hits": 456789, "peaks": 89012},
    ["records", "hits", "peaks"]
)
# 返回: "records: 1.2M, hits: 457K, peaks: 89K"
```

## 向后兼容性

- 所有新参数都是可选的，默认值保持现有行为
- `show_cache=False` 时，不会进行任何缓存扫描
- 现有代码无需修改即可继续使用

## 测试

测试脚本位于：
- `test_cache_display.py` - 命令行测试
- `test_cache_display.ipynb` - Jupyter 笔记本测试

运行测试：
```bash
python3 test_cache_display.py
```

## 相关文件

- `waveform_analysis/utils/daq/daq_analyzer.py` - 主实现文件
- `waveform_analysis/core/storage/cache_analyzer.py` - 缓存分析器（独立工具）
- `waveform_analysis/core/storage/memmap.py` - 缓存存储层
