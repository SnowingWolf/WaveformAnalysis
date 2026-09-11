# 用户指南

**导航**: [文档中心](../README.md) > 用户指南

本指南帮助你快速上手 WaveformAnalysis，掌握常见使用场景。

## 你将掌握

- 用 Context 跑通完整的数据处理流程
- 常见场景的代码模板与参数配置
- 深入功能文档与插件细节的入口

## 文档列表

| 文档 | 说明 |
|------|------|
| [QUICKSTART_GUIDE.md](QUICKSTART_GUIDE.md) | 快速上手（含黄金路径），包含代码模板 |
| [EXAMPLES_GUIDE.md](EXAMPLES_GUIDE.md) | 常见场景示例集合 |
| [位置二维 Dashboard](../features/visualizations/POSITION_DASHBOARD_GUIDE.md) | 位置重建、S1/S2 分布与交互式二维检查 |
| [Run 6 Xe Fast 教学 Notebook](https://github.com/SnowingWolf/WaveformAnalysis/blob/0bc56668c0d2ebf81fc391287fb0097cd94b49f7/archive/notebooks/run6_xe_fast_0611_teaching.ipynb) | Run 6 Xe 数据扫描、Context 配置、records 读取与快速分析教学流程 |
| [Context 使用](../features/context/README.md) | 配置管理、数据获取、执行预览 |

## 学习路径

1. [快速上手](QUICKSTART_GUIDE.md) - 跑通第一个流程（含 5 分钟上手）
2. [常见示例](EXAMPLES_GUIDE.md) - 了解更多场景
3. [Context 功能](../features/context/README.md) - 深入 Context 使用

## 术语约定

| 术语 | 在本指南中的含义 |
|---|---|
| `run_name` | DAQ/CLI 数据集名称，通常就是 DAQ 根目录下的运行目录名。 |
| `run_id` | Context/API 访问数据时显式传入的运行标识。每次 `ctx.get_data()` 都应明确传入它。 |
| `--run-name` | `waveform-process` 的正式参数，对应要处理的 `run_name`。 |
| `--char` | `--run-name` 的旧兼容别名，仅用于迁移旧脚本；新用法统一写 `--run-name`。 |

在简单目录布局中 `run_name` 和 `run_id` 常常是同一个字符串，但它们属于不同边界：DAQ/CLI 识别数据集名称，Context/API 识别一次显式数据访问。

## 按场景查找

| 场景 | 文档 |
|------|------|
| 5 分钟上手 | [QUICKSTART_GUIDE.md#5-分钟上手](QUICKSTART_GUIDE.md#5-分钟上手) |
| 快速上手 | [QUICKSTART_GUIDE.md](QUICKSTART_GUIDE.md) |
| 查看代码示例 | [EXAMPLES_GUIDE.md](EXAMPLES_GUIDE.md) |
| 使用位置二维 Dashboard | [POSITION_DASHBOARD_GUIDE.md](../features/visualizations/POSITION_DASHBOARD_GUIDE.md) |
| 查看 DAQ 运行概览 | [DAQ_ANALYZER_GUIDE.md](../features/utils/DAQ_ANALYZER_GUIDE.md) |
| 管理配置 | [CONFIGURATION.md](../features/context/CONFIGURATION.md) |
| 可视化血缘 | [LINEAGE_VISUALIZATION_GUIDE.md](../features/context/LINEAGE_VISUALIZATION_GUIDE.md) |
| 查看内置插件细节 | [插件详解](../plugins/README.md) |

## 相关资源

- [功能特性](../features/README.md) - 详细功能说明
- [开发者指南](../development/README.md) - 插件开发和系统架构
