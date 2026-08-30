# execution_report

- `task_id`: `peaklet_pipeline_optimization`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `executor_role`: `executor.plugin`
- `agent_profile`: `graph_engineer`
- `changed_paths`:
  - `waveform_analysis/core/plugins/builtin/hit_threshold/plugin.py`
  - `waveform_analysis/core/plugins/builtin/hit_threshold/manifest.yaml`
  - `waveform_analysis/core/plugins/builtin/hit_threshold/tests/test_hit_threshold.py`
  - `waveform_analysis/core/plugins/builtin/peaklet_channels/plugin.py`
  - `waveform_analysis/core/plugins/builtin/peaklet_channels/manifest.yaml`
  - `waveform_analysis/core/plugins/builtin/shared/record_utils.py`
  - `tests/test_record_utils.py`
  - `docs/plugins/reference/agent/hit_threshold.md`
  - `docs/plugins/reference/builtin/auto/hit_threshold.md`
  - `docs/plugins/reference/agent/peaklet_channels.md`
  - `docs/plugins/reference/builtin/auto/peaklet_channels.md`
  - `docs/agents/protocol/artifacts/peaklet_pipeline_optimization_plan_brief.md`
  - `docs/agents/protocol/artifacts/peaklet_pipeline_optimization_execution_report.md`
  - `docs/agents/protocol/artifacts/peaklet_pipeline_optimization_review_report.md`
- `actions_taken`:
  - 将 `hit_threshold` 版本从 `1.2.0` 升至 `1.2.1`；自动 ragged chunk worker 限制为 `min(cpu_count, 64, n_chunks)`，显式正数 `n_workers` 保持原语义。
  - 用有序滑动 future 窗口和 amortized output buffer 收集 ragged chunk，避免保留全量 `parts` 后再次 `concatenate`。
  - 将 `RecordLookup` 的 identity 检查改为每次 1,000,000 行的分块比较，避免为完整 records 缓存建立等长 `arange`。
  - 将 `peaklet_channels` 版本从 `2.0.3` 升至 `2.0.4`；CSR fast path 保留 board/channel 原生 i1/i2，fraction/area 校验只保留 mismatch flags，异常文本需要时才归约失败组。
  - dense identity peaklet features 直接使用 native float32 area view；结构异常、冲突和 canonical materialize 继续走原有严格 fallback/oracle。
  - 未新增公开配置、未改变 provides/depends_on/字段 dtype/输出顺序/全局 Numba 线程设置，未写入正式缓存。
- `commands_run`:
  - `python -m pytest -q --no-cov waveform_analysis/core/plugins/builtin/peaklet_channels/tests/test_peaklet_channels.py waveform_analysis/core/plugins/builtin/hit_threshold/tests/test_hit_threshold.py waveform_analysis/core/plugins/builtin/hit_threshold/tests/test_hit_threshold_ordering.py tests/test_record_utils.py tests/test_peak_channel_accessor.py`（65 passed）。
  - 随机 dense fast path 与 feature 重排 generic oracle 对照（200 cases，逐字段 `array_equal`，PASS）。
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/assess_change_impact.py --base HEAD`（PASS）。
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/schema_compat_check.py --base HEAD --run-smoke`（PASS，dtype changes=0，smoke chain 正常）。
  - pyroot `compileall`、Ruff、Black check、`git diff --check`（PASS）。
  - 四个插件页面的 agent/auto `waveform-docs generate`（均生成成功）；随后保留仓库现有依赖说明和 downstream 语义，仅同步版本字段。
  - `python scripts/render_agent_docs.py --check`（PASS）；`check_doc_anchors.py --check-sync --base HEAD`（errors=0，仅无关 `context.py` 文档 warning）。
  - `python scripts/performance_regression_check.py --base HEAD`（PASS，no performance regression detected；临时 DAQ 解析有既有 pickle warning，baseline worktree fallback 因 sandbox 只读不可用）。
  - 定向完整只读链路（直接 mmap `/mnt/data/TPC/run6_Xe/00196`，不写缓存）：`hit_threshold`、`peaklet_channels`、`peak_classification`、`s1_s2_pair_candidates`、`s1_s2_pairs`、`position_reconstruction`。
- `tests_run`:
  - `hit_threshold` 全量 00196：23.1199 s，64,587,847 rows，SHA-256 `9f0f02fc7f3f60ffb74dd72c88044cd426d89af726d2e6da1b44b017fcf48701`，与既有缓存文件逐字节一致，peak RSS 17.731 GiB。
  - 下游全链路：`peaklet_channels` 27.8497 s、17,762,453 rows、SHA-256 `fea1d5107bd2cb98b1292c1fb4d312197096dfe12354b7e541805d0e960b8b38`；`peak_classification` 0.1672 s，`s1_s2_pair_candidates` 0.7296 s，后两级各约 0.0001 s，最终 peak RSS 22.822 GiB。
  - 1M component warm-JIT fast path 当前 median 0.057193 s（16 threads，976,835 rows）；输出 dtype 与字段保持契约。
  - 真实 records 切片：2M records/40 chunks bounded collector 在 auto/32/64 workers 的 median 约 0.4312/0.4041/0.3959 s；worker 上限没有改变显式 override。
- `gates_executed`:
  - `assess_change_impact`: PASS
  - `schema_compat_check --run-smoke`: PASS
  - `docs_generation`: PASS（四个目标页面）
  - `render_agent_docs --check`: PASS
  - `doc_anchors`: PASS（0 errors，1 unrelated warning）
  - `compileall/ruff/black`: PASS
  - `performance_regression_check`: PASS
  - `doc_sync`: PASS in strict revalidation；早期系统 Python 过旧记录为历史环境问题。
- `open_risks`:
  - 旧 2.0.2 的完整 00196 global matching/lexsort 基线在当前环境单次执行即被系统终止，无法取得计划要求的 3 次 baseline median/RSS；因此未宣称完整 wall-clock/RSS 改善比例。
  - 当前完整新链路是只读 memmap 单次诊断；首次触页和输入映射会显著放大 `peaklet_channels` 冷路径耗时（约 27.85 s），与 warm prepared benchmark（约 7.7 s）不是同一口径。
  - 自动 worker 上限 64 已由 2M/40-chunk 真实切片验证；全量 00196 的 1,011 个 chunk 未做三次重复 worker 矩阵。
  - 工作区仍有既有 site-doc-generator 等无关 dirty 改动，本任务不纳入也不清理。

## Strict revalidation (2026-08-19)

- 旧版 2.0.2 与当前优化版使用同一只读 00196 direct records/wave_pool 输入各运行 3 次；旧版中位数 `133.08960648602806 s`，优化版中位数 `9.016401179833338 s`，输出 hash 均为 `fea1d5107bd2cb98b1292c1fb4d312197096dfe12354b7e541805d0e960b8b38`，优化版约快 `93.23%`。
- 预触页峰值增量从旧版 `3.6244850158691406 GiB` 降至 `3.4094505310058594 GiB`；完整原始峰值 RSS 中位数从约 `25.3449 GiB` 降至 `25.1285 GiB`。
- 当前 Python 3.10+ 环境下 doc sync、anchors、impact、schema smoke、compileall、wheel 安装态生成及完整 `release_artifact_sync --perf-repeats 10` 均 PASS。
- `requested_review_focus`:
  - 检查 bounded collector 是否保持 chunk/record 顺序、空 chunk 行为和 `THRESHOLD_HIT_DTYPE`。
  - 检查 native board/channel dtype 与 dense float32 view 是否只作用于安全 fast path，异常/重排/冲突是否仍严格 fallback。
  - 区分全量冷 memmap 触页成本和算法 warm-JIT 成本，确认未把不等口径 benchmark 当成回归结论。

## Optional Notes

- `version_changed`: `true`（`hit_threshold 1.2.0 -> 1.2.1`，`peaklet_channels 2.0.3 -> 2.0.4`）。
- `contract_changed`: `false`。
- `backend_implemented_as_planned`: `true`。
- `not_executed_and_why`: 完整旧版 2.0.2 三次基线受 global matching/lexsort 内存峰值阻断；`check_doc_sync.sh` 受系统 Python 版本阻断；未写正式缓存以避免诊断污染产品 lineage。
