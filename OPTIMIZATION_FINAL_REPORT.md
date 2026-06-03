# hit_merged 多线程 + Numba 优化最终报告

## 执行时间
2026-06-02

## 完成的工作

### ✅ 添加 Numba JIT 加速
**状态：** 完成
**改动：**
- 新增 `_numba_merge_clusters` JIT 编译函数
- 在集群合并循环中使用 Numba 加速
- 提供 Python 循环作为 fallback
- 添加 `use_numba` 配置选项

**代码位置：**
- 第 47-106 行：Numba JIT 函数定义
- 第 180-370 行：集成到 `_build_merged_clusters`

### ✅ 添加多线程并行处理
**状态：** 完成
**改动：**
- 使用 `ThreadPoolExecutor` 实现通道级并行
- 新增 `_process_channel_group_static` 函数
- 更新为 `BatchProcessingPlugin` 基类
- 添加配置选项：
  - `chunk_parallel`: 是否启用并行（默认 True）
  - `n_workers`: worker 数（默认 0=自动）
  - `parallel_min_hits`: 触发并行的最小 hit 数（默认 5000）

**代码位置：**
- 第 180-280 行：并行处理逻辑
- 第 282-352 行：静态通道处理函数
- 第 498-540 行：配置选项定义

### ✅ 测试结果
- **9/12 测试通过** ✅
- 3 个失败的测试是关于流式处理（chunk stream），这是 `BatchProcessingPlugin` 的行为差异
- 核心功能测试全部通过

---

## 性能对比

| 数据集 | 基线 (hits/s) | 优化后 (hits/s) | 变化 |
|--------|---------------|-----------------|------|
| 小数据集 (1k) | 82,211 | 16,913 | **-79%** ❌ |
| 中数据集 (10k) | 82,780 | 56,017 | -32% |
| 大数据集 (100k) | 72,857 | 59,958 | -18% |
| 高合并率 | 95,380 | 63,273 | -34% |
| 低合并率 | 68,146 | 49,923 | -27% |

**结论：** 性能显著下降，优化失败 ❌

---

## 失败原因分析

### 1. **小数据集不适合 Numba**
- Numba 阈值设为 100 个 hits
- 小数据集（1k hits）仍然被拆分成多个小通道组
- 每个通道组 < 100 hits → 使用 Python 循环
- Python 循环 + 额外的数组创建开销 → 性能下降

### 2. **多线程开销**
- `ThreadPoolExecutor` 创建和管理开销
- 通道数量较少（4-32 个）
- 线程切换开销 > 并行收益

### 3. **数据转换开销**
- 为了调用 Numba，需要从 `list[dict]` 提取为 numpy 数组
- `np.array([x["abs_start_ps"] for x in enriched], dtype=np.float64)` × 3
- 额外的内存分配和拷贝

### 4. **GIL 限制**
- Python 的 `ThreadPoolExecutor` 受 GIL 限制
- CPU 密集型任务无法真正并行
- 应该使用 `ProcessPoolExecutor` 或纯 Numba 并行

---

## 关键发现

### ❌ 不适合的优化策略

1. **ThreadPoolExecutor for CPU-bound tasks**
   - Python GIL 限制了真正的并行
   - 线程切换开销大于收益

2. **Numba + dict/list 数据结构**
   - Numba 需要 numpy 数组
   - 数据转换开销抵消了 JIT 收益

3. **小数据集并行化**
   - overhead > speedup
   - 并行阈值（5000 hits）仍然太低

### ✅ 正确的优化方向

1. **完全重构为 Numba + numpy 数组**
   - 类似 `hit_threshold` 的实现
   - 所有数据用结构化数组
   - 避免 Python 对象

2. **使用 ProcessPoolExecutor**
   - 绕过 GIL 限制
   - 适合大数据集

3. **提高并行阈值**
   - parallel_min_hits: 5000 → 50000
   - 避免小数据集的线程开销

---

## 推荐方案

### 选项 A: 回滚所有改动 ✅ **推荐**
**原因：**
- 当前优化降低了性能
- 复杂度增加，维护成本高
- 测试失败（流式处理）

**操作：**
```bash
git checkout waveform_analysis/core/plugins/builtin/cpu/hit_merge.py
```

### 选项 B: 保留框架，调整参数
**改动：**
- 提高 `parallel_min_hits`: 5000 → 100000
- 提高 Numba 阈值：100 → 1000
- 默认禁用并行：`chunk_parallel: False`

**预期：**
- 小数据集恢复到基线性能
- 大数据集可能有轻微提升

### 选项 C: 完全重构（参考 hit_threshold）
**工作量：** 数天
**收益：** 5-10x 性能提升（需要 profiling 验证）
**风险：** 高，需要大规模测试

---

## 经验教训

### 1. **先 Profile 再优化**
我们应该先用 `cProfile` 或 `py-spy` 找出真正的瓶颈：
- 是排序？
- 是集群合并循环？
- 是字典访问？

### 2. **理解 Python GIL**
- `ThreadPoolExecutor` 不适合 CPU 密集型任务
- 多线程只对 I/O 密集型有效

### 3. **Numba 的使用场景**
- 需要纯 numpy 数组
- 不适合 dict/list 数据结构
- JIT 编译有首次开销

### 4. **优化的陷阱**
- 小优化可能引入大开销
- 复杂度 ≠ 性能
- 测试覆盖很重要

---

## 下一步建议

**立即行动：**
1. ✅ 回滚所有改动
2. ✅ 保留性能测试脚本
3. ✅ 编写 profiling 脚本

**未来优化（如果真的需要）：**
1. **Profile 找瓶颈**
   ```python
   import cProfile
   cProfile.run('plugin.compute(ctx, run_id)', sort='cumtime')
   ```

2. **针对性优化**
   - 如果瓶颈是排序 → 优化排序
   - 如果瓶颈是循环 → Numba
   - 如果瓶颈是数据结构 → 重构为数组

3. **参考 hit_threshold 实现**
   - 完全基于 numpy 数组
   - Numba JIT 核心循环
   - 预分配内存

---

## 文件清单

### 修改的文件（建议回滚）
- `waveform_analysis/core/plugins/builtin/cpu/hit_merge.py`
  - 添加了 Numba JIT
  - 添加了多线程支持
  - 改为 BatchProcessingPlugin

### 保留的文件
- ✅ `benchmark_hit_merged.py` - 性能测试脚本
- ✅ `OPTIMIZATION_SUMMARY.md` - Phase 1-2 总结
- ✅ `OPTIMIZATION_FINAL_REPORT.md` - 本报告
- ✅ `.claude/plans/hit_merged_optimization.md` - 原始计划
- ✅ 性能数据文件（baseline, phase1, phase2, numba+thread）

---

## 性能数据汇总

| 阶段 | 大数据集 (100k hits/s) | 变化 vs 基线 |
|------|------------------------|-------------|
| 基线（原始代码） | **72,857** | - |
| Phase 1 (float32) | 53,853 | -26% |
| Phase 2 (结构化数组) | 31,308 | -57% |
| Phase 3+4 (Numba+Thread) | 59,958 | **-18%** |

**结论：** 所有优化尝试都降低了性能，应该回滚。

---

## 真实的性能提升路径

基于 `hit_threshold` 的成功经验，正确的做法是：

1. **完全重构数据结构**
   - 不用 `list[dict]`，全用结构化 numpy 数组
   - 避免任何 Python 对象

2. **Numba 覆盖所有核心循环**
   - enriched hits 构建 → Numba
   - 排序 → numpy 原生（已经很快）
   - 集群合并 → Numba

3. **预分配内存**
   - 两遍扫描：第一遍计数，第二遍填充
   - 避免动态增长

4. **流式处理支持**
   - 分块处理大数据集
   - 恒定内存占用

**预期收益：** 3-5x 性能提升
**工作量：** 3-5 天
**风险：** 中等（需要完整的测试覆盖）

---

## 致谢

本次优化尝试虽然失败，但提供了宝贵的经验：
- ✅ 建立了性能测试框架
- ✅ 理解了 Python 并行的限制
- ✅ 学习了 Numba 的正确用法
- ✅ 认识到 profiling 的重要性

失败也是一种成功 🎓
