# Agent Conventions

## 代码与接口约定
- Python 3.10+ 基线
- 命名规范：PascalCase / snake_case / UPPER_SNAKE_CASE
- `run_id` 必填
- `run_name` 优先，`char` 视为 legacy

## 插件约定
- 单一职责
- 变更即升级版本（行为/配置语义/output）
- 尽量保持 dtype 字段名稳定

## 提交约定
- 提交前缀：`feat/fix/refactor/docs/chore`
- 用户可见变更需要同步文档
