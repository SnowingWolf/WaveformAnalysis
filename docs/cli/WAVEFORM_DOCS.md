# waveform-docs 命令参考

**导航**: [文档中心](../README.md) > [命令行工具](README.md) > waveform-docs 命令参考

`waveform-docs` 是 WaveformAnalysis 的文档生成工具，用于自动生成插件文档和检查文档覆盖率。

---

## 命令概述

`waveform-docs` 提供以下功能：
- 自动生成内置插件文档
- 检查文档覆盖率

---

## 基本用法

```bash
waveform-docs <命令> [选项]
```

---

## 子命令

### generate - 生成文档

生成指定类型的文档。

```bash
waveform-docs generate <文档类型> [选项]
```

### check - 检查文档

检查文档覆盖率。

```bash
waveform-docs check coverage [选项]
```

---

## 文档类型

| 类型 | 说明 | 默认输出 |
|------|------|----------|
| `plugins-auto` | 自动生成内置插件文档 | `docs/plugins/builtin/auto/` |

---

## 选项

### generate 选项

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--output` | `-o` | str | - | 输出路径（目录） |
| `--plugin` | `-p` | str | - | 生成单个插件文档 |

### check 选项

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--docs-dir` | `-d` | str | - | 文档目录路径 |
| `--strict` | - | flag | False | 严格模式（也检查 spec 质量） |
| `--fail-on-warning` | - | flag | False | 有警告时也失败 |

---

## 使用示例

### 1. 生成内置插件文档

```bash
# 生成所有内置插件文档
waveform-docs generate plugins-auto

# 指定输出目录
waveform-docs generate plugins-auto -o docs/plugins/builtin/auto/

# 生成单个插件文档
waveform-docs generate plugins-auto --plugin raw_files
```

### 2. 检查文档覆盖率

```bash
# 基本检查
waveform-docs check coverage

# 严格模式（检查 spec 质量）
waveform-docs check coverage --strict

# 有警告时失败
waveform-docs check coverage --fail-on-warning
```

---

## 输出文件说明

### 插件文档

每个插件生成一个 Markdown 文件，包含：
- 基本信息（类名、版本、provides、依赖）
- 描述
- 输出 schema（dtype 字段）
- 配置选项表
- 使用示例

生成的文件位于 `docs/plugins/builtin/auto/` 目录：
- `raw_files.md`
- `waveforms.md`
- `st_waveforms.md`
- `filtered_waveforms.md`
- `signal_peaks.md`
- `INDEX.md`（索引页）
- ...

---

## 依赖要求

文档生成需要以下依赖：

```bash
pip install jinja2
```

或者安装开发依赖：

```bash
pip install -e ".[docgen]"
```

---

## 错误处理

### 常见错误

1. **缺少依赖**
   ```
   ❌ 缺少依赖: No module named 'jinja2'
   提示: 运行 'pip install jinja2' 安装依赖
   ```
   解决: 安装 `jinja2` 包

2. **插件不存在**
   ```
   ❌ 错误: Plugin 'xxx' not found
   ```
   解决: 检查插件名称是否正确

---

## 使用场景

### 场景 1: 更新插件文档

在插件代码更新后，重新生成文档：

```bash
waveform-docs generate plugins-auto
```

### 场景 2: CI/CD 集成

在 CI 中检查文档覆盖率：

```bash
waveform-docs check coverage --strict --fail-on-warning
```

---

## 注意事项

1. **文档准确性**: 生成的文档基于插件的 `SPEC` 和 `options`，确保插件定义完整
2. **输出路径**: 默认输出到 `docs/plugins/builtin/auto/`，会覆盖已有文件
3. **INDEX.md**: 自动生成索引页，包含所有插件的概览表

---

**相关文档**:
[CLI 工具总览](README.md) |
[API 参考](../api/README.md) |
[插件开发指南](../plugins/README.md)
