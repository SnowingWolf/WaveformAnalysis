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

用户指南是公开文档的首个入口：从文档中心进入用户指南后，可在第二次点击到达[快速开始](user-guide/QUICKSTART_GUIDE.md)或[示例集合](user-guide/EXAMPLES_GUIDE.md)。站点导航与本页保持同一学习顺序。

## 术语约定

| 术语 | 规范含义 |
|---|---|
| `run_name` | DAQ/CLI 使用的数据集名称，通常对应 DAQ 根目录下的运行目录名。 |
| `run_id` | Context/API 访问数据时显式传入的运行标识；Context 不保存隐式的“当前 run”。 |
| `--run-name` | `waveform-process` 的正式 CLI 参数，用于指定 `run_name`。 |
| `--char` | `--run-name` 的 legacy 兼容别名，仅为旧脚本保留；新命令和文档统一使用 `--run-name`。 |

`run_name` 和 `run_id` 在常见目录布局中可能使用同一个字符串，但前者描述 DAQ/CLI 数据集名称，后者描述 API 调用边界。需要访问数据时始终显式传入 `run_id`，例如 `ctx.get_data(run_id, "records")`。

## 角色导航

按角色选择入口请看 [功能特性](features/README.md) 的“按角色选择入口”。

## 按问题直达

| 问题 | 文档 |
|---|---|
| 如何可视化依赖关系/血缘？ | [LINEAGE_VISUALIZATION_GUIDE.md](features/context/LINEAGE_VISUALIZATION_GUIDE.md) |
| 如何管理配置来源？ | [CONFIGURATION.md](features/context/CONFIGURATION.md) |
| 缓存为什么失效或命中异常？ | [PLUGIN_DAG_LINEAGE_CACHE.md](architecture/PLUGIN_DAG_LINEAGE_CACHE.md) |
| 插件缓存如何分层、如何生成键与失效？ | [PLUGIN_CACHE_ARCHITECTURE.md](architecture/PLUGIN_CACHE_ARCHITECTURE.md) |
| records 与 wave_pool 如何共同构建和访问？ | [DATA_PRODUCTS.md](architecture/DATA_PRODUCTS.md) |
| 如何使用信号处理插件？ | [SIGNAL_PROCESSING_PLUGINS.md](plugins/tutorials/SIGNAL_PROCESSING_PLUGINS.md) |
| 如何开发自定义插件？ | [PLUGIN_SYSTEM_OVERVIEW.md](plugins/PLUGIN_SYSTEM_OVERVIEW.md) |
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
