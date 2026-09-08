# 隔离文档构建

`docs-build external workspace` 工作流从当前 worktree 的文档、Python 模型生成器和
Next 源码构建站点，将依赖与输出保存在外部目录，便于检查真实构建证据。
原有文档生成及发布命令继续可用。

```bash
PYTHONPATH="$PWD" /home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/docs_build.py build --workspace "$PWD" --run-id docs-default
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
