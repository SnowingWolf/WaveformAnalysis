# hit_merged Phase 3 优化说明

**日期**: 2026-06-05
**状态**: 已完成

## 背景

`hit_merged` 在 `merge_gap_ns > 0` 时会把 `hit_threshold` 输出按 `(board, channel)` 分组，并根据绝对时间窗口生成 `hit_merge_clusters`。旧实现构建最终 `hit_merged` 输出时先逐 cluster 生成 tuple，再通过 `np.array(..., dtype=HIT_MERGED_DTYPE)` 一次性转换为结构化数组。

在中大型输入或低合并率场景下，cluster 数量较多，tuple 列表和最终结构化数组转换会放大 Python 层分配与拷贝成本。

## 本次优化

本次优化保持 `hit_merged` 的 public contract 不变：`provides`、`depends_on`、`options` 与 `HIT_MERGED_DTYPE` 均不变，只调整内部构建路径。

主要变更：

1. 新增 `_build_merged_from_cluster_rows()`，按 cluster 数量预分配 `HIT_MERGED_DTYPE` 输出数组。
2. 将旧的 tuple 返回路径改为原地填充结构化数组字段，避免 list append 后再整体转换。
3. 拆分 `_fill_single_hit_merged()` 与 `_fill_multi_hit_merged()`，让单 hit cluster 走更直接的字段复制路径。
4. 多 hit cluster 直接通过原始 `hits` 与 `hit_indices` 取数，减少传递 `hits[hit_indices]` 临时数组。
5. 删除旧 `_emit_cluster()` 路径，收敛输出构建逻辑。

由于核心算法内部路径发生变化，`HitMergePlugin.version` 升级到 `1.1.2`，用于触发 lineage/cache 失效。

## 性能结果

本地 benchmark 文件记录了 Phase 2 到 Phase 3 的对比结果：

| 场景 | Phase 2 | Phase 3 | 结果 |
| --- | ---: | ---: | --- |
| Small dataset, 1,000 hits | 31.18 ms | 57.44 ms | 退化 1.84x |
| Medium dataset, 10,000 hits | 313.64 ms | 96.59 ms | 提升 3.25x |
| Large dataset, 100,000 hits | 3194.12 ms | 1000.34 ms | 提升 3.19x |
| High merge rate, 10,000 hits | 249.92 ms | 72.76 ms | 提升 3.44x |
| Low merge rate, 10,000 hits | 357.02 ms | 102.14 ms | 提升 3.50x |

结论：

- 中大型数据集和大量 cluster 场景收益明显，主要来自减少 Python tuple/list 与结构化数组转换开销。
- 小数据集有退化，但绝对耗时仍在几十毫秒量级；该路径的优化目标是中大型批量处理。
- 输出字段和下游消费方式不变，`hit_merged_components`、`hit_grouped`、`hit_merged_features`、`peaklets` 不需要迁移。

## 代码与验证

代码位置：

- `waveform_analysis/core/plugins/builtin/cpu/hit_merge.py`

相关产物：

- `benchmark_hit_merged_baseline.txt`
- `benchmark_hit_merged_phase3_comparison.txt`

建议验证：

```bash
pytest -q tests/plugins/test_hit_merge_plugin.py tests/plugins/test_hit_merge_pretrigger.py
waveform-docs generate plugins-agent --plugin hit_merged
python scripts/render_agent_docs.py --check
```

发布或 PR 前如需覆盖性能回归，再执行：

```bash
python scripts/performance_regression_check.py --base HEAD --targets hit_merged
```
