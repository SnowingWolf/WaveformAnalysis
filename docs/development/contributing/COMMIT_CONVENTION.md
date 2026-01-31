# 提交规范（Conventional Commits）

**导航**: [文档中心](../../README.md) > [development](../README.md) > 开发规范 > 提交规范

本项目使用 Conventional Commits 约定，保证提交可读、可追踪、可自动生成变更日志。

---

## 基本格式

```
<type>(<scope>): <subject>
```

- `type`: 变更类型，必填
- `scope`: 影响范围，可选但推荐
- `subject`: 简明描述，必填

示例：

```
feat(core): add cache prefetch for dependency order
fix(context): warn on plugin override registration
test(core): add context DAG/cache/timeout coverage
docs(contributing): add commit convention
```

---

## 类型（type）

推荐使用以下类型：

- `feat`: 新功能
- `fix`: 缺陷修复
- `perf`: 性能优化
- `refactor`: 重构（不改变行为）
- `docs`: 文档改动
- `test`: 测试改动
- `build`: 构建系统或依赖调整
- `ci`: CI 流水线配置改动
- `chore`: 杂项/维护性改动
- `revert`: 回滚提交

---

## 范围（scope）

常见范围示例（可按实际模块调整）：

- `core`
- `context`
- `execution`
- `processing`
- `storage`
- `plugins`
- `utils`
- `docs`
- `tests`
- `cli`
- `api`

---

## 主题（subject）

- 使用祈使动词（add/fix/update/rename/remove）
- 小写开头，避免句号结尾
- 控制在 72 字符内（超过建议拆为 body）

---

## 重大变更（breaking change）

使用以下任一方式标记重大变更：

```
feat(core)!: change default cache behavior
```

或在 footer 中明确说明：

```
BREAKING CHANGE: cache keys are now derived from lineage hash only
```

---

## 正文与脚注（body / footer）

当改动需要解释动机、影响或迁移步骤时，添加 body：

```
feat(storage): add checksum verification

Explain why checksums are required and how to enable them.
```

Issue 关联推荐使用 footer：

```
Refs: #123
Closes: #456
```

---

## 回滚提交（revert）

```
revert: fix(context): warn on plugin override registration

This reverts commit 1234abcd.
```

---

## 质量要求

- 不使用 `WIP`、`temp` 等非正式提交信息
- 一个提交聚焦一个主题；必要时拆分提交
- 涉及行为变更时优先补充测试
