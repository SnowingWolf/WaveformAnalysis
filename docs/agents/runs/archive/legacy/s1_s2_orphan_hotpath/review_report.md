# review_report

- `task_id`: `s1_s2_orphan_hotpath`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `reviewer`: `reviewer (Luna Max)`
- `gate_results`:
  - `initial_review`: `REWORK_REQUIRED` - 初审发现 pairs 的 `nearest`/`best_score` 评分范围被 orphan 哨兵改变，且最终 refinement 后的 00196 hash 和明确 commit handoff 尚未闭环。
  - `focused_candidate_pairs_position_events_energy_tests`: `PASS` - 复审独立运行 74 passed（含 shim/downstream 与 nearest/best_score × require 开关回归）。
  - `orphan_random_legacy_oracle`: `PASS` - 200 组随机输入 × 4 种 orphan 开关组合（共 800 次）逐字段比较一致。
  - `single_side_membership_mask`: `PASS` - 两个单侧场景各只调用启用侧 `np.isin`；双侧调用 2 次，双侧关闭调用 0 次。
  - `candidate_dtype_fields_order_sentinels_flags`: `PASS` - 混合、空、单类、重复/无序 ID 的 oracle 一致；dtype 仍为 `S1_S2_PAIR_CANDIDATES_DTYPE`。
  - `pairs_negative_id_filter_and_all_mode`: `PASS` - 任一负 ID（含 -2/-3）在复制前过滤；`selection_mode=all` 仅输出完整 pair、全部 selected，且输入不原地修改。
  - `complete_pair_score_rank_selected_invariance`: `PASS` - 返工通过 `_legacy_drift_bounds` 在过滤前保存旧 area-filter 后全集的 min/max；复审确定性反例及 1000 组随机唯一 ID sentinel 输入中，nearest/best_score 的完整 pair score、rank、selected 与旧逻辑一致。
  - `version_manifest_docs_consistency`: `PASS` - code、manifest、Agent/Auto 页面一致：candidate `0.2.0`，pairs `0.3.0`；返工后的 pairs source fingerprint 已同步。
  - `run_00196_final_hash_evidence`: `PASS_WITH_SCOPE_LIMITATION` - execution report 已记录最终代码的只读 memmap 对照：14,875,145 行、2,037,894,865 bytes、dtype/逐字段无 mismatch、SHA-256 `b5e12802bd2026654fb0e947b79cbf1644cb9d72e4cb13e6f88c56a1ad82fd77`；完整 pair 121,573 行，未写入正式缓存。
  - `assess_change_impact`: `PASS_WITH_LIMITATION` - 复审以 `0bde2c7^` 运行，2 个低 lineage risk；该脚本只识别 version 变化，内部 score 语义由定向回归补足。
  - `schema_compat_check_smoke`: `PASS` - 复审以 `0bde2c7^` 运行，dtype changes `0`，smoke chain 通过。
  - `black_ruff_compileall`: `PASS` - 复审独立运行，任务 Python 文件 Black/Ruff 与 `compileall` 通过。
  - `render_agent_docs_doc_sync_doc_anchors`: `PASS` - render、doc sync、anchors（0 errors/0 warnings）通过。
  - `plugin_doc_coverage_and_links`: `PASS` - 36/36 coverage、0 warning/error，496 个本地引用有效。
  - `execution_commit_handoff`: `PASS` - execution report 明确记录原实现 `0bde2c70062908fdfd31498ff01d128837d00ff0` 与返工实现 `59470d032c4f07704105f3e2636bf9e20e280703` 两个完整 40 位 SHA。
- `decision`: `completed`
- `blocking_findings`:
  - `none` - 初审三项阻断均已解除。
- `residual_risks`:
  - 00196 验证使用既有 cache 的只读 memmap，未进行新版 lineage 正式缓存的全量落盘/重物化；这符合本任务“不写/删正式缓存”的范围，但发布环境仍应自行执行缓存物化验证。
  - 00196 candidate `6.1222 s` 与选择 `1.0692 s` 是本次只读运行测量；报告没有把它们宣称为可与不同 page-cache 状态直接比较的端到端加速基准。100k old/new synthetic benchmark 和最终 hash 才是本变更的主要性能/等价证据。
  - `waveform-docs` console script 在当前 shell 不可用；同一 CLI 的 pyroot-kernel module invocation 已完成生成、coverage 与 links，若发布环境要求 console-script 入口需确认安装方式。
  - 选择过程中既有非正 S1 area 的 `log1p` warning 仍存在，不由本返工引入。
- `follow_up_actions`:
  - 发布或切换缓存前，在目标环境按当前两个新版本重新物化并检查 lineage；不要把本次 read-only 对照误当作正式缓存落盘验证。
  - 若未来改变 orphan QA 产品语义（例如从 candidate 主表移出），另起配置/产品迁移任务，不并入本次性能修复。
- `agent_profile`: `graph_engineer`
- `agent_profile_review`: `dependency_direction=pass`（candidate -> pairs -> position/events/energy 方向未变）；`runtime_vs_display_semantics=pass`（无展示变换混入运行时依赖）；`cross_renderer_consistency=pass`（Agent/Auto 版本、行为说明和 fingerprint 同步）。返工保留单层 NumPy 路径，并通过标量 bounds 修复评分兼容。

## Review History

- 初审在 `0bde2c70062908fdfd31498ff01d128837d00ff0` 上判定 `rework_required`，原因是 orphan 提前过滤改变 nearest/best_score 的归一化并缺少最终 refinement 后的 00196/hash 与明确 SHA handoff。
- Executor 返工提交 `59470d032c4f07704105f3e2636bf9e20e280703`：在过滤前向量化保存旧 bounds，并增加四组 nearest/best_score 回归；复审提交 `568d642a767d36097473f3fe1ee50f46997eda59` 固化最终 00196 证据和完整实现 SHA。
- Luna Max 复审确认上述阻断解除，允许进入 `completed`。

## Rework Control

- `scope_changed`: `false`
- `required_fixes`:
  - `none` - 初审返工项均已关闭。
- `gates_to_rerun`:
  - `none` - 本复审所需定向测试、impact/schema、文档门禁和最终 00196 read-only 对照均已完成；后续仅保留非阻断发布 follow-up。

## Optional Notes

- `version_review`: `PASS` - candidate `0.1.3 -> 0.2.0`、pairs `0.2.0 -> 0.3.0` 与内部算法/用户可见过滤行为等级相符，code/manifest/Agent/Auto 页面一致。
- `contract_review`: `PASS` - candidate orphan 逐字段兼容，pairs 任一负 ID 过滤、all 模式安全，以及 nearest/best_score 完整 pair score/rank/selected 兼容均有测试和证据。
- `docs_review`: `PASS_WITH_ENV_NOTE` - Agent/Auto 生成结果、coverage、links、render、sync、anchors 通过；console script 缺失已明确记录并由等价 module invocation 替代。
- `performance_style_review`:
  - `single_parallel_layer`: `pass`
  - `numba_parallel_evidence`: `not_applicable`
  - `worker_option_review`: `pass` - 未新增 worker/线程/进程配置。
  - `fallback_review`: `pass` - 空数组、单侧输入和 score bounds 处理均为明确的 NumPy 路径。
- `completion_allowed`: `true`
