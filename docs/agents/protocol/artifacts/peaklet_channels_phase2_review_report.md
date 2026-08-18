# review_report

- `task_id`: `peaklet_channels_phase2`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `reviewer`: `reviewer`
- `gate_results`:
  - `peaklet_channels_oracle`: PASS；定向 15 tests、随机 dense/generic 对照、异常 fallback、signed/clipped、冲突和零面积覆盖。
  - `downstream_tests`: PASS；107 passed、2 deselected；1 个 site documentation 断言失败，命中无关的既有 site-doc-generator 重构。
  - `compileall_ruff_black`: PASS（任务代码、共享 Numba、定向测试）。
  - `assess_change_impact`: PASS；peaklet_channels lineage risk=low，dtype/depends_on 未改变。
  - `schema_compat_smoke`: PASS；dtype changes=0，smoke chain 正常。
  - `docs_generation`: PASS；agent/auto peaklet_channels 文档与索引为 2.0.3。
  - `doc_render`: PASS（pyroot）；`doc_sync`: 系统 Python 过旧导致脚本语法错误，pyroot render 通过。
  - `doc_anchors`: PASS（errors=0）；仅无关 `context.py` 变更产生 warning。
  - `performance_matrix_1M`: PASS；优化版 16 threads median 0.039488 s，2.0.2 median 0.257944 s，提升约 84.7%，1/8/16/32/64/192 threads 均低于 0.21 s，输出逐字段相等。
  - `synthetic_mixed_95_5`: PASS；已有 warm-JIT 记录优化版 0.002470 s vs 2.0.2 0.165269 s，输出逐字段相等。
  - `full_00196_optimized`: PASS；3 次 median 7.7066 s，hash `fea1d5107bd2cb98b1292c1fb4d312197096dfe12354b7e541805d0e960b8b38`，与 2.0.2 严格 oracle 缓存逐字节一致，增量 RSS 3.55–3.59 GB。
  - `full_00196_baseline`: BLOCKED；动态加载 2.0.2 在完整 global matching/lexsort 阶段 OOM，无法完成计划要求的 3 次 baseline median/RSS。
  - `performance_regression_check`: BLOCKED；无关 `hit_threshold` RSS +188.99% 既有回归。
- `decision`: `blocked`
- `blocking_findings`:
  - strict gate 要求的完整 00196 旧版 3 次基线无法在当前内存环境完成；因此不能证明完整 run 的 median improvement 和 RSS 不高于旧版。
  - 仓库现有 site-doc-generator 重构使一个文档测试失败，且性能回归脚本命中无关 hit_threshold RSS 回归。
- `residual_risks`:
  - 需要在足够内存且无上述 dirty refactor 干扰的环境重新运行 2.0.2/2.0.3 完整 00196 三次对照。
  - 当前工作区的无关 dirty 文件未纳入本任务提交，后续整仓库发布前仍需单独收敛。
- `follow_up_actions`:
  - 在隔离的 baseline 环境执行完整 00196 旧版/新版各 3 次，记录 median、hash 和 peak RSS。
  - 处理 site-doc-generator 与 hit_threshold 的既有回归后重跑仓库级固定闸门。
- `agent_profile`: `graph_engineer`
- `agent_profile_review`: 局部 CSR key 排序、Numba count/fill、canonical reduce 与 Python fallback 均保持单层并行；无全局线程数修改；area 使用 NumPy reduceat 保持 oracle 位级结果；计划中的真实乱序 CSR 场景已覆盖。

## Rework Control

- `scope_changed`: `false`
- `required_fixes`:
  - 不扩大本任务 scope；只需补齐隔离环境中的 baseline 性能证据。
- `gates_to_rerun`:
  - `full_00196_baseline`
  - `performance_regression_check`
  - 受 site-doc-generator 影响的文档测试与 doc sync

## Optional Notes

- `version_review`: PASS；`2.0.2 -> 2.0.3`，性能/内部算法变更按 PATCH 升级。
- `contract_review`: PASS；provides、depends_on、options、dtype、输出顺序和错误诊断保持兼容。
- `docs_review`: PASS；两套插件文档及 agent 索引同步，未将无关生成器漂移纳入任务。
- `performance_style_review`:
  - `single_parallel_layer`: `pass`
  - `numba_parallel_evidence`: `pass`
  - `worker_option_review`: `pass`
  - `fallback_review`: `pass`
- `completion_allowed`: `false`
