# 命令行工具

**导航**: [文档中心](../README.md) > 命令行工具

WaveformAnalysis 提供三个命令行工具，用于数据处理、缓存管理和文档生成。

## 工具概览

| 命令 | 功能 | 文档 |
|------|------|------|
| `waveform-process` | 处理波形数据、扫描 DAQ 目录 | [详细文档](WAVEFORM_PROCESS.md) |
| `waveform-cache` | 管理缓存数据、诊断和清理 | [详细文档](WAVEFORM_CACHE.md) |
| `waveform-docs` | 自动生成 API 文档 | [详细文档](WAVEFORM_DOCS.md) |

## 快速参考

### waveform-process

```bash
# 处理单个数据集
waveform-process --run-name run_001 --output results.csv

# 扫描 DAQ 目录
waveform-process --scan-daq --daq-root DAQ

# 显示 DAQ 信息
waveform-process --show-daq run_001
```

### waveform-cache

```bash
# 查看缓存信息
waveform-cache info --storage-dir ./strax_data

# 清理缓存
waveform-cache clean --strategy lru --size-mb 500 --no-dry-run
```

### waveform-docs

```bash
# 生成 API 文档
waveform-docs generate api --output docs/api.md

# 生成所有文档
waveform-docs generate all
```

## 安装

CLI 工具通过 `pyproject.toml` 中的 `[project.scripts]` 配置自动安装：

```toml
[project.scripts]
waveform-process = "waveform_analysis.cli:main"
waveform-cache = "waveform_analysis.cli_cache:main"
waveform-docs = "waveform_analysis.utils.cli_docs:main"
```

安装包后命令自动可用：

```bash
pip install -e .
waveform-process --help
```

## 常见问题

**Q: 如何查看命令的帮助信息？**

使用 `--help` 选项，例如 `waveform-process --help`

**Q: 命令执行失败怎么办？**

使用 `--verbose` 选项查看详细错误信息

**Q: waveform-process 基于什么实现？**

基于 `Context` 和插件系统
