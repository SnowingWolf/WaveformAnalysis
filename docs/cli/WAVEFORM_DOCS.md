# waveform-docs 命令参考

**导航**: [CLI 工具](README.md) > waveform-docs

`waveform-docs` 是 WaveformAnalysis 的文档生成工具，用于自动生成 API 参考、配置参考和插件指南。

---

## 命令概述

`waveform-docs` 提供以下功能：
- 自动生成 API 参考文档
- 生成配置参考文档
- 生成插件开发指南
- 支持 Markdown 和 HTML 格式输出

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

---

## 文档类型

| 类型 | 说明 | 默认输出 |
|------|------|----------|
| `api` | API 参考文档 | `docs/api_reference.md` |
| `config` | 配置参考文档 | `docs/config_reference.md` |
| `plugins` | 插件开发指南 | `docs/plugin_guide.md` |
| `all` | 生成所有文档 | `docs/` 目录 |

---

## 选项

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--output` | `-o` | str | - | 输出路径（文件或目录） |
| `--format` | `-f` | str | "markdown" | 输出格式：`markdown` 或 `html` |
| `--with-context` | - | flag | False | 使用完整 Context 上下文（注册所有标准插件） |

---

## 使用示例

### 1. 生成 API 参考文档

```bash
# 使用默认路径和格式
waveform-docs generate api

# 指定输出路径
waveform-docs generate api --output docs/api/api_reference.md

# 生成 HTML 格式
waveform-docs generate api --format html --output docs/api/api_reference.html

# 使用完整上下文（包含所有插件信息）
waveform-docs generate api --with-context
```

### 2. 生成配置参考文档

```bash
# 基本生成
waveform-docs generate config

# 指定输出路径
waveform-docs generate config --output docs/api/config_reference.md
```

### 3. 生成插件指南

```bash
# 基本生成
waveform-docs generate plugins

# 指定输出路径
waveform-docs generate plugins --output docs/api/plugin_guide.md
```

### 4. 生成所有文档

```bash
# 生成所有文档到默认目录
waveform-docs generate all

# 生成所有文档到指定目录
waveform-docs generate all --output docs/generated/

# 使用完整上下文生成
waveform-docs generate all --with-context
```

---

## 输出格式

### Markdown 格式（默认）

生成标准的 Markdown 文档，适合在 GitHub、文档网站等平台显示。

```bash
waveform-docs generate api --format markdown --output docs/api.md
```

### HTML 格式

生成 HTML 文档，适合在浏览器中查看。

```bash
waveform-docs generate api --format html --output docs/api.html
```

---

## --with-context 选项

使用 `--with-context` 选项时，工具会：
1. 创建完整的 `Context` 实例
2. 注册所有标准插件
3. 生成包含所有插件信息的完整文档

这对于生成完整的 API 参考特别有用。

**示例**:
```bash
# 生成包含所有插件信息的完整 API 文档
waveform-docs generate api --with-context --output docs/api_reference.md
```

---

## 输出文件说明

### API 参考文档

包含：
- 所有类的完整文档字符串
- 方法签名和参数说明
- 使用示例
- 类型信息

### 配置参考文档

包含：
- 所有插件的配置选项
- 选项类型和默认值
- 配置说明和验证规则

### 插件指南

包含：
- 插件开发教程
- 插件架构说明
- 示例代码
- 最佳实践

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

2. **输出路径错误**
   ```
   ❌ 生成文档时出错: ...
   ```
   解决: 检查输出路径是否可写，确保目录存在

---

## 使用场景

### 场景 1: 更新 API 文档

在代码更新后，重新生成 API 文档：

```bash
waveform-docs generate api --with-context --output docs/api/api_reference.md
```

### 场景 2: 生成完整文档集

生成所有文档用于发布：

```bash
waveform-docs generate all --with-context --output docs/generated/
```

### 场景 3: 生成 HTML 文档

生成 HTML 格式用于在线查看：

```bash
waveform-docs generate api --format html --output docs/api_reference.html
```

---

## 注意事项

1. **文档准确性**: 生成的文档基于代码中的文档字符串，确保代码文档完整
2. **上下文选项**: 使用 `--with-context` 会加载所有插件，可能需要一些时间
3. **输出路径**: 如果输出路径是目录，确保目录存在
4. **格式选择**: Markdown 格式更适合版本控制和编辑，HTML 格式更适合在线查看

---

## 与手动文档的关系

自动生成的文档通常用于：
- API 参考（保持与代码同步）
- 配置参考（从代码自动提取）

手动编写的文档通常用于：
- 教程和指南
- 架构说明
- 最佳实践

两者结合使用，提供完整的文档体系。

---

**相关文档**: 
[CLI 工具总览](README.md) | 
[API 参考](../api/README.md) | 
[插件开发指南](../features/plugin/README.md)
