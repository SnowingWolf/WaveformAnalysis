# plan_brief Template

## When To Create
- 在 `planning` 阶段结束前创建。
- 进入 `ready_for_execution` 前必须完成。

## Required Fields
- `task_id`
- `route`
- `workflow_cost`
- `lifecycle_profile`
- `risk_level`
- `scope_in`
- `scope_out`
- `required_gates`
- `executor_role`
- `blocking_assumptions`

## Field Rules
- `workflow_cost`
  仅允许：`light | standard | strict`
- `risk_level`
  仅允许：`low | medium | high`
- `light` 模式
  可省略 `scope_out`、`lifecycle_profile`、`blocking_assumptions` 中不适用的细节，但必须说明最小 `required_gates`
- `required_gates`
  使用平铺列表，不写嵌套结构
- `blocking_assumptions`
  只记录会阻止进入 `executing` 的前提，不写一般性备注

## Copy-ready Template
```md
# plan_brief

- `task_id`:
- `route`:
- `workflow_cost`: `light|standard|strict`
- `lifecycle_profile`:
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  -
- `executor_role`:
- `blocking_assumptions`:
  -

## Optional Notes
- `change_level`:
- `execution_backend_decision`:
  - `backend`: `python|numpy|numba_serial|numba_parallel|thread_pool|process_pool`
  - `backend_reason`: `CPU-bound|memory-bound|IO-bound|GIL-released|startup-cost-sensitive`
  - `parallel_scope`: `none|file|channel|chunk|record`
  - `worker_option`:
  - `fallback_path`:
  - `benchmark_required`: `true|false`
- `must_run_commands`:
  -
- `needs_user_input`:
  -
- `needs_approval`:
  -
```

## Completion Checklist
- `route` 与 route profile 一致
- `workflow_cost` 已明确，且不低于任务实际风险
- `required_gates` 已明确
- `executor_role` 已明确
- 没有缺失会阻止执行的前提
