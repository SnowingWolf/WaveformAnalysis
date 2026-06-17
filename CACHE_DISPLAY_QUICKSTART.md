# 快速开始：DAQAnalyzer 缓存状态显示

## 一行代码示例

```python
from waveform_analysis.utils.daq.daq_analyzer import DAQAnalyzer

# 扫描并显示缓存状态
DAQAnalyzer(daq_root="DAQ").scan_all_runs().display_overview(
    show_cache=True,
    cache_storage_dir="./strax_data"
)
```

## 常见用法

### 1. 显示默认缓存类型 (records, hits, peaks)

```python
da = DAQAnalyzer(daq_root="/mnt/data/TPC/run6_Xe", daq_adapter="vx2730")
da.scan_all_runs()
da.display_overview(
    show_cache=True,
    cache_storage_dir="./strax_data"
)
```

### 2. 显示自定义缓存类型

```python
da.display_overview(
    show_cache=True,
    cache_storage_dir="./strax_data",
    cache_data_types=["st_waveforms", "basic_features", "pulse_width"]
)
```

### 3. 结合排序和过滤

```python
# 按大小降序，显示前 20 个，并显示缓存
da.display_overview(
    sort_by="size",
    ascending=False,
    max_rows=20,
    show_cache=True,
    cache_storage_dir="./strax_data"
)
```

## 输出示例

```
00290  files=   6  boards= 2  channels= 9  size=4.67 GB  cache=[records: 1.2M, hits: 340K, peaks: 58K]  start=2026-06-15 01:26:07  end=2026-06-15 02:13:08  path=/mnt/data/TPC/run6_Xe/00290
00291  files=   2  boards= 2  channels= 9  size=405.48 MB  cache=[N/A]  start=2026-06-15 02:18:28  end=2026-06-15 02:18:28  path=/mnt/data/TPC/run6_Xe/00291
```

## 注意事项

- 默认 `show_cache=False`，需要显式开启
- `cache_storage_dir` 必须指向包含 `{run_id}/_cache/` 结构的目录
- 没有缓存的运行显示 `N/A`
- 支持笔记本和终端环境

完整文档: `docs/features/daq_analyzer_cache_display.md`
