# 🚀 入门指南索引

**导航**: [文档中心](../README.md) > 入门指南

快速开始使用 WaveformAnalysis，从零到上手只需 10-30 分钟。

---

## 📚 推荐学习顺序

### 1️⃣ 第一步：快速入门（10 分钟）⭐
**文档**: [QUICKSTART.md](../QUICKSTART.md)

**你将学到**:
- 基本安装和配置
- 第一个完整示例
- 核心概念和术语
- 常用工作流程

**适合人群**: 所有新用户

```python
# 你的第一行代码
from waveform_analysis import WaveformDataset

ds = WaveformDataset(run_name="my_run", n_channels=2)
ds.load_raw_data().extract_waveforms()
```

---

### 2️⃣ 第二步：快速参考（2 分钟）📋
**文档**: [QUICK_REFERENCE.md](../QUICK_REFERENCE.md)

**你将学到**:
- 常用参数速查表
- 核心 API 快速查找
- 常见操作代码片段

**适合人群**: 需要快速查找的用户

**使用场景**:
- ✅ "这个参数叫什么来着？"
- ✅ "我忘了这个方法怎么用"
- ✅ "有没有快速的代码示例？"

---

### 3️⃣ 第三步：详细使用指南（15 分钟）📖
**文档**: [USAGE.md](../USAGE.md)

**你将学到**:
- 完整的功能演示
- 最佳实践和技巧
- 常见问题解答
- 高级用法示例

**适合人群**: 想要深入了解的用户

---

## 🎯 按需求查找

### 我想快速上手
→ 直接看 [QUICKSTART.md](../QUICKSTART.md)（10 分钟）

### 我需要查找某个 API
→ 使用 [QUICK_REFERENCE.md](../QUICK_REFERENCE.md)（2 分钟）

### 我想了解最佳实践
→ 阅读 [USAGE.md](../USAGE.md)（15 分钟）

### 我遇到了问题
→ 查看 [USAGE.md](../USAGE.md) 的常见问题章节

---

## ⏱️ 时间规划

### 快速浏览（15 分钟）
```
QUICKSTART.md (10 分钟)
    ↓
QUICK_REFERENCE.md (2 分钟)
    ↓
运行第一个示例 (3 分钟)
```

### 完整学习（30 分钟）
```
QUICKSTART.md (10 分钟)
    ↓
USAGE.md (15 分钟)
    ↓
QUICK_REFERENCE.md (2 分钟)
    ↓
实践练习 (3 分钟)
```

---

## 💡 学习建议

### 初次使用
1. ✅ 先看 QUICKSTART.md 了解全貌
2. ✅ 跟着示例代码亲自运行一遍
3. ✅ 遇到问题时查 QUICK_REFERENCE.md
4. ✅ 想深入了解时读 USAGE.md

### 已有经验
1. ✅ 直接使用 QUICK_REFERENCE.md 作为速查表
2. ✅ 遇到新功能时查阅 USAGE.md 对应章节
3. ✅ 需要深入理解时查看 [架构设计](architecture.md)

---

## 📖 文档详情

### QUICKSTART.md
- **时间**: 10 分钟
- **难度**: ⭐ 入门
- **内容**:
  - 安装配置
  - 基本概念
  - 第一个示例
  - 核心工作流
- **示例代码**: ✅ 包含
- **最后更新**: 2024-01

### QUICK_REFERENCE.md
- **时间**: 2 分钟
- **难度**: ⭐ 入门
- **内容**:
  - 参数速查表
  - API 快速查找
  - 代码片段
- **示例代码**: ✅ 包含
- **最后更新**: 2024-01

### USAGE.md
- **时间**: 15 分钟
- **难度**: ⭐⭐ 进阶
- **内容**:
  - 详细功能说明
  - 最佳实践
  - 常见问题
  - 高级技巧
- **示例代码**: ✅ 包含
- **最后更新**: 2024-01

---

## 🔗 相关资源

### 下一步学习
- [API 参考](api-reference.md) - 查看完整 API 文档
- [功能特性](features.md) - 了解高级功能
- [架构设计](architecture.md) - 理解系统设计

### 常见问题
- **Q: 我应该从哪里开始？**
  A: 从 QUICKSTART.md 开始，10 分钟快速上手。

- **Q: 文档太长读不完怎么办？**
  A: 使用 QUICK_REFERENCE.md 作为速查表，需要时再查详细文档。

- **Q: 遇到错误怎么办？**
  A: 先查看 USAGE.md 的常见问题章节，未解决则查看 GitHub Issues。

---

## ✅ 检查清单

完成入门学习后，你应该能够：

- [ ] 安装和配置 WaveformAnalysis
- [ ] 创建 WaveformDataset 对象
- [ ] 加载和处理原始数据
- [ ] 提取波形特征
- [ ] 导出结果数据
- [ ] 查找常用 API 参数
- [ ] 理解基本概念和术语

---

**准备好了吗？** 开始你的第一步 → [QUICKSTART.md](../QUICKSTART.md) 🚀
