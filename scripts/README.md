# 脚本工具说明

## 导入管理工具

### `check_imports.py` - 导入规范检查

检查代码库中的导入是否符合规范：

```bash
python scripts/check_imports.py
```

检查内容：
- 禁止使用超过两级的相对导入（`...`）
- 禁止使用 Python 3.10+ 的联合类型语法（`str | Path`）
- 检查导入路径是否正确

### `fix_imports.py` - 自动修复导入

自动修复常见的导入路径问题：

```bash
# 检查并显示问题
python scripts/fix_imports.py

# 自动修复
python scripts/fix_imports.py --fix

# 只检查不修复
python scripts/fix_imports.py --check
```

修复内容：
- 相对导入 → 绝对导入
- Python 3.10+ 类型语法 → Python 3.8 兼容语法
- 自动添加缺失的 `Optional` 导入

## 使用 ruff 自动修复

```bash
# 安装 ruff
pip install ruff

# 自动修复所有导入问题
ruff check --fix waveform_analysis/

# 只检查导入
ruff check --select I waveform_analysis/
```

## 插件脚手架

### `scaffold_plugin.py` - 生成插件 + 单测 + 文档

```bash
python scripts/scaffold_plugin.py MyPlugin
```

常用参数：

```bash
python scripts/scaffold_plugin.py MyPlugin --provides my_plugin --depends-on st_waveforms
```

## 工作流程

1. **开发时**：运行 `check_imports.py` 检查导入规范
2. **重构时**：运行 `fix_imports.py --fix` 自动修复
3. **CI/CD**：集成 `check_imports.py` 和 `ruff check` 到 CI 流程

## 相关文档

- [导入风格指南](../docs/IMPORT_STYLE_GUIDE.md)
