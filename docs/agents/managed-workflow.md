# Managed Workflow MVP

把一个 Task Spec 交给 Executor，在独立 Git worktree 中修改代码，运行验收命令，
再交给只读 Reviewer。审查通过后等待人工接受，接受后才集成到启动任务的分支。
第一版使用 CLI，一次运行一个任务，默认最多返工两次。

## 与现有协议的关系

任务定义继续使用 [AgentTask](protocol/README.md) 的 `task.yaml`，读取
`metadata.id`、`spec.goal`、`spec.scope.base_sha`、`spec.scope.allowed_paths`、
`spec.acceptance_criteria` 和 `spec.required_gates`。

`scripts/agent_workflow.py` 继续负责仓库任务契约和生命周期；
`scripts/managed_workflow.py` 负责执行尝试、worktree、命令日志和人工集成。
运行状态不等同于 canonical task 的 `completed`，MVP 不自动改写原始任务记录。
仓库任务的 execution/review/handoff 证据仍按现有协议登记。

## 运行流程

```text
Task Spec → managed worktree → Executor → tests + diff → Reviewer
                                  ↑                       │
                                  └──── 有限返工 ──────────┤
                                                         ↓
                                               awaiting_acceptance
                                                ├─ accept → 集成
                                                └─ reject → 保留现场
```

Executor 使用本机 `codex exec` 和 `workspace-write` sandbox；Reviewer 使用
独立调用及 `read-only` sandbox。继承当前 Codex 身份、模型和 provider 配置。
Runner 保存真实命令退出码、日志、diff、Executor 报告和 Reviewer JSON；
不把 Agent 的口头“测试通过”作为命令成功证据。

## 前置条件

- Python 3.10+、PyYAML、Git 和已配置好的 `codex` CLI。
- 当前仓库位于一个分支；Task Spec 的基线与当前 HEAD 一致。
  新 worktree 只包含该提交，不会复制目标工作区的未提交修改；接受时目标工作区必须干净。
- 验收命令所需依赖已安装；第一版不创建 Python 环境或下载科学数据。
- 为 Task Spec 中每个 required gate 显式提供验收命令。

运行数据保存在 Git common directory 下的专用 managed workflow 目录。
通过 `status` 返回的位置查看产物；它们不会被当作业务代码提交。

## CLI 用法

以下示例假设任务的 required gates 为 `doc_sync` 和 `doc_anchors`。
实际使用时，每个 gate 都要对应一个 `--test '名称=命令'`；命令在新 worktree
中执行，使用 shell 语法。Python 环境请换成当前任务实际使用的解释器。
任务 YAML 可以位于仓库外；若保存在仓库中，它的未提交修改不会被复制到新 worktree，
Runner 会将读取的 Spec 传给 Agent。接受前须处理目标工作区的未提交修改；若处理后
目标 HEAD 改变，需要用新基线重新运行。试跑时建议把输入 YAML 放在仓库外。

```bash
python scripts/managed_workflow.py --repo /path/to/repo run \
  --task /path/to/task.yaml \
  --test 'doc_sync=WAVEFORM_PYTHON=/path/to/python bash scripts/check_doc_sync.sh --base <base-sha>' \
  --test 'doc_anchors=/path/to/python scripts/check_doc_anchors.py --check-sync --base <base-sha>' \
  --max-reworks 2

python scripts/managed_workflow.py --repo /path/to/repo status <run-id>
python scripts/managed_workflow.py --repo /path/to/repo accept <run-id>
python scripts/managed_workflow.py --repo /path/to/repo reject <run-id>
```

`run` 启动时打印 `id` 和 `artifacts`；后续命令使用该 **run ID**。
示例中的 `<base-sha>` 必须替换为 Task Spec 的完整基线 SHA，不能用执行后的 HEAD
替代，否则 diff 类检查可能看不到 Runner 已提交的修改。
`--timeout` 为每次 Agent 调用或验收命令的超时秒数，默认 1800。
最多执行 `1 + max_reworks` 轮。Reviewer 即使返回通过，非零验收退出码仍会阻止接受。

每轮 `attempt-N/` 中保存 `diff.patch`、`executor.md`、`executor.log`、
`tests.json`、`test-N.log`、`review.json` 和 `reviewer.log`。
`status` 返回当前运行状态、worktree、分支、各轮证据位置和已审查的 SHA。

## 人工接受

审查通过只产生待接受结果。`accept` 检查代码仍然是被审查的版本、工作树干净、
目标仍然是原分支，再执行 fast-forward 集成。遇到目标分支变化或不能安全集成时
停止并报告，不自动解决冲突。`reject` 保留 worktree 和证据，不集成代码。

## 第一版边界

只支持本地单仓库、单任务、一个 Executor 和一个 Reviewer。
不提供 DevSpace UI、多任务调度、自动发布、自动环境管理或崩溃后断点续跑。
失败或达到返工上限时保留日志和 worktree，便于人工检查。
超时会终止该调用所在的进程组；验收命令应以前台方式运行并自行结束，
不要通过验收命令启动脱离该进程组的长期后台服务。
