# 命令行工具

WaveformAnalysis 提供三个命令行工具，用于数据处理、缓存管理和文档生成。

## 工具概览

| 命令 | 功能 | 文档 |
|------|------|------|
| `waveform-process` | 处理波形数据、扫描 DAQ 目录 | [详细文档](WAVEFORM_PROCESS.md) |
| `waveform-cache` | 管理缓存数据、诊断和清理 | [详细文档](WAVEFORM_CACHE.md) |
| `waveform-docs` | 生成插件参考、构建文档网站与检查文档 | [详细文档](WAVEFORM_DOCS.md) |

## 安装

安装包后可通过各命令的帮助查看当前支持的参数：

```bash
pip install -e .
waveform-process --help
waveform-cache --help
waveform-docs --help
```
