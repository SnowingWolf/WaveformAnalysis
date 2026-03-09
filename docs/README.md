# WaveformAnalysis 文档中心

WaveformAnalysis 是一个用于处理和分析 DAQ 波形数据的 Python 包。

## 安装流程

首次使用建议按下面顺序执行：

```bash
# 1) 安装项目依赖
./install.sh

# 2) 以开发模式安装（包含开发依赖）
pip install -e ".[dev]"

# 3) 验证安装
waveform-process --help
```

## 文档入口总览

| 目标 | 入口 | 说明 |
|---|---|---|
| 快速完成首次流程 | [快速开始](user-guide/QUICKSTART_GUIDE.md) | 新用户建议从此处开始 |
| 参考常见场景示例 | [示例集合](user-guide/EXAMPLES_GUIDE.md) | 提供可复用代码模板 |
| 查阅核心能力（配置/缓存/执行链） | [功能特性](features/README.md) | Context、插件与高级能力说明 |
| 查看内置插件能力 | [插件详解](plugins/README.md) | 按插件类型组织 |
| 开发或修改插件 | [插件开发](development/plugin-development/README.md) | 插件开发规范与实践 |
| 查阅 API 与配置说明 | [API 参考](api/README.md) | 代码接口与参数定义 |
| 使用命令行工具 | [CLI 文档](cli/README.md) | `waveform-process` 等命令说明 |
| 维护 Agent 入口文档 | [AGENTS.md](../AGENTS.md) | 仓库入口规则真源 |

## 角色导航

按角色选择入口请看 [功能特性](features/README.md) 的“按角色选择入口”。

## 按问题直达

| 问题 | 文档 |
|---|---|
| 如何预览执行计划？ | [PREVIEW_EXECUTION.md](features/context/PREVIEW_EXECUTION.md) |
| 如何可视化依赖关系/血缘？ | [LINEAGE_VISUALIZATION_GUIDE.md](features/context/LINEAGE_VISUALIZATION_GUIDE.md) |
| 如何管理配置来源？ | [CONFIGURATION.md](features/context/CONFIGURATION.md) |
| 缓存为什么失效或命中异常？ | [DATA_ACCESS.md](features/context/DATA_ACCESS.md) |
| 如何使用信号处理插件？ | [SIGNAL_PROCESSING_PLUGINS.md](plugins/tutorials/SIGNAL_PROCESSING_PLUGINS.md) |
| 如何开发自定义插件？ | [SIMPLE_PLUGIN_GUIDE.md](plugins/tutorials/SIMPLE_PLUGIN_GUIDE.md) |
| 如何管理执行器与并行处理？ | [EXECUTOR_MANAGER_GUIDE.md](features/advanced/EXECUTOR_MANAGER_GUIDE.md) |

## 常用命令

```bash
# 安装
./install.sh
pip install -e ".[dev]"

# 测试
./scripts/run_tests.sh

# 常用 CLI
waveform-process --run-name <run_name> --verbose
waveform-process --scan-daq --daq-root DAQ
waveform-process --show-daq --daq-root DAQ
```

## 维护说明（面向文档维护者）

- Agent 入口规则以 [AGENTS.md](../AGENTS.md) 为唯一真源。
- `CLAUDE.md` 与 `docs/agents/*` 为兼容入口，新增入口规则优先更新 `AGENTS.md`。
- 用户可见的功能变更，请同步更新对应子目录文档（`features/`、`plugins/`、`api/`）。
