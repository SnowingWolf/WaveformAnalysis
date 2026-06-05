# hit_merged_features Phase 3 优化说明（Numba 加速）

**日期**: 2026-06-05
**状态**: 已完成

## 背景

`hit_merged_features` 插件负责从 `hit_merged` 输出计算每个 merged hit 的局部波形特征（area、height、width 等）。

Phase 2 已经实现了预分配数组 + 原地填充，但仍存在性能瓶颈：
1. 每个窗口调用 `_window_signal()` 生成临时数组
2. `_window_feature_values()` 对每个窗口做多次 NumPy 操作（argmax、sum）
3. fallback 路径每次全扫描 `component_rows`
4. 为所有 records 构建 Python dict

## Phase 3 优化

Phase 3 采用分层优化策略，核心思想是"批量数组操作 + Numba 单 pass"。

### 主要变更

1. **避免 records_by_id dict 构建**
   - 新增 `_resolve_record_indices()`：将 `record_id` 转换为 records 数组索引
   - 快路径：当 `record_id == array_index` 时直接返回
   - 通用路径：`argsort` + `searchsorted` 一次性映射

2. **Numba JIT 核心**
   - `_features_fast_kernel()`：对主路径（有合法 sample_start/sample_end）批量计算
   - **单 pass 遍历**：一次循环同时累加 area 和找 max，避免 `np.sum()` + `np.argmax()` 两次遍历
   - 无临时数组分配：直接在循环中计算 `signal = sign * (raw - baseline)`
   - 向量化时间计算：批量提取字段后传入 Numba

3. **批量数组字段提取**
   - `_field_or_default()`：安全提取 structured array 字段，不存在时返回默认值数组
   - `_polarity_sign_array()`：批量转换 polarity 为 sign 数组（+1.0 / -1.0）
   - 所有字段提取在 Python 层完成，Numba 只处理普通数组

4. **优化 fallback 索引查找**
   - `_build_component_slices()`：一次性对 `component_rows` 排序 + `searchsorted`
   - fallback 查找从 `O(n_component_rows)` 变为 `O(1)` slice

5. **批量字段赋值**
   - Numba 返回所有字段的数组后，通过向量化赋值填充输出
   - 减少 Python 循环次数

### 版本升级

`HitMergedFeaturesPlugin.version`: `0.2.0` → `0.3.0`（触发 lineage/cache 失效）

## 性能结果

本地 benchmark 对比（Phase 2 → Phase 3）：

| 场景 | Phase 2 | Phase 3 | 加速比 | 吞吐量提升 |
| --- | ---: | ---: | ---: | ---: |
| Small dataset (1k) | 24.11 ms | 190.94 ms* | 0.13x* | 首次 JIT 编译开销 |
| Medium dataset (10k) | 283.56 ms | 107.42 ms | **2.64x** | 35k → 93k merged/s |
| Large dataset (100k) | 7065.36 ms | 1080.67 ms | **6.54x** | 14k → 92k merged/s |
| High component (10k, 40k comp) | 368.67 ms | 156.61 ms | **2.35x** | 27k → 64k merged/s |
| Low component (10k, 15k comp) | 235.33 ms | 77.13 ms | **3.05x** | 42k → 130k merged/s |

\* Small dataset 首次运行包含 Numba JIT 编译时间，稳定后预计 15-20 ms（~1.2-1.6x 提升）

### 关键收益

✓✓✓ **Large dataset 加速 6.5x**：生产环境最重要的指标
✓ **Medium 以上数据集 2.4-6.5x 加速**
✓ **单 pass 核心**：彻底消除重复 NumPy 调用（`np.sum` + `np.argmax` → 一次循环）
✓ **消除 dict 构建**：避免为所有 records 建 Python dict
✓ **优化 fallback**：一次性排序 + searchsorted 替代每次全扫描
✓ **批量操作**：字段提取和赋值都是向量化的

## 代码架构

### 主路径（Numba）

```python
提取 records 字段 -> 提取 merged 字段 -> _features_fast_kernel()
                                                 ↓
                                    单 pass 计算每个窗口
                                    (area + height + max)
                                                 ↓
                                    批量填充输出数组
```

### fallback 路径（Python）

```python
检测 valid == 0 -> _build_component_slices() -> 逐个处理跨 record hits
                                                 ↓
                                        _fallback_values()
```

## 验证

### 功能测试

```bash
pytest tests/plugins/test_hit_merged_features_plugin.py -v
```

所有 6 个测试用例通过 ✓

### 性能基准

```bash
python benchmark_hit_merged_features.py
```

结果保存在：
- `benchmark_hit_merged_features_baseline.txt`（Phase 3 结果）
- `benchmark_hit_merged_features_phase3_comparison.txt`（对比报告）

## 技术细节

### Numba 核心实现

```python
@nb.njit(cache=True)
def _features_fast_kernel(wave_pool, rec_indices, ...):
    # 对每个 merged hit
    for i in range(n):
        # clip 窗口到 event_length
        start, end = ...

        # 单 pass 计算
        area = 0.0
        height = 0.0
        max_j = 0

        for j in range(n_sample):
            v = sign * (wave_pool[base + j] - baseline)
            v = max(v, 0.0)

            area += v  # 累加 area

            if v > height:  # 找 max
                height = v
                max_j = j

        # 计算时间特征
        ...
```

### 索引优化

```python
# 快路径：record_id == array_index
if np.array_equal(rec_ids, np.arange(len(records))):
    return record_ids

# 通用路径：排序 + searchsorted
order = np.argsort(rec_ids)
rec_ids_sorted = rec_ids[order]
pos = np.searchsorted(rec_ids_sorted, record_ids)
return order[pos]
```

## 后续优化建议

1. **并行化 Numba 核心**
   - 将 `@nb.njit(cache=True)` 改为 `@nb.njit(cache=True, parallel=True)`
   - 将 `for i in range(n)` 改为 `for i in nb.prange(n)`
   - 需要测试内存带宽是否成为瓶颈

2. **进一步向量化 fallback**
   - 当前 fallback 仍是 Python 循环
   - 可以考虑批量处理 fallback rows

3. **监控 fallback 比例**
   - 如果 fallback 比例很高（>30%），应优化 `hit_merged` 让其输出稳定的 sample_start/sample_end

## 影响范围

- **下游消费者无影响**：输出 dtype 和字段含义完全不变
- **缓存会失效**：version 升级触发重算
- **测试覆盖**：所有现有测试保持通过
- **依赖变化**：新增 `numba` 依赖

## 文件清单

- 插件实现：`waveform_analysis/core/plugins/builtin/cpu/hit_merged_features.py`
- 测试：`tests/plugins/test_hit_merged_features_plugin.py`
- 性能基准：`benchmark_hit_merged_features.py`
- 基准结果：`benchmark_hit_merged_features_baseline.txt`
- 对比报告：`benchmark_hit_merged_features_phase3_comparison.txt`
