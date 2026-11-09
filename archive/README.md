# 归档资料

这里保存历史资料与根目录整理时移入的产物。历史页面中的命令、路径和设计描述反映当时状态，当前使用方式以根目录 README 和 `docs/` 为准。

| 目录 | 内容 |
| --- | --- |
| [notebooks/](notebooks/) | 历史 Notebook |
| [reports/](reports/) | 历史报告与基准结果 |
| [previews/](previews/) | 独立 HTML 设计预览与说明页 |
| `local/` | 本机保留的依赖、构建产物、测试输出和临时文件；不纳入 Git |

本次归档的根目录文件：

- [文档系统统一设计预览](previews/docs_unification_preview.html)
- [插件目录重构预览](previews/plugin_restructure_preview.html)
- [S1-S2 配对逻辑说明](previews/s1_s2_pairing_visualization.html)
- [历史基准结果](reports/benchmark_report.json)

本机整理批次保存在 `local/workspace-cleanup-20261030-01/`。该目录的 `manifest.json` 记录每项产物的原路径、归档路径与移动前后元数据；恢复时先检查原路径没有新文件，再将对应产物移回。整理采用同一文件系统内的重命名，不清空归档，也不删除文件。
