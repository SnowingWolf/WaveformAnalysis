# plan_brief

- `task_id`: `plugin-doc-quality-20260826`
- `route`: `generate_docs`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `high`
- `scope_in`: 插件文档事实模型、动态依赖展示、Auto/Agent 模板、published AgentDoc provenance、严格内容质量门禁、36 个内置插件参考页及对应测试
- `scope_out`: 插件运行算法、Context/Accessor/CLI 的全面重写、`docs/_site` 提交、工作区既有 visualization 改动与未跟踪文件
- `required_gates`:
  - `waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/`
  - `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`
  - `waveform-docs check coverage --strict --fail-on-warning`
  - `waveform-docs check links --docs-dir docs`
  - `scripts/check_doc_sync.sh HEAD`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
  - `python scripts/assess_change_impact.py --base HEAD`
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- `executor_role`: `executor.docs`
- `agent_profile`: `none`
- `profile_plan`:
  - Luna-A：只读审计 36 个插件源码与现有页面，输出事实/内容缺口矩阵；当前环境没有可调用的 Luna 实例，由主 Agent 内联执行同一角色。
  - Max-A：只读审查生成器、模板、coverage checker 和测试边界，锁定兼容接口；当前环境没有可调用的 Max 实例，由主 Agent 内联执行同一角色。
  - Max-B：只修改生成器事实模型、动态依赖和模板，不修改插件算法。
  - Luna-B：只补充源码文档元数据和 published AgentDoc，不修改生成器。
  - Max-C：只实现质量门禁、CLI 输出和质量测试。
  - Luna-C/Max-D：只读内容复核与技术复核，主 Agent 负责最终放行。
- `blocking_assumptions`:
  - 当前工作区的 visualization 修改和 `artifacts/`、`plans/`、`graph-agent-workflow.zip` 无关，必须原样保留。
  - 默认文档画像继续使用 `wave_source=records`、`use_filtered=false`、`daq_adapter=vx2730`。
  - 文档元数据改动不改变插件行为，因此不升级插件版本。

## generate_docs Notes

- `doc_target_scope`: `waveform_analysis/utils/plugin_doc_generator.py`、插件文档模板、`waveform_analysis/utils/doc_coverage.py`、必要的插件 `agent_doc`、published AgentDoc、测试和生成的 Auto/Agent Markdown。
- `source_change_summary`: 从代码提取配置/输入/输出/依赖/运行契约，统一 Markdown 与 HTML 的默认动态依赖事实，并阻断空叙述、占位内容、事实漂移和 stale provenance。
- `generation_mode`: `mixed`
- `must_run_commands`:
  - `waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/`
  - `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`
  - `scripts/check_doc_sync.sh HEAD`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
- `docs_expected_to_change`:
  - `docs/plugins/reference/builtin/auto/**`
  - `docs/plugins/reference/agent/**`
  - `docs/cli/WAVEFORM_DOCS.md`
