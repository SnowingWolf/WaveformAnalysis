# plan_brief

- `task_id`: `site_doc_generator_review_fixes`
- `route`: `generate_docs`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `doc_generator_reviewed`
- `risk_level`: `high`
- `scope_in`:
  - 将插件集合图片纳入 wheel package data，并验证安装态站点生成。
  - 为独立 `plugins-web` 恢复固定侧栏导航 fallback。
  - 通过将 `hist_density` 追加到参数末尾，保持 `corner_hist` 既有位置参数顺序。
  - 仅渲染 schema v2 frontmatter 后的 Markdown 正文。
  - 将被扫描器跳过的目录 README 链接解析到栏目索引。
  - 发布手写适配器指南，同时排除自动生成的 reference 页面。
  - 恢复 `contexts/index.html` 作为 Context 兼容入口，并避免覆盖已有综合索引。
  - 保持生成站点离线，避免生成外部编辑链接。
- `scope_out`:
  - 工作区中既有的站点文档重构、迁移和删除。
  - 与本次审查项无关的插件算法或性能实现。
  - 完整 `00196` 性能基线及旧版对照。
- `required_gates`:
  - 定向站点、插件文档和 `corner_hist` 回归测试。
  - HTTP 站点发布测试。
  - 非隔离 wheel 构建、安装态插件文档和站点生成。
  - `waveform-docs` 的 plugins-auto/plugins-agent 生成。
  - `assess_change_impact.py --base HEAD`。
  - `schema_compat_check.py --base HEAD --run-smoke`。
  - 文档同步、锚点、Ruff、Black、compileall 和 diff 检查。
  - 性能回归和发布 artifact 检查（结果必须记录，既有链路问题不得隐瞒）。
- `executor_role`: `executor.docs`
- `agent_profile`: `none`
- `profile_plan`: `Not applicable; no specialist profile selected.`
- `blocking_assumptions`:
  - 当前工作区的大量 dirty 站点重构属于用户已有改动，本轮只在其上修复审查项并保持不重置。
  - 隔离构建需要下载依赖且网络不可用，因此使用已安装依赖的 `--no-isolation` 作为安装态验证。

## Optional Notes

- `change_level`: `compatibility_and_release_fix`
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest -q tests/test_site_guides.py tests/test_plugin_documentation.py tests/test_corner_hist_performance.py`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m build --wheel --no-isolation`
  - `python scripts/assess_change_impact.py --base HEAD`
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
  - `scripts/check_doc_sync.sh`
