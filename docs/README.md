# 📚 WaveformAnalysis 文档中心

欢迎使用 WaveformAnalysis 文档！这是一个用于处理和分析 DAQ 系统波形数据的 Python 包。

---

## 🚀 快速开始（5 分钟）

**新用户？** 从这里开始：

- 🎯 [快速入门教程](quickstart/QUICKSTART.md) - 10 分钟上手
- ⚡ [速查表](quickstart/QUICK_REFERENCE.md) - 2 分钟速查
- 📖 [使用指南](quickstart/USAGE.md) - 15 分钟深入

**快速示例**:

```python
from waveform_analysis import WaveformDataset

# 创建数据集
ds = WaveformDataset(run_name="50V_OV_circulation_20thr", n_channels=2)

# 处理数据（链式调用）
(ds.load_raw_data()
   .extract_waveforms()
   .build_dataframe()
   .group_events())

# 获取结果
df = ds.get_dataframe()
```

---

## 📂 文档导航

### 🚀 [快速开始](quickstart/README.md)
> 10-30 分钟快速掌握核心功能

**包含**: 快速入门 | 速查表 | 使用指南

---

### 🏗️ [架构设计](architecture/README.md)
> 理解系统设计和数据流程

**包含**: 系统架构 | 项目结构 | 工作流程 | 数据模块

---

### ✨ [功能特性](features/README.md)
> 详细的功能说明和使用指南

**分类**:
- 📊 [数据处理](features/data-processing/README.md) - 流式处理 | 缓存 | CSV 处理
- ⚡ [性能优化](features/performance/README.md) - 内存优化 | 性能提升
- 🔧 [高级功能](features/advanced/README.md) - 执行器管理 | 依赖分析 | 进度追踪

---

### 📚 [API 参考](api/README.md)
> 完整的 API 文档和配置说明

**包含**: API 参考 | 配置参考 | 插件开发指南

---

### 🛠️ [开发指南](development/README.md)
> 贡献代码和开发插件的指南

**包含**: 开发规范 | 代码风格 | 插件开发

---

### 📝 [更新记录](updates/README.md)
> 版本更新和功能改进记录

**包含**: 新功能 | 更新总结 | 实现记录

---

## 🎯 按场景查找

| 我想... | 文档 | 时间 |
|---------|------|------|
| 快速上手 | [快速入门](quickstart/QUICKSTART.md) | 10 分钟 |
| 优化内存 | [内存优化](features/performance/MEMORY_OPTIMIZATION.md) | 15 分钟 |
| 提升性能 | [性能优化](features/performance/PERFORMANCE_OPTIMIZATION.md) | 10 分钟 |
| 开发插件 | [插件指南](api/plugin_guide.md) | 30 分钟 |
| 理解架构 | [系统架构](architecture/ARCHITECTURE.md) | 20 分钟 |
| 处理大数据 | [流式处理](features/data-processing/STREAMING_GUIDE.md) | 15 分钟 |

---

## 🎓 推荐学习路径

### 初学者（30 分钟）
```
快速入门 → 运行示例 → 速查表
```

### 进阶用户（2 小时）
```
系统架构 → 流式处理 → 内存优化 → 插件开发
```

### 插件开发者（3 小时）
```
插件指南 → 系统架构 → API 参考 → 开发规范
```

---

## 💡 常见问题

**Q: 从哪里开始？**
A: 新用户从 [快速入门](quickstart/QUICKSTART.md) 开始。

**Q: 如何节省内存？**
A: 查看 [内存优化指南](features/performance/MEMORY_OPTIMIZATION.md)。

**Q: 如何开发插件？**
A: 从 [插件开发指南](api/plugin_guide.md) 开始。

---

## 📞 获取帮助

- **问题反馈**: GitHub Issues
- **功能请求**: GitHub Discussions
- **文档改进**: 欢迎提交 Pull Request

---

**快速链接**: [快速入门](quickstart/QUICKSTART.md) | [API 参考](api/README.md) | [系统架构](architecture/ARCHITECTURE.md)
