# Hit Threshold 查询工具实现总结

## 概述

实现了一套完整的查询工具函数，用于在 notebook 和脚本中方便地查询和分析 peak、merged 和 hit_threshold 之间的关系。

## 实现的功能

### 1. 核心查询函数

- **`get_merged_indices_for_peak(peak_id, peaklet_components)`**
  - 通过 peak_id 查询其包含的所有 merged_index
  - 返回 numpy 数组

- **`get_hit_indices_for_merged(merged_index, hit_merged_components)`**
  - 通过 merged_index 查询其包含的所有 hit_index
  - 返回 numpy 数组

### 2. 完整数据查询函数（带时间间隔计算）

- **`get_hits_for_merged(merged_index, hit_merged_components, hit_threshold)`**
  - 获取某个 merged 的所有 hit 数据
  - 自动计算绝对时间（time_start, time_end）
  - 自动计算时间间隔（dt_start_to_start_ns, dt_end_to_start_ns）
  - 返回 pandas DataFrame

- **`get_hits_for_peak(peak_id, peaklet_components, hit_merged_components, hit_threshold)`**
  - 获取某个 peak 的所有 hit 数据
  - 包含 peak_id 和 merged_index 列
  - 自动按 time_start 排序
  - 返回 pandas DataFrame

### 3. 批量优化函数

- **`build_peak_to_merged_lookup(peaklet_components)`**
  - 构建 peak_id → merged_indices 完整映射字典
  - 适用于批量查询多个 peak

- **`build_merged_to_hit_lookup(hit_merged_components)`**
  - 构建 merged_index → hit_indices 完整映射字典
  - 适用于批量查询多个 merged

## 关键实现细节

### 时间计算

遵循 `hit_merge.py` 中的实现：

```python
time_start_ps = timestamp + (edge_start - position) * dt * 1000  # dt 是 ns，转为 ps
time_end_ps = timestamp + (edge_end - position) * dt * 1000
```

### 时间间隔计算

使用 pandas 的 `shift()` 方法进行向量化计算：

```python
dt_start_to_start_ns = (time_start[i] - time_start[i-1]) / 1000.0  # ps 转 ns
dt_end_to_start_ns = (time_start[i] - time_end[i-1]) / 1000.0
```

### 数据排序

所有返回的 DataFrame 都按 `time_start` 排序，确保时间间隔计算的正确性。

### 空数据处理

- 所有函数都正确处理空输入（返回空数组或空 DataFrame）
- 空 DataFrame 保持完整的列结构，便于后续 concat 操作

## 文件清单

### 新建文件

1. **`waveform_analysis/utils/query_helpers.py`** (82 行)
   - 主要实现文件
   - 包含 6 个公开函数和 1 个内部辅助函数

2. **`tests/utils/test_query_helpers.py`** (约 400 行)
   - 完整的单元测试
   - 16 个测试用例，覆盖率 95%

3. **`examples/demo_hit_query.py`** (约 200 行)
   - 使用示例和演示脚本
   - 包含模拟数据演示（无需真实数据即可运行）

4. **`docs/query_helpers_guide.md`** (约 300 行)
   - 完整的使用指南
   - API 参考文档
   - 常见问题解答

### 修改文件

1. **`waveform_analysis/utils/__init__.py`**
   - 添加 6 个新函数到 `__all__`
   - 添加对应的 lazy import 配置

## 测试结果

```
tests/utils/test_query_helpers.py::test_get_merged_indices_for_peak PASSED
tests/utils/test_query_helpers.py::test_get_merged_indices_for_peak_empty_input PASSED
tests/utils/test_query_helpers.py::test_get_hit_indices_for_merged PASSED
tests/utils/test_query_helpers.py::test_get_hit_indices_for_merged_empty_input PASSED
tests/utils/test_query_helpers.py::test_get_hits_for_merged PASSED
tests/utils/test_query_helpers.py::test_get_hits_for_merged_time_calculation PASSED
tests/utils/test_query_helpers.py::test_get_hits_for_merged_empty PASSED
tests/utils/test_query_helpers.py::test_get_hits_for_peak PASSED
tests/utils/test_query_helpers.py::test_get_hits_for_peak_sorting PASSED
tests/utils/test_query_helpers.py::test_get_hits_for_peak_empty PASSED
tests/utils/test_query_helpers.py::test_build_peak_to_merged_lookup PASSED
tests/utils/test_query_helpers.py::test_build_peak_to_merged_lookup_empty PASSED
tests/utils/test_query_helpers.py::test_build_merged_to_hit_lookup PASSED
tests/utils/test_query_helpers.py::test_build_merged_to_hit_lookup_empty PASSED
tests/utils/test_query_helpers.py::test_full_workflow PASSED
tests/utils/test_query_helpers.py::test_time_intervals_calculation PASSED

================================ 16 passed in 6.53s ================================
代码覆盖率: 95%
```

## 使用示例

### 基本用法

```python
from waveform_analysis.utils import get_hits_for_peak

# 查询 peak 123 的所有 hit 数据
intervals = get_hits_for_peak(
    peak_id=123,
    peaklet_components=peaklet_components,
    hit_merged_components=hit_merged_components,
    hit_threshold=hit_threshold
)

# 查看结果
print(intervals.head())
```

### 绘制时间间隔直方图

```python
import matplotlib.pyplot as plt
import numpy as np

dt = intervals["dt_start_to_start_ns"].dropna()
plt.hist(dt, bins=np.linspace(0, dt.max(), 100))
plt.yscale("log")
plt.xlabel("hit_threshold interval within hit_merged (ns)")
plt.ylabel("counts")
plt.show()
```

## 命名约定

符合代码库现有约定：

| 用户原始命名 | 新命名 | 说明 |
|-------------|--------|------|
| `hit_threshold_intervals_for_peak` | `get_hits_for_peak` | 更简洁，符合 `get_*` 模式 |
| `hit_threshold_intervals_in_merged` | `get_hits_for_merged` | 更简洁，符合 `get_*` 模式 |
| `peak_id_to_merged` | `get_merged_indices_for_peak` | 更清晰，表明返回类型 |
| `merged_id_to_hit` | `get_hit_indices_for_merged` | 更清晰，表明返回类型 |

参考的现有命名模式：
- `get_field_safe()` (_record_utils.py)
- `resolve_record_indices()` (_record_utils.py)
- `get_raw_files()` (loader.py)
- `get_waveforms()` (loader.py)

## 性能考虑

1. **基础查询**：使用 NumPy 布尔索引，性能良好（O(n)）
2. **时间计算**：使用 NumPy 向量化操作，避免循环
3. **时间间隔计算**：使用 pandas `shift()` 进行向量化计算
4. **批量优化**：提供 lookup 字典构建函数，避免重复扫描

## 与现有代码的兼容性

- 遵循 `hit_merge.py` 中的时间计算逻辑
- 参考 `_record_utils.py` 的 lookup 设计模式
- 参考 `_build_component_slices()` 的索引构建模式
- DataFrame 列名与 `THRESHOLD_HIT_DTYPE` 字段名保持一致

## 后续改进建议

1. **性能优化**（如果需要）：
   - 考虑使用 Numba JIT 加速时间计算
   - 实现类似 `RecordLookup` 的优化索引类

2. **功能扩展**（如果需要）：
   - 添加按通道、板卡筛选的查询函数
   - 添加按时间范围筛选的查询函数
   - 添加统计汇总函数（平均间隔、最小间隔等）

3. **文档完善**：
   - 在主 README 中添加链接
   - 在 CHANGELOG 中记录新功能

## 参考的代码库模式

1. **数据结构**：
   - `PEAKLET_COMPONENTS_DTYPE` (peaklets.py:38)
   - `HIT_MERGED_COMPONENTS_DTYPE` (hit_merge.py:44)
   - `THRESHOLD_HIT_DTYPE` (hit_finder.py:54)

2. **时间计算**：
   - `hit_merge.py:480-481` - 绝对时间计算

3. **索引构建**：
   - `_build_component_slices()` (hit_merged_features.py:94)
   - `RecordLookup` (_record_utils.py:20)

4. **查询模式**：
   - `group_hit_windows()` (event_grouping.py:286)
   - `peaklet_channels.py:92-101` - 字典查询模式

## 总结

成功实现了完整的 hit threshold 查询工具集，包括：

✅ 6 个公开查询函数
✅ 完整的单元测试（16 个测试用例，95% 覆盖率）
✅ 使用示例和演示脚本
✅ 详细的使用指南和 API 文档
✅ 与现有代码库完全兼容
✅ 所有测试通过

用户现在可以在 notebook 中方便地使用这些函数进行数据查询和分析，无需手动编写查询逻辑。
