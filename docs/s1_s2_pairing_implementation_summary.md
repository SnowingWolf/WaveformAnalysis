# S1-S2 配对插件实现总结

## 完成状态

✅ **Phase 1 已完成**: S1S2PairCandidatesPlugin (候选生成层)

## 实现概览

### 1. 核心插件: `S1S2PairCandidatesPlugin`

**文件位置**: `waveform_analysis/core/plugins/builtin/cpu/s1_s2_pair_candidates.py`

**功能**: 生成所有物理允许的 S1-S2 配对候选对

**关键特性**:
- ✅ S2-anchor 设计 (以 S2 为基准向前搜索 S1)
- ✅ 高效二分搜索算法 (时间复杂度 O(M log N))
- ✅ 完整的 30 字段数据结构
- ✅ Ambiguity 统计 (多候选、竞争情况)
- ✅ 孤立信号处理
- ✅ 时间窗口筛选
- ✅ 可选的面积阈值筛选

### 2. 数据结构: `S1_S2_PAIR_CANDIDATES_DTYPE`

**30 个字段**,分为 6 类:
- **Identity** (5): pair_id, s1_peak_id, s2_peak_id, s1_index, s2_index
- **Timing** (4): s1_time, s2_time, drift_time (ps), drift_time_ns
- **Observables** (7): areas, log10_s2_s1, widths, n_channels
- **Scores** (7): score_total, score_time, score_s1_quality, 等 (第二层填充)
- **Ambiguity** (5): ranks, n_candidates, delta_score_to_next_best
- **Flags** (2): flags (bit field), selected

### 3. Flags 系统

**10 个 bit flags**:
```python
FLAG_VALID_TIME           # 在时间窗口内
FLAG_RATIO_IN_RANGE       # S2/S1 在合理范围
FLAG_S1_LOW_QUALITY       # S1 质量低
FLAG_S2_LOW_QUALITY       # S2 质量低
FLAG_MULTI_S1_CANDIDATE   # 该 S2 有多个 S1 候选
FLAG_MULTI_S2_CANDIDATE   # 该 S1 有多个 S2 候选
FLAG_CLOSE_COMPETITOR     # 次优候选分数接近
FLAG_ORPHAN_S1            # 孤立 S1
FLAG_ORPHAN_S2            # 孤立 S2
FLAG_NEAR_CHUNK_BOUNDARY  # 接近数据块边界
```

### 4. 测试覆盖

**文件位置**: `tests/plugins/test_s1_s2_pairing.py`

**9 个测试用例**:
- ✅ test_basic_pairing_one_to_one
- ✅ test_multiple_s1_for_one_s2
- ✅ test_time_window_filtering
- ✅ test_causality_s2_before_s1
- ✅ test_empty_input
- ✅ test_orphan_s1
- ✅ test_orphan_s2
- ✅ test_min_area_threshold
- ✅ test_log10_s2_s1_calculation

**测试结果**: 9/9 通过 ✅, 覆盖率 85%

### 5. 使用示例

**文件位置**: `examples/demo_s1_s2_pairing.py`

**演示内容**:
- 创建测试数据 (2 S1, 3 S2)
- 生成候选对
- 分析 ambiguity (多候选情况)
- 识别孤立信号

**运行结果**:
```
输入: 2 S1, 3 S2
输出: 4 个候选对
- S2_10: 2 个 S1 候选 (drift_time: 18-19 μs)
- S2_11: 2 个 S1 候选 (drift_time: 23-24 μs)
- S2_12: 孤立 (超出时间窗口)
```

---

## 配置选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `max_drift_time` | 50000.0 ns | 最大漂移时间 (50 μs) |
| `min_drift_time` | 0.0 ns | 最小漂移时间 |
| `time_field` | "center_time" | 使用的时间字段 |
| `min_s1_area` | None | S1 最小面积阈值 |
| `min_s2_area` | None | S2 最小面积阈值 |
| `allow_orphan_s1` | False | 是否输出孤立 S1 |
| `allow_orphan_s2` | False | 是否输出孤立 S2 |

---

## 核心算法

### S2-anchor + 二分搜索

```python
# 对每个 S2, 向前搜索 S1 候选
for s2 in s2_peaks_sorted:
    s2_time = s2["center_time"]

    # 计算 S1 有效时间范围
    s1_time_min = s2_time - max_drift_ps
    s1_time_max = s2_time - min_drift_ps

    # O(log N) 二分查找
    left = np.searchsorted(s1_times, s1_time_min, side="left")
    right = np.searchsorted(s1_times, s1_time_max, side="right")

    # 只遍历候选范围
    for s1 in s1_peaks_sorted[left:right]:
        create_candidate(s1, s2)
```

**时间复杂度**: O(M log N + K)
- M: S2 数量
- N: S1 数量
- K: 候选总数 (通常 K << M*N)

---

## 下一步: Phase 2

### S1S2PairSelectionPlugin (选择层)

**功能**: 对候选打分并选择最佳配对

**待实现**:
- 打分函数 (score_time, score_s1_quality, score_s2_quality)
- 选择模式 (nearest, largest_s1, best_score, all)
- 设置 selected flag
- 计算 delta_score_to_next_best
- 更新 rank 字段

**预计工作量**: ~200 行代码 + ~150 行测试

---

## 技术亮点

1. **两层架构**: 候选生成与选择分离,打分系统可持续升级
2. **S2-anchor**: 符合事件构建的自然逻辑
3. **高效算法**: 二分搜索 + 时间窗口优化
4. **完整诊断**: 保留所有候选信息,不仅是最终结果
5. **Flags 系统**: 灵活的位标志,便于后续筛选
6. **充分测试**: 9 个测试用例覆盖主要场景

---

## 文件清单

### 新建文件 (3)
- `waveform_analysis/core/plugins/builtin/cpu/s1_s2_pair_candidates.py` (362 行)
- `tests/plugins/test_s1_s2_pairing.py` (337 行)
- `examples/demo_s1_s2_pairing.py` (208 行)

### 修改文件 (1)
- `waveform_analysis/core/plugins/builtin/cpu/__init__.py` (添加导入和导出)

**总计**: ~900 行新代码

---

## 使用方法

```python
from waveform_analysis.core.plugins.builtin.cpu import (
    S1S2PairCandidatesPlugin,
    S1_S2_PAIR_CANDIDATES_DTYPE,
)

# 初始化插件
plugin = S1S2PairCandidatesPlugin()
ctx.register(plugin)

# 配置
ctx.set_config({
    "max_drift_time": 50000.0,  # 50 μs
    "min_drift_time": 0.0,
    "allow_orphan_s2": True,
})

# 生成候选
candidates = ctx.get_data(run_id, "s1_s2_pair_candidates")

# 分析
print(f"候选总数: {len(candidates)}")
print(f"唯一配对: {sum(candidates['n_s1_candidates_for_s2'] == 1)}")
print(f"多候选: {sum(candidates['n_s1_candidates_for_s2'] > 1)}")
```

---

## 验证

所有功能已通过测试验证:
```bash
$ python -m pytest tests/plugins/test_s1_s2_pairing.py -v
================================ 9 passed in 6.93s ================================
```

演示脚本运行正常:
```bash
$ python examples/demo_s1_s2_pairing.py
✓ 生成 4 个候选对
✓ 正确识别 ambiguity
✓ 正确识别孤立 S2
```

---

## 总结

✅ **Phase 1 (候选生成) 已完成**

- 实现了完整的 S1S2PairCandidatesPlugin
- 30 字段的候选数据结构
- 高效的 S2-anchor 二分搜索算法
- 完整的 ambiguity 统计
- 9 个测试用例全部通过
- 提供使用示例和演示

**下一步**: 实现 Phase 2 (S1S2PairSelectionPlugin) 进行候选选择和打分。
