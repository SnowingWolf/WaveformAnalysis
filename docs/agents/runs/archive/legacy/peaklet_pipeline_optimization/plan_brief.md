# plan_brief

- `task_id`: `peaklet_pipeline_optimization`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `high`
- `scope_in`:
  - 将 `hit_threshold` 的自动 ragged chunk worker 数限制在有证据的 bounded 上限内（当前上限 64）；显式 `n_workers > 0` 语义保持不变。
  - 降低 records-backed `RecordLookup` identity 检测的临时数组峰值。
  - 降低 `peaklet_channels` dense CSR 路径的 board/channel dtype widening 和 fraction 校验临时数组驻留。
  - 让 `hit_threshold` 并行 chunk 结果按序限量驻留，避免全量 `parts` 与最终 `concatenate` 同时占用输出内存。
  - 保持 `peaklet_channels` 输出顺序、dtype、hash、冲突检测、fallback、异常文本和缓存 lineage 语义不变。
- `scope_out`:
  - 不新增公开配置，不修改 provides、depends_on、字段或正式产品格式。
  - 不改变全局 Numba 线程数，不触碰无关 dirty 文件或正式缓存。
  - 不把冲突 canonical materialize 改成并行写入，不弱化旧版严格去重/冲突语义。
- `required_gates`:
  - hit_threshold 与 peaklet_channels 定向测试、空/异常/fallback/oracle 测试。
  - warm-JIT 合成性能与现有 00196 只读缓存 hash 对照。
  - `waveform-docs` 两套生成、impact、schema smoke、doc sync、anchors、Ruff、Black、compileall。
  - 性能回归检查；无关既有阻断必须在报告中单独记录。
- `executor_role`: `executor.plugin`
- `agent_profile`: `graph_engineer`
- `profile_plan`:
  - `hit_threshold`: `numba_parallel` 内部只保留 chunk 并行层；自动 worker 使用 bounded default，显式配置优先。
  - `RecordLookup`: 分块检查 identity，避免为全量 records 创建等长 `arange`。
  - `peaklet_channels`: Numba kernel 接受原生 board/channel dtype；校验 kernel 仅保留必要 mismatch flags，失败时再计算异常文本所需标量。
  - 所有结构异常和冲突仍走现有 Python canonical oracle。
- `blocking_assumptions`:
  - NumPy/Numba 环境可用；完整旧版 00196 baseline 可能因历史 OOM 仍无法取得，不能伪造对照。

## Optional Notes

- `change_level`: `L1`
- `provides_impact`: none
- `depends_on_impact`: none
- `output_contract_impact`: none
- `version_action`: `hit_threshold 1.2.0 -> 1.2.1`; `peaklet_channels 2.0.3 -> 2.0.4`
- `docs_sync_required`: true
- `execution_backend_decision`:
  - `backend`: `numba_parallel + numpy views`
  - `backend_reason`: `CPU/memory-bound; measured worker oversubscription and large temporary arrays`
  - `parallel_scope`: `chunk / peaklet`
  - `worker_option`: `existing n_workers only; no new public option`
  - `fallback_path`: `existing generic matching and Python canonical oracle`
  - `benchmark_required`: true
