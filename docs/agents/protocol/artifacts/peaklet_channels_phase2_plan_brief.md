# plan_brief

- `task_id`: `peaklet_channels_phase2`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `high`
- `scope_in`:
  - 优化 `peaklet_channels` 的 dense identity / 连续 component 快路径。
  - 用 Numba 双阶段 CSR 统计与填充替代 Python list/tuple 窗口展开。
  - 并行化安全 dense waveform 的 occupied 范围、area、height 归约。
  - 将面积守恒、fraction 写入及 fraction 守恒合并为按 peaklet 并行校验 kernel。
  - 保留 2.0.2 的严格去重、冲突检测、fallback、输出顺序和 dtype。
- `scope_out`:
  - 不新增公开配置，不改变 provides、depends_on、输出字段或缓存产品语义。
  - 不修改无关的既有工作区改动，不执行破坏性清理。
  - 完整 `00196` 仅在小规模门槛通过且数据可用时运行。
- `required_gates`:
  - 合成 oracle 对照：空输入、CSR/fallback、feature 重排、组内乱序、多通道、重复/cross-record、冲突、signed/clipped、零面积、长 S2。
  - warm-JIT 线程矩阵与 1M component / 95% 普通组 + 5% overlap 合成性能门槛。
  - 可用时旧版/优化版 `00196` 各 3 次 hash、median、RSS 对照。
  - 定向 peaklet_channels / 下游测试、Ruff、Black check、compileall。
  - 两套插件文档生成、impact、schema smoke、文档同步与锚点检查、性能回归检查。
- `executor_role`: `executor.plugin`
- `agent_profile`: `graph_engineer`
- `profile_plan`:
  - 仅在 dense identity feature、连续 component slice 且 peaklet/component CSR 可验证时进入双阶段 CSR fast path；组内乱序键在 Numba 局部稳定排序后直接写出，避免全局 lexsort。
  - 任一结构异常、重复/冲突、非 dense 时间轴或超大窗口都回到现有 Python canonical oracle。
  - Numba 只保留一个算法并行层；canonical materialize 串行，归约 kernel 按 group 并行。
- `blocking_assumptions`:
  - Python 环境可导入 NumPy/Numba；若真实 `00196` 数据不存在，记录为环境阻断而不伪造结果。

## Optional Notes

- `change_level`: `L1`
- `provides_impact`: none
- `depends_on_impact`: none
- `output_contract_impact`: none
- `version_action`: `peaklet_channels 2.0.2 -> 2.0.3`
- `docs_sync_required`: true
- `execution_backend_decision`:
  - `backend`: `numpy + numba_serial + numba_parallel`
  - `backend_reason`: `CPU-bound grouping, CSR expansion and dense waveform reduction`
  - `parallel_scope`: `peaklet / independent group`
  - `worker_option`: `none; no global thread-count mutation`
  - `fallback_path`: `existing Python merge_waveform_segments canonical oracle`
  - `benchmark_required`: true
