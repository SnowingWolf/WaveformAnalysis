# Doc Anchor 文档同步指南

**导航**: [文档中心](../../README.md) > [development](../README.md) > [contributing](README.md) > Doc Anchor 指南

本指南说明如何使用 `# DOC:` 注释标记代码与文档的关联关系，以及 CI 检查机制。

---

## 背景与目标

随着项目发展，代码和文档容易出现不同步的问题：
- 修改了代码逻辑，但忘记更新对应文档
- 文档引用的代码位置已变更
- 新功能缺少文档说明

**Doc Anchor 机制**通过在代码中添加 `# DOC:` 注释，建立代码与文档的显式关联，配合 CI 检查确保：
1. 文档引用始终有效
2. 代码变更时提醒更新文档

---

## 注释格式规范

### 基本格式

```python
# DOC: docs/<path>/<filename>.md
# DOC: docs/<path>/<filename>.md#<anchor>
```

### 示例

```python
# -*- coding: utf-8 -*-
# DOC: docs/features/plugin/SIMPLE_PLUGIN_GUIDE.md
# DOC: docs/development/plugin-development/PLUGIN_SPEC_GUIDE.md
"""
Plugins 模块 - 定义插件和配置选项的基类。
"""

class Plugin:
    # DOC: docs/development/plugin-development/PLUGIN_SPEC_GUIDE.md#插件属性
    provides: str = ""
    depends_on: List[str] = []
```

### 格式说明

| 组成部分 | 说明 | 示例 |
|---------|------|------|
| `# DOC:` | 固定前缀（大小写敏感） | `# DOC:` |
| `docs/...` | 相对于项目根目录的文档路径 | `docs/features/context/CONFIGURATION.md` |
| `#anchor` | 可选的锚点（Markdown 标题） | `#配置优先级` |

---

## 放置位置建议

### 文件级别

在文件头部（编码声明之后、docstring 之前）添加，标记整个模块的相关文档：

```python
# -*- coding: utf-8 -*-
# DOC: docs/features/context/DATA_ACCESS.md
# DOC: docs/features/context/CONFIGURATION.md
"""
Context 模块 - 插件系统的核心调度器。
"""
```

### 类/函数级别

在类或函数定义内部添加，标记特定功能的文档：

```python
class ConfigResolver:
    """配置解析器"""
    # DOC: docs/features/context/CONFIGURATION.md#配置优先级

    ADAPTER_INFERRED_OPTIONS = {
        # DOC: docs/features/context/CONFIGURATION.md#adapter-推断
        "sampling_rate_hz": lambda info: info.sampling_rate_hz,
    }
```

### 推荐标记的位置

| 代码位置 | 建议标记的文档 |
|---------|--------------|
| 插件基类 (`base.py`) | 插件开发指南、插件规范 |
| Context 类 | 数据访问、配置管理、插件管理 |
| 配置系统 | 配置指南 |
| 存储/缓存 | 数据访问、缓存管理 |
| 公开 API | 对应的用户指南 |

---

## CI 检查说明

### 检查命令

```bash
# 检查所有 DOC 注释的有效性
make check-docs

# 检查代码变更是否需要同步文档
make check-docs-sync
```

### 检查规则

| 检查项 | 结果 | 说明 |
|-------|------|------|
| 文档文件不存在 | **Fail** ❌ | 必须修复，CI 会失败 |
| 锚点不存在 | **Warn** ⚠️ | 建议修复，不阻塞 CI |
| 代码改了但文档没改 | **Warn** ⚠️ | 提醒检查，不阻塞 CI |

### 退出码

| 退出码 | 含义 |
|-------|------|
| 0 | 所有检查通过 |
| 1 | 存在错误（文档文件不存在） |
| 2 | 仅存在警告 |

### 示例输出

```
Doc Anchor 检查
==================================================

发现问题:

waveform_analysis/core/context.py:
  ❌ Line 3: 文档文件不存在: docs/nonexistent.md
     # DOC: docs/nonexistent.md

waveform_analysis/core/config/resolver.py:
  ⚠️ Line 5: 锚点不存在: docs/features/context/CONFIGURATION.md#不存在的锚点
     # DOC: docs/features/context/CONFIGURATION.md#不存在的锚点

==================================================
Doc Anchor 检查摘要
==================================================
  扫描到的 DOC 注释: 10
  ❌ 错误: 1
  ⚠️  警告: 1

提示: 错误必须修复，警告建议处理
```

---

## 常见问题

### Q: 锚点名称如何确定？

Markdown 标题会自动生成锚点，规则如下：
- 转换为小写
- 空格替换为 `-`
- 移除特殊字符（保留中文）

示例：
| 标题 | 锚点 |
|------|------|
| `## 配置优先级` | `#配置优先级` |
| `## Adapter 推断` | `#adapter-推断` |
| `## Quick Start` | `#quick-start` |

### Q: 一个文件可以有多个 DOC 注释吗？

可以。建议在文件头部列出所有相关文档，在具体代码位置添加更精确的锚点引用。

### Q: DOC 注释会影响代码执行吗？

不会。`# DOC:` 是普通的 Python 注释，不会被解释器执行。

### Q: 如何查看所有 DOC 注释？

```bash
python scripts/check_doc_anchors.py --verbose
```

### Q: 文档路径必须以 `docs/` 开头吗？

是的。所有文档路径都相对于项目根目录，应以 `docs/` 开头。

### Q: 文档需要标注内容来源吗？

建议对核心指南、用户指引和 API 说明添加**源码位置脚注**，用于提示文档内容的主要来源位置。
统一使用脚注形式，放在文档末尾：

```md
[^source]: 来源：`path/to/source.py`、`path/to/dir/`
```

建议至少包含：
- 主要逻辑所在源码文件
- 相关模块目录（如 `core/plugins/`、`core/config/`）
- 文档生成器（若是生成文档）

---

## 相关资源

- [导入规范](IMPORT_STYLE_GUIDE.md) - Python 导入规范
- [提交规范](COMMIT_CONVENTION.md) - Git 提交规范
- [插件开发](../plugin-development/README.md) - 插件开发指南

---

**快速链接**: [导入规范](IMPORT_STYLE_GUIDE.md) | [提交规范](COMMIT_CONVENTION.md)
