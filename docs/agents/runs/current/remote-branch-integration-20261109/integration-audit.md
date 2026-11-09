# Develop 整合与 CI 修复核查

本轮获得明确授权：清理九个已并入 master 的分支并保存恢复记录，补齐独立改动的 PR，修复真实失败，验证和独立审查后整合至 develop。master 保持原提交，不执行正式发布。

## 分支与审阅范围

- 前置基础改动：PR #15；设备格式重组：#12；运行管理与文件读取重组：#14；Context/API 与文档后续改动：#16。
- 分层只读缓存：#13，采用远程 `29fb90f2`。本地缓存工作树另有未推送提交，本轮不包含。
- 历史发布差异：#17（v1.1）、#18（v1.2）及原 #7（v1.3），保留待审，不自动带入旧版本元数据。
- 最终采用一个整合候选保留原始提交身份，集中解决跨分支冲突和 CI 问题，避免在多个旧快照重复修复。同一候选通过检查和独立审查后才进入 develop。

## 已确认的失败与修复

| 失败 | 原因与最终处理 |
| --- | --- |
| 热重载测试缺少临时模块 pyc | docs_build 模块导入时设置全局 dont_write_bytecode；改为仅在构建期间设置并在 finally 恢复，增加两种初始值的导入回归和成功/失败构建恢复断言 |
| Python 3.10 插件合同的 11 个 fixture 错误 | 私有 typing 别名先进入 issubclass；先排除私有名称，再检查真实插件类 |
| raw_files 元数据断言 | 测试仍写0.0.2，实现为0.0.3；同步预期，不改插件行为 |
| 两个文档发布测试 | records fixture仍写0.14.2，当前模型契约为0.17.0；同步fixture，保留raw_files依赖要求 |
| 缓存分支构造签名快照 | Context新增base参数未进入公共签名快照；精确更新该项 |
| 缓存分支旧执行预览测试 | preview_execution已在现行API退役；改测真实get_data的冻结身份和禁止重算边界，不恢复旧入口 |
| 合并后的指南数量与静态资源 | 新增一篇LAYERED_CACHE指南后计数为36；合并内容基线及fixture，重新真实构建site_dist，消除旧chunk引用 |
| Agent Workflow首步失败 | 七份历史任务记录的schema与审查证据格式不符；忠实迁移并保留原文，缺少独立验收的记录继续reviewing，原失败仍为FAIL |
| 已批准退役仍触发影响分析退出1 | 三个DF类删除有原始批准与审查，但旧工具不识别；增加精确身份、原删除提交与批准任务核验，继续报告high风险并拦截未批准或不匹配的风险 |

PR12/13/14的Python 3.10、3.11、3.12共九份快速测试原日志均已检查。原始运行：

- https://github.com/SnowingWolf/WaveformAnalysis/actions/runs/41828049338
- https://github.com/SnowingWolf/WaveformAnalysis/actions/runs/41828395984
- https://github.com/SnowingWolf/WaveformAnalysis/actions/runs/41832819087

PR12仅一个Python3.10运行的速度测试为0.94x，低于0.95阈值；其余八份对应测试通过，数值断言也通过。本轮未降低阈值。当前整合快测包含此测试，远程矩阵再核验。

## 验证范围

本地快测覆盖完整发现目录：2393项通过、5项跳过，唯一指南数量断言修复后单项通过。慢测14项通过；唯一性能CLI测试因沙箱禁止创建临时Git worktree失败，外部环境原测试单项重跑通过。最终远程Python矩阵与全部闸门结果在PR和task.yaml中另行记录，不将这些分段本地证据描述成远端已通过。

格式工具采用项目固定的Black25.1.0与Ruff0.6.4，独立安装在/tmp，不修改共享Python环境。早期较新Black产生的八项格式差异已撤回。

七份任务迁移的原始全文内嵌在各自status.migration.original_record_yaml，并与原Git文件直接比较一致。三份有可信历史终审的记录保留completed，其余四份为reviewing；这不代表这些历史任务获得了新的完成批准。

隔离构建保留真实安装、类型检查、Next导出与打包证据。源码变更后的最终报告、精确风险批准测试和独立Reviewer决定以本任务status.execution/status.review为准。

## 恢复

九个删除分支的完整SHA映射见remote-branches-before.json，逐项恢复命令见remote-branches-restoration.md；本地另保留独立恢复refs。所有原提交仍可从master到达。
