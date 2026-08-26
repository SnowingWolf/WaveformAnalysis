# 项目结构

**导航**: [文档中心](../README.md) > [系统架构与数据模型](README.md) > 项目结构

本页说明 WaveformAnalysis 的代码、文档、示例和质量检查分别位于哪里。它只描述当前维护的公开入口；历史报告和实验性草稿仍保留在仓库归档中，但不属于发布站点。

## 顶层目录

```text
WaveformAnalysis/
├── waveform_analysis/       # Python 包：Context、插件、数据访问和工具
│   ├── core/                # Context、存储、插件系统和内置插件
│   ├── utils/               # CLI、Accessor、查询和可视化工具
│   └── visualization/       # 绘图与统计可视化实现
├── docs/                    # 用户、开发者和 Agent 文档
│   ├── user-guide/          # 快速开始和常见示例
│   ├── features/            # 功能专题
│   ├── plugins/             # 插件教程与参考
│   ├── architecture/        # 架构、数据产物和缓存说明
│   ├── cli/                 # 命令行参考
│   ├── development/         # 贡献与插件开发指南
│   └── agents/              # Agent 执行协议和内部维护入口
├── examples/                # 可直接运行的示例程序
├── tests/                   # 单元、集成和契约测试
├── scripts/                 # 开发、文档和质量门禁脚本
├── archive/                 # 历史报告与 notebook 归档
└── pyproject.toml           # 包元数据、依赖和命令入口
```

## 代码入口

使用者通常从 `waveform_analysis.core.context.Context` 开始，通过显式的 `run_id` 请求插件产物。插件实现位于 `waveform_analysis/core/plugins/`，按照 `provides` 和 `depends_on` 组成 DAG；数据访问和分析辅助接口位于 `waveform_analysis/utils/`。

推荐的阅读顺序是：

1. [快速开始](../user-guide/QUICKSTART_GUIDE.md) —— 跑通一个最小 Context 流程。
2. [系统架构与数据流](ARCHITECTURE.md) —— 了解数据从输入到分析产物的路径。
3. [数据产物与波形访问](DATA_PRODUCTS.md) —— 了解 records、wave_pool 和关联 ID。
4. [插件系统与模板 API](../plugins/PLUGIN_SYSTEM_OVERVIEW.md) —— 编写或扩展插件。

## 文档发布边界

离线文档总站由 [`docs/site-guides.yaml`](../site-guides.yaml) 驱动。生产清单采用显式 `pages` 白名单：

- `user-guide/`、`features/`、`architecture/`、`plugins/`、`cli/` 和 `development/` 中登记的页面属于公开学习路径。
- `docs/agents/` 保存 Agent 协议、执行计划和质量交接记录，供仓库维护使用，不自动发布到用户站点。
- `archive/` 中的历史 notebook 和报告不作为站点页面；需要分享时使用对应的稳定仓库链接。
- `docs/_site/` 是可重建的生成产物，不应手工编辑或提交。

修改公开页面后，请同步相应目录的 `README.md` 索引，并按 [文档同步规范](../development/contributing/DOC_ANCHOR_GUIDE.md) 执行锚点和链接检查。
