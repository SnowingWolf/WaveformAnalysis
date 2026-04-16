# Skills Adapter Notes

本页预留给基于 skills 的角色模板映射。

## 映射原则
- `planner` skill 消费 `plan_brief` 模板。
- `executor.*` skill 消费 route profile 和 `execution_report` 模板。
- `reviewer` skill 消费 gate 规则和 `review_report` 模板。

## 当前边界
- 本轮不新增具体 skill。
- 现有 `.agents/skills/create-pr/` 不纳入生命周期状态机。
