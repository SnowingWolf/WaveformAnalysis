# 更新日志

所有重要的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 修复
- **CSV 表头处理**: 修复了 CSV 文件读取时的表头处理问题
  - 现在只有每个通道的第一个文件会跳过表头行（`skiprows`）
  - 后续文件不再跳过任何行（`skiprows=0`），因为它们不包含表头
  - 影响函数：`parse_and_stack_files` 和 `parse_files_generator`
  - 相关文档：`docs/CSV_HEADER_HANDLING.md`
  - 测试：`tests/test_csv_header_handling.py`

### 计划功能
- 并行处理支持
- 更多内置拟合模型
- 交互式可视化工具
- Web 界面
- 性能优化

## [0.1.0] - 2024-12-24

### 新增
- 🎉 首次发布
- 完整的包结构重组
- 标准化的 Python 包
- 模块化架构设计
- 链式 API 调用支持
- 特征注册系统
- 自定义配对策略支持
- 时间戳索引缓存优化
- 命令行工具 `waveform-process`
- 完整的文档体系
- 示例脚本和教程
- 测试框架
- CI/CD 配置（预留）

### 核心功能
- **数据加载**: 
  - 高效的多通道数据加载
  - 文件自动识别和排序
  - 错误处理和空文件跳过
  
- **数据处理**:
  - 波形结构化
  - 基线校正
  - 峰值和电荷计算
  - 事件时间戳提取
  
- **事件配对**:
  - 基于时间窗口的多通道配对
  - 可配置的时间窗口
  - 自定义配对策略支持
  
- **特征提取**:
  - 内置峰值和电荷计算
  - 可扩展的特征注册系统
  - 自动特征计算和缓存
  
- **数据导出**:
  - CSV 格式支持
  - Parquet 格式支持
  - 灵活的保存选项

### 拟合模块
- Landau-Gauss 卷积拟合
- JAX 加速计算
- 基于 iminuit 的优化

### 文档
- README.md - 项目主文档
- QUICKSTART.md - 快速开始指南
- USAGE.md - 详细使用文档
- PROJECT_STRUCTURE.md - 项目结构说明
- CONTRIBUTING.md - 贡献指南
- 原模块文档保留

### 工具
- 快速安装脚本 `install.sh`
- 安装验证脚本 `verify_install.py`
- 命令行接口

### 测试
- 基础功能测试
- 数据加载测试
- pytest 配置

### 配置
- pyproject.toml - 现代配置
- setup.py - 向后兼容
- requirements.txt - 依赖管理
- .gitignore - Git 配置

## [0.0.1] - 2024-12-XX (内部版本)

### 初始实现
- 基础数据加载功能
- 简单的数据处理
- Jupyter 笔记本示例
- 独立的 Python 脚本

---

## 版本说明

### 语义化版本格式

- **主版本号 (MAJOR)**: 不兼容的 API 修改
- **次版本号 (MINOR)**: 向下兼容的功能性新增
- **修订号 (PATCH)**: 向下兼容的问题修正

### 变更类型

- `新增` - 新功能
- `变更` - 已有功能的变更
- `弃用` - 即将移除的功能
- `移除` - 已移除的功能
- `修复` - 问题修复
- `安全` - 安全相关的修复

---

[未发布]: https://github.com/yourusername/waveform-analysis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/waveform-analysis/releases/tag/v0.1.0
