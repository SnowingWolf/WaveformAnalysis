# 开发者指南

**导航**: [文档中心](../README.md) > 开发者指南

本指南面向 WaveformAnalysis 的开发者，介绍系统架构、插件开发和代码规范。

## 适合谁

- 想理解系统架构与核心模块
- 需要开发或维护插件
- 参与贡献与扩展

## 文档分类

### [架构设计](../architecture/README.md)

- [系统架构](../architecture/ARCHITECTURE.md) - 整体架构设计
- [Context 工作流](../architecture/CONTEXT_PROCESSOR_WORKFLOW.md) - 数据流和执行流程
- [项目结构](../architecture/PROJECT_STRUCTURE.md) - 目录和模块组织

### [插件开发](plugin-development/README.md)

- [插件开发教程](../features/plugin/SIMPLE_PLUGIN_GUIDE.md) - 入门
- [插件开发完整指南](plugin-development/plugin_guide.md) - 深入学习

### [API 参考](../api/README.md)

- [API 参考](../api/api_reference.md) - Context API
- [配置参考](../api/config_reference.md) - 所有配置选项

### [开发规范](contributing/README.md)

- [导入风格指南](contributing/IMPORT_STYLE_GUIDE.md) - Python 导入规范
- [提交规范](contributing/COMMIT_CONVENTION.md) - Conventional Commits

## 学习路径

### 插件开发入门

1. [插件开发教程](../features/plugin/SIMPLE_PLUGIN_GUIDE.md)
2. [插件开发完整指南](plugin-development/plugin_guide.md)

### 架构深入

1. [系统架构](../architecture/ARCHITECTURE.md)
2. [Context 工作流](../architecture/CONTEXT_PROCESSOR_WORKFLOW.md)
3. [项目结构](../architecture/PROJECT_STRUCTURE.md)

### 贡献代码

1. [导入风格指南](contributing/IMPORT_STYLE_GUIDE.md)
2. [提交规范](contributing/COMMIT_CONVENTION.md)
3. [API 参考](../api/api_reference.md)

## 文档维护

更新面包屑导航：

```bash
python3 scripts/update_breadcrumbs.py        # 实际更新
python3 scripts/update_breadcrumbs.py --dry-run  # 预览模式
```

## 相关资源

- [用户指南](../user-guide/README.md) - Context 和 Plugin 使用
- [更新记录](../updates/README.md) - 版本历史
