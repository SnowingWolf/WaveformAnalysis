# Peaks 上游插件优化方案

## 执行摘要

本文档分析 `peaks` 插件上游处理链的性能瓶颈，并提供优化建议。

**上游依赖链路：**
```
hit_threshold → hit_merged → peaklets → peaklet_components
                                      → peaklet_waveforms → peaklet_features → peaks
                                                         → peaklet_waveform_pool
```

## 1. 性能瓶颈识别

### 1.1 高频 Python 循环（关键瓶颈）

**问题位置：** `peaklets.py` 的 `_abs_window()` 函数

```python
def _abs_window(rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    starts = np.zeros(len(rows), dtype=np.float64)
    ends = np.zeros(len(rows), dtype=np.float64)
    for i, row in enumerate(rows):  # ← Python 循环，每个 peaklet 调用一次
        start, end = _hit_abs_window(row)
        starts[i] = start
        ends[i] = end
    return starts, ends
```

**性能数据：**
- n=100: ~0.24 ms
- n=1000: ~2.4 ms (线性增长)
- 纯 Python 循环，无法利用向量化

### 1.2 重复计算 cluster 成员关系

**问题位置：** `PeakletPlugin` 和 `PeakletComponentsPlugin` 重复计算相同的 clustering

```python
# PeakletPlugin.compute()
clusters = _cluster_merged_hits(merged, ...)  # 第 1 次

# PeakletComponentsPlugin.compute()
clusters = _cluster_merged_hits(merged, ...)  # 第 2 次，完全相同的输入和参数
```

**影响：**
- 500 个 hit_merged: ~1.35 ms × 2 = 2.7 ms
- 增加缓存压力和内存分配

### 1.3 波形构建中的多次数据访问

**问题位置：** `PeakletWaveformPlugin._merged_wave_piece()`

```python
for merged_index in merged_indices:
    hit = merged[int(merged_index)]
    record = record_lookup.get(int(hit["record_id"]))  # ← 逐个查找
    # ... 提取波形片段
```

**优化空间：**
- 批量查找 record_ids
- 预先计算 record 映射关系

## 2. 优化方案

### 2.1 向量化 `_abs_window()` [高优先级]

**优化前：**
```python
def _abs_window(rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    starts = np.zeros(len(rows), dtype=np.float64)
    ends = np.zeros(len(rows), dtype=np.float64)
    for i, row in enumerate(rows):
        start, end = _hit_abs_window(row)
        starts[i] = start
        ends[i] = end
    return starts, ends
```

**优化后：**
```python
def _abs_window_vectorized(rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """向量化版本，避免 Python 循环。"""
    names = rows.dtype.names or ()

    # 批量提取字段
    if {"sample_start", "sample_end"}.issubset(names):
        sample_start = rows["sample_start"].astype(np.int64)
        sample_end = rows["sample_end"].astype(np.int64)
    elif {"edge_start", "edge_end"}.issubset(names):
        sample_start = rows["edge_start"].astype(np.int64)
        sample_end = rows["edge_end"].astype(np.int64)
    else:
        raise KeyError("需要 sample_start/sample_end 或 edge_start/edge_end")

    dt_ps = rows["dt"].astype(np.int64) * 1000
    timestamp = rows["timestamp"].astype(np.int64) if "timestamp" in names else np.zeros(len(rows), dtype=np.int64)
    position = rows["position"].astype(np.int64) if "position" in names else np.zeros(len(rows), dtype=np.int64)

    # 向量化计算
    abs_starts = timestamp + (sample_start - position) * dt_ps
    abs_ends = timestamp + (sample_end - position) * dt_ps

    return abs_starts, abs_ends
```

**预期收益：**
- 性能提升：10-20x（n=1000）
- 从 2.4 ms → ~0.15 ms

### 2.2 缓存 cluster 计算结果 [中优先级]

**方案 A：在 context 中缓存中间结果**

```python
class PeakletPlugin(BatchProcessingPlugin):
    def compute_array(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        merged = context.get_data(run_id, "hit_merged")
        if len(merged) == 0:
            return _empty_peaklets()

        # 检查缓存
        cache_key = "_peaklet_clusters"
        clusters = getattr(context, cache_key, None)
        if clusters is None:
            clusters = self._compute_clusters(merged, context)
            setattr(context, cache_key, clusters)  # 缓存

        return self._build_peaklets_from_clusters(clusters, merged)
```

**方案 B：创建独立的 cluster 插件（推荐）**

```python
class PeakletClustersPlugin(Plugin):
    """计算 peaklet cluster 成员关系的专用插件。"""
    provides = "peaklet_clusters"
    depends_on = ["hit_merged"]
    version = "1.0.0"

    def compute(self, context: Any, run_id: str, **_kwargs) -> list[list[int]]:
        merged = context.get_data(run_id, "hit_merged")
        return _cluster_merged_hits(merged, ...)

# PeakletPlugin 和 PeakletComponentsPlugin 都依赖 peaklet_clusters
```

**预期收益：**
- 消除 50% 的 clustering 计算
- 更清晰的依赖关系

### 2.3 批量 record 查找 [中优先级]

**优化前：**
```python
for merged_index in merged_indices:
    hit = merged[int(merged_index)]
    record = record_lookup.get(int(hit["record_id"]))  # ← 逐个查找
```

**优化后：**
```python
# 批量查找
hit_indices = merged_indices
hits = merged[hit_indices]
record_ids = hits["record_id"]
record_indices = record_lookup.get_indices(record_ids)  # ← 批量查找
records = records_array[record_indices]

for i, (hit, record) in enumerate(zip(hits, records)):
    # ... 处理
```

**注意：** `RecordLookup.get_indices()` 已经在 `_record_utils.py` 中实现。

### 2.4 Numba 加速 peaklet clustering [低优先级]

`hit_merge.py` 已经有 Numba 版本的 clustering，但 `peaklets.py` 的 `_cluster_merged_hits` 仍然是纯 Python。

**考虑复用或适配：**
```python
# 参考 hit_merge.py 的 _merge_clusters_numba
# 适配到 peaklets 的场景
```

**预期收益：**
- 性能提升：10-20x（n > 200）
- 对于大数据集更明显

## 3. 实施优先级

| 优化项 | 优先级 | 实施成本 | 性能提升 | 风险 |
|--------|--------|----------|----------|------|
| 向量化 `_abs_window()` | **高** | 低 | 10-20x | 低 |
| 缓存 cluster 结果 | 中 | 中 | 50% 减少 | 中（需要插件版本升级）|
| 批量 record 查找 | 中 | 低 | 2-5x | 低 |
| Numba 加速 clustering | 低 | 高 | 10-20x | 中（需要 Numba 依赖）|

## 4. 实施步骤

### 第 1 阶段：向量化 `_abs_window()`（立即实施）

1. 实现 `_abs_window_vectorized()`
2. 替换 `peaklets.py` 中的调用
3. 运行回归测试：`pytest tests/plugins/test_plugins.py -k peaklet`
4. 升级 `PeakletPlugin.version` → `1.1.0`

### 第 2 阶段：优化 cluster 计算（可选）

**选项 A：** Context 缓存（快速，但不够优雅）
**选项 B：** 新增 `peaklet_clusters` 插件（推荐，符合架构）

### 第 3 阶段：批量 record 查找（可选）

在 `PeakletWaveformPlugin._build()` 中实施。

## 5. 测试策略

### 5.1 性能基准测试

```python
import timeit
from waveform_analysis.core.plugins.builtin.cpu.peaklets import _abs_window, _abs_window_vectorized

# 对比测试
n = 1000
merged = create_test_data(n)

t_old = timeit.timeit(lambda: _abs_window(merged), number=100)
t_new = timeit.timeit(lambda: _abs_window_vectorized(merged), number=100)

print(f"旧版本: {t_old/100*1000:.3f} ms")
print(f"新版本: {t_new/100*1000:.3f} ms")
print(f"提升: {t_old/t_new:.1f}x")
```

### 5.2 正确性测试

```python
def test_abs_window_vectorized_correctness():
    """确保向量化版本与原版本输出一致。"""
    merged = create_test_data(100)

    starts_old, ends_old = _abs_window(merged)
    starts_new, ends_new = _abs_window_vectorized(merged)

    np.testing.assert_array_equal(starts_old, starts_new)
    np.testing.assert_array_equal(ends_old, ends_new)
```

### 5.3 集成测试

运行完整的 peaklet 处理链：
```bash
pytest tests/plugins/test_plugins.py::test_peaklet_plugin -v
pytest tests/plugins/test_plugin_set_peaks_compat.py -v
```

## 6. 风险与缓解措施

### 6.1 缓存失效风险

**风险：** 如果 `hit_merged` 配置变化，缓存的 cluster 结果可能失效。

**缓解：**
- 方案 A：在缓存 key 中包含配置参数
- 方案 B：使用独立插件（推荐），由插件系统自动管理缓存 lineage

### 6.2 dtype 兼容性

**风险：** 向量化版本可能对输入 dtype 更敏感。

**缓解：**
- 保留字段名回退逻辑
- 添加更全面的测试覆盖

### 6.3 数值精度

**风险：** 向量化计算的浮点运算顺序可能与循环版本略有不同。

**缓解：**
- 使用 `np.testing.assert_allclose()` 而非 `assert_array_equal()`
- 允许合理的浮点误差（eps=1e-9）

## 7. 后续优化方向

1. **流式处理优化：** 当前 `_materialize_array()` 强制物化所有数据，考虑真正的流式 peaklet 构建
2. **内存布局优化：** 减少中间数组分配，使用 in-place 操作
3. **并行化：** 对于多通道数据，考虑并行处理每个通道的 peaklet

## 8. 参考

- 源文件：`waveform_analysis/core/plugins/builtin/cpu/peaklets.py`
- 相关优化：`hit_merge.py` 的 Numba 加速实现
- 测试：`tests/plugins/test_plugins.py`
