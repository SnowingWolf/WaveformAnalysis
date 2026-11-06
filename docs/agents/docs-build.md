# 文档维护与隔离构建

## 内容与产物的边界

文档沿着“正文与代码 → 站点模型 → Next 静态站点 → Python 包内站点”的流程生成。
修改时先找到内容真源，再同步对应产物。

| 内容 | 修改入口 | 下游产物 |
| --- | --- | --- |
| 用户指南、架构与开发说明 | `docs/` 中的 Markdown 正文 | 站点模型中的指南页 |
| 公开页面与分类导航 | `docs/site-guides.yaml` 的显式白名单；`source_indexes` 指向分类简介 | 页面路由、导航与搜索入口 |
| 插件参考 | 插件实现、spec 与文档模板 | `docs/plugins/reference/builtin/auto/`、`docs/plugins/reference/agent/` |
| Context、Accessor 等 API 参考 | Python 接口与 `waveform_analysis/documentation/site_docs/catalog.py` | 反射接口页 |
| 页面呈现与交互 | `docs/site-next/` | Next 静态导出 |
| 离线打包站点 | 通过隔离构建更新 | `waveform_analysis/documentation/site_dist/` |

生成参考和 `site_dist` 不作为手写正文维护。新正文是否公开由白名单决定，
不能仅靠放入 `docs/` 目录发布；内部任务记录与分析草稿不应批量加入公开目录。
现有页面改名或迁移时，还需检查 `docs/site-route-migration.yaml` 与旧链接的处理。

仓库硬规则、Agent 流程与用户文档分开维护：规则入口是 [AGENTS.md](../../AGENTS.md)，
流程真源见 [Agent 文档导航](INDEX.md)。当前流程文档不是弃用的兼容材料。

## 按变更选择验证

从仓库根目录执行命令，并使用已安装项目依赖的 Python 3.10+ 环境。
以下示例假设仓库有 `.venv/bin/python`；其他环境用其解释器绝对路径替换。
使用 `python -m` 可确保 CLI 与选定解释器一致。

| 变更 | 需要同步与验证 |
| --- | --- |
| 内部说明或链接 | 本地链接、Agent 文档同步与 doc anchors |
| 公开正文或分类简介 | 上述检查，加站点模型测试、受影响内容基线与 fixture、真实站点构建 |
| 公开页面清单或路由 | 模型与导航测试、旧路由处理、真实构建 |
| 插件/API/配置契约 | 从代码核对语义，重新生成对应参考；同时遵循源代码 route 的质量闸门 |
| Next 呈现或交互 | TypeScript、前端测试与真实构建；受影响页面需要浏览器验证 |
| 包内站点更新 | 真实构建通过后使用 `--stage-output`，审查打包差异 |

常用的独立检查命令：

```bash
.venv/bin/python -m waveform_analysis.documentation.cli check links --docs-dir docs
.venv/bin/python -m waveform_analysis.documentation.cli check coverage --strict --fail-on-warning
.venv/bin/python -m pytest -q tests/test_doc_links.py tests/test_site_guides.py tests/test_site_model.py
WAVEFORM_PYTHON="$PWD/.venv/bin/python" bash scripts/check_doc_sync.sh --base HEAD
```

`--base HEAD` 检查当前未提交差异；检查一组提交时改为实际比较基线。
`check_doc_sync.sh` 已包含生成的 Agent 文档与 doc anchors 检查。
插件参考生成命令与完整参数见 [文档 CLI](../cli/WAVEFORM_DOCS.md)。

`docs/site-content-baseline.json` 保存公开内容的回归基线，
`docs/site-next/fixture/site-model.v1.json` 保存前端使用的模型样本。
正文修改后只更新已审查的相关基线项，并从当前源码生成 fixture；
不能为消除失败而整体接受不明来源的内容差异。

文档 CI 分两层：先检查本地链接、插件覆盖与导航/模型契约，通过后才安装 Node 依赖、
生成插件参考并构建站点。它覆盖 `docs/`、Python 包、构建脚本与项目依赖配置的变更。
PR 的 Agent workflow 另行执行流程契约和 doc sync，职责保持分开。

链接通过只说明本地目标存在；覆盖率只说明插件文档满足检查项；模型与构建通过
不能证明所有示例都运行过，也不能证明内容与算法语义完全一致。交付时分别报告
结构检查、实际执行、页面验证及未验证项。CI 构建成功不代表已发布或已更新包内站点。

## 隔离构建与打包

`docs-build external workspace` 工作流从当前 worktree 的文档、Python 模型生成器和
Next 源码构建站点，将依赖与输出保存在外部目录，便于检查真实构建证据。
原有文档生成及发布命令继续可用。

```bash
PYTHONPATH="$PWD" .venv/bin/python scripts/docs_build.py build --workspace "$PWD" --run-id docs-maintenance-001
```

默认根目录为 `tempfile.gettempdir()/waveform-doc-build`，可用 `--build-root DIR`
指定工作树外目录。每次必须使用新的字母或数字开头的 run ID，其余字符允许字母、
数字、下划线和连字符，最多 80 个字符。已有 ID 会被拒绝，证据不会覆盖。
符号链接输出路径和工作树内构建根目录也会被拒绝。

每次运行在 `runs/ID/app` 复制当前 `docs/site-next` 源码，排除依赖、构建输出和
临时文件；执行 `npm ci --ignore-scripts`、类型检查和 Next 构建。依赖不跨运行共享，
仅 `npm-cache` 下载缓存共享。单次命令受剩余 30 分钟运行预算约束。

产物位于 `runs/ID/`：

- `site/`：通过静态导出验证的站点及 package manifest。
- `site-model.json`：可检查的当前模型。
- `build.log`：安装、检查、构建的合并日志。
- `report.json`：状态、源 HEAD、dirty 路径、输入字节指纹、命令退出状态和产物绝对路径。

指纹覆盖 docs、Python 包、scripts、pyproject.toml 与 AGENTS.md，排除旧 site_dist、
任务运行记录、任务导航、Git 元数据和构建临时文件。它包含未提交的源文件内容。

默认不修改工作树。需要更新当前工作树的 wheel 打包产物时，追加 `--stage-output`。
只有构建成功并验证后才会替换 `waveform_analysis/documentation/site_dist`；文本规范化
及 manifest 生成复用现有实现，替换失败会恢复原目录。此操作不执行 Git add 或提交。

失败返回非零，并在已分配的运行目录保留错误报告和日志。参数或重复 ID 在创建运行
目录前拒绝，不会写入旧报告。排查日志后以新 ID 重试，不要把单元测试当作真实构建证据。
