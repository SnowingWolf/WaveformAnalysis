# hit_merged_features Phase 4 优化说明

**日期**: 2026-06-05
**状态**: 已完成

## 背景

`benchmark_hit_merged_features_phase4_comparison.txt` 对比了 Phase 3 Numba 单 pass
实现和 Phase 4 候选优化。候选优化包含：

1. `parallel=True` / `prange`
2. `fastmath=True`
3. `polarity` 解析向量化

基准结论显示 `hit_merged_features` 的主耗时来自 `wave_pool` 顺序读，是 memory-bound
任务。`parallel=True` 对大多数场景只有很小收益，Medium dataset 还出现退化，因此本阶段
不采用多线程并行作为默认实现。

## 本次落地策略

Phase 4 按 benchmark 结论收敛为：

1. **保留 `fastmath=True`**：对 Numba 核心启用浮点优化，输出字段和 dtype 不变。
2. **回退 `parallel=True`**：主循环继续使用单线程 `range`，避免 memory-bound 场景下的线程调度和内存带宽竞争。
3. **保留 `polarity` 向量化解析**：对 `S` / `U` 字符串 dtype 使用 NumPy 比较批量生成 sign 数组，对其他 dtype 保留兼容 fallback。

## 性能判断

Phase 4 benchmark 的关键结果：

| 场景 | Phase 3 | Phase 4 候选 | 结论 |
| --- | ---: | ---: | --- |
| Medium dataset | 107.42 ms | 116.01 ms | `parallel=True` 退化 1.08x |
| Large dataset | 1080.67 ms | 1043.52 ms | 仅提升 1.03x |
| High component count | 156.61 ms | 151.35 ms | 仅提升 1.03x |
| Low component count | 77.13 ms | 72.78 ms | 提升 1.06x |

这些结果不足以抵消并行路径的复杂度和小数据集 JIT/调度开销，因此最终实现采用
`@nb.njit(cache=True, fastmath=True)`，不使用 `parallel=True`。

## 契约影响

- `provides` 不变：`hit_merged_features`
- `depends_on` 不变
- `options` 不变
- `HIT_MERGED_FEATURES_DTYPE` 不变
- 插件版本保持 Phase 3 已升级后的 `0.3.0`

## 验证

定向验证：

```bash
pytest tests/plugins/test_hit_merged_features_plugin.py -v
```

新增覆盖：

- positive polarity 的直接窗口主路径
- `polarity` 为 Unicode 字符串 dtype 的向量化解析
- `polarity` 为 bytes 字符串 dtype 的向量化解析

## 文件清单

- 插件实现：`waveform_analysis/core/plugins/builtin/cpu/hit_merged_features.py`
- 测试：`tests/plugins/test_hit_merged_features_plugin.py`
- benchmark 对比：`benchmark_hit_merged_features_phase4_comparison.txt`
