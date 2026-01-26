**导航**: [文档中心](../README.md) > [更新记录](README.md) > 文档格式改进

---

# 文档格式改进对比

> 2026-01-11 - 文档生成器格式优化

---

## 改进前后对比

### ❌ 改进前（原始格式）

```markdown
#### `clear_cache_for(...)`

清理指定运行和步骤的缓存。

参数:
    run_id: 运行 ID
    data_name: 数据名称（步骤名称），如果为 None 则清理所有步骤
    clear_memory: 是否清理内存缓存
    clear_disk: 是否清理磁盘缓存
    verbose: 是否显示详细的清理信息

返回:
    清理的缓存项数量

示例:
    >>> ctx = Context()
    >>> ctx.clear_cache_for("run_001", "st_waveforms")
```

**问题：**
- ❌ 参数部分没有格式化为 Markdown 列表
- ❌ 参数名没有代码样式
- ❌ 缩进混乱，不符合 Markdown 规范
- ❌ 章节标题（参数:、返回:、示例:）格式不统一

---

### ✅ 改进后（Markdown 格式）

```markdown
#### `clear_cache_for(self, run_id: str, data_name: Optional[str] = None, clear_memory: bool = True, clear_disk: bool = True, verbose: bool = True) -> int`

清理指定运行和步骤的缓存。

**参数:**
- `run_id`: 运行 ID
- `data_name`: 数据名称（步骤名称），如果为 None 则清理所有步骤
- `clear_memory`: 是否清理内存缓存
- `clear_disk`: 是否清理磁盘缓存
- `verbose`: 是否显示详细的清理信息

**返回:**

清理的缓存项数量

**示例:**

\`\`\`python
>>> ctx = Context()
>>> ctx.clear_cache_for("run_001", "st_waveforms")
\`\`\`
```

**改进：**
- ✅ 参数格式化为 Markdown 无序列表（`-` 开头）
- ✅ 参数名使用代码样式（`` `param_name` ``）
- ✅ 章节标题加粗统一（**参数:**、**返回:**、**示例:**）
- ✅ 示例代码独立的代码块
- ✅ 完整的方法签名（包含类型提示）

---

## 技术实现

### 新增功能

1. **Docstring 解析器** (`extractors.py:format_docstring_to_markdown`)
   - 识别 Google/NumPy 风格的 docstring 章节
   - 支持中英文章节标题（Args/参数, Returns/返回, etc.）
   - 智能格式化参数列表

2. **元数据提取增强** (`MetadataExtractor.extract_class_api`)
   - 自动应用格式化到所有方法文档
   - 保留原始文档和格式化文档两个版本
   - 提取完整方法签名（包括类型提示）

### 支持的 Docstring 章节

**英文:**
- Args, Arguments, Parameters
- Returns, Return
- Yields, Yield
- Raises, Raise
- Examples, Example
- Note, Notes
- Warning, Warnings
- See Also, References

**中文:**
- 参数:, 参数：
- 返回:, 返回：
- 抛出:, 抛出：, 异常:, 异常：
- 示例:, 示例：
- 注意:, 注意：
- 警告:, 警告：

---

## 使用效果

### API 参考文档

生成的 `api_reference.md` 现在包含：

- ✅ 清晰的章节结构
- ✅ 规范的 Markdown 列表
- ✅ 代码样式的参数名
- ✅ 独立的代码块示例
- ✅ 一致的格式风格

### 配置参考文档

`config_reference.md` 保持原有清晰格式：

```markdown
#### `daq_adapter`

- **类型**: `<class 'str'>`
- **默认值**: `vx2730`
- **说明**: DAQ adapter name

**使用示例**:

\`\`\`python
ctx.set_config({'daq_adapter': <value>}, plugin_name='raw_files')
\`\`\`
```

### 插件开发指南

`plugin_guide.md` 包含格式化后的 Plugin 基类文档。

---

## 测试

重新生成所有文档：

```bash
waveform-docs generate all --with-context --output docs/
```

验证格式：

```bash
# 检查参数列表格式
grep -A 10 "**参数:**" docs/api_reference.md

# 检查返回值格式
grep -A 5 "**返回:**" docs/api_reference.md

# 检查示例代码块
grep -A 5 "**示例:**" docs/api_reference.md
```

---

## 已知限制

1. **嵌套描述**: 如果参数描述包含多级缩进（如 Storage Modes 示例），可能会被合并到上一个参数
   - **解决方案**: 在 docstring 中使用明确的章节分隔

2. **复杂格式**: 包含表格、代码块的 docstring 可能需要手动调整
   - **解决方案**: 使用简洁的 docstring 风格

3. **类型提示**: 复杂类型（Union, Optional, Dict[str, Any]）在签名中可能过长
   - **当前状态**: 保持完整签名，确保准确性

---

## 总结

✅ **格式规范化** - 符合标准 Markdown 语法
✅ **可读性提升** - 清晰的列表和代码样式
✅ **一致性改进** - 中英文 docstring 统一处理
✅ **自动化** - 无需手动维护文档格式

**下次使用:**

```bash
# 重新生成文档（已包含格式优化）
waveform-docs generate all --with-context --output docs/
```

所有未来生成的文档都将自动应用这些格式改进！🎉
