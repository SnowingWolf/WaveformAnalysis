# 🏗️ 架构设计索引

**导航**: [文档中心](../README.md) > 架构设计

理解 WaveformAnalysis 的系统架构、设计模式和实现细节。

---

## 📚 核心架构文档

### 1. 系统架构总览 ⭐
**文档**: [ARCHITECTURE.md](../ARCHITECTURE.md)

**内容**:
- 系统整体架构设计
- 核心组件和职责
- 数据流程和生命周期
- 设计模式和原则

**适合**:
- 理解系统全貌
- 开发新功能前的准备
- 贡献代码前的学习

**架构要点**:
```
WaveformAnalysis 架构
├── 核心层 (Core Layer)
│   ├── Context - 插件管理和配置
│   ├── Dataset - 数据处理入口
│   └── Plugin System - 插件框架
├── 处理层 (Processing Layer)
│   ├── Loader - 数据加载
│   ├── Processor - 数据处理
│   └── Analyzer - 数据分析
├── 存储层 (Storage Layer)
│   ├── Memmap - 零拷贝存储
│   ├── Cache - 缓存管理
│   └── Backends - 存储后端
└── 执行层 (Execution Layer)
    ├── Executor - 并行执行
    └── LoadBalancer - 负载均衡
```

**关键设计**:
- **插件化架构**: 灵活扩展，松耦合
- **血缘追踪**: 自动缓存失效
- **流式处理**: 内存高效
- **零拷贝存储**: 性能优化

---

### 2. 项目结构说明
**文档**: [PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md)

**内容**:
- 目录结构和组织
- 模块职责划分
- 文件命名规范
- 依赖关系图

**目录树**:
```
waveform_analysis/
├── core/                    # 核心功能
│   ├── context.py          # Context 管理器
│   ├── dataset.py          # Dataset API
│   ├── plugins/            # 插件系统
│   │   ├── core/          # 插件核心
│   │   └── builtin/       # 内置插件
│   ├── processing/         # 数据处理
│   │   ├── loader.py
│   │   ├── processor.py
│   │   └── analyzer.py
│   ├── storage/            # 存储层
│   │   ├── memmap.py
│   │   ├── cache.py
│   │   └── backends.py
│   ├── execution/          # 执行层
│   │   ├── manager.py
│   │   └── config.py
│   └── foundation/         # 基础工具
│       ├── utils.py
│       ├── mixins.py
│       └── progress.py
├── fitting/                # 拟合模型
├── utils/                  # 工具函数
│   ├── daq/               # DAQ 接口
│   ├── visualization/     # 可视化
│   └── io.py              # I/O 工具
└── cli.py                  # 命令行接口
```

**模块化原则**:
- 单一职责
- 高内聚低耦合
- 可测试性
- 可扩展性

---

### 3. Context 和 Processor 工作流程
**文档**: [CONTEXT_PROCESSOR_WORKFLOW.md](../CONTEXT_PROCESSOR_WORKFLOW.md)

**内容**:
- Context 生命周期
- Processor 执行流程
- 插件加载和执行
- 缓存机制详解

**工作流程**:
```
1. 初始化阶段
   Context.__init__()
   ├── 注册插件
   ├── 加载配置
   └── 初始化缓存

2. 数据请求
   Context.get_data(run_id, data_name)
   ├── 检查缓存
   ├── 构建依赖图（DAG）
   ├── 按拓扑顺序执行
   └── 缓存结果

3. 插件执行
   Plugin.compute(context, run_id, **deps)
   ├── 获取依赖数据
   ├── 执行处理逻辑
   └── 返回结果

4. 缓存管理
   CacheManager
   ├── 计算血缘哈希
   ├── 验证缓存有效性
   └── 保存/加载数据
```

**状态管理**:
- **无状态设计**: Context 不维护运行级状态
- **显式 run_id**: 所有操作需要指定 run_id
- **血缘追踪**: SHA1 哈希确保缓存一致性

---

### 4. 数据模块设计
**文档**: [data_module.md](../data_module.md)

**内容**:
- 数据模型定义
- 数据类型系统
- 数据转换流程
- 存储格式说明

**核心数据类型**:
- **原始数据**: List[List[str]] (文件路径)
- **波形数据**: List[np.ndarray] (多通道波形)
- **结构化数据**: np.ndarray (dtype with fields)
- **DataFrame**: pd.DataFrame (表格数据)

**数据流转**:
```
CSV 文件
  ↓ (RawFilesPlugin)
文件路径列表
  ↓ (WaveformsPlugin)
波形数组
  ↓ (StWaveformsPlugin)
结构化数组 (time, amplitude, ...)
  ↓ (BasicFeaturesPlugin)
特征数组 (charge, peak, ...)
  ↓ (DataFramePlugin)
Pandas DataFrame
```

---

## 🎯 设计模式

### 使用的设计模式

#### 1. 插件模式 (Plugin Pattern)
**位置**: `core/plugins/`

**优点**:
- 功能模块化
- 易于扩展
- 松耦合

**示例**:
```python
class MyPlugin(Plugin):
    provides = "my_data"
    depends_on = ["input_data"]

    def compute(self, context, run_id, input_data):
        return process(input_data)
```

#### 2. Mixin 模式 (Mixin Pattern)
**位置**: `core/foundation/mixins.py`

**优点**:
- 代码复用
- 组合优于继承
- 灵活的功能组合

**示例**:
```python
class WaveformDataset(CacheMixin, PluginMixin, StepMixin):
    # 继承多个 Mixin 的功能
    pass
```

#### 3. 策略模式 (Strategy Pattern)
**位置**: `core/storage/backends.py`

**优点**:
- 算法可替换
- 运行时切换策略
- 符合开闭原则

**示例**:
```python
# 不同的存储策略
storage = MemmapStorage(...)  # Memmap 策略
storage = SQLiteBackend(...)  # SQLite 策略
```

#### 4. 单例模式 (Singleton Pattern)
**位置**: `core/execution/manager.py`

**优点**:
- 全局资源管理
- 避免资源浪费
- 统一访问点

**示例**:
```python
executor_manager = ExecutorManager.get_instance()
```

#### 5. 工厂模式 (Factory Pattern)
**位置**: `core/storage/compression.py`

**优点**:
- 对象创建封装
- 依赖解耦
- 易于扩展

**示例**:
```python
compression_manager = get_compression_manager()
backend = compression_manager.get_backend('blosc2')
```

---

## 🔧 架构原则

### SOLID 原则

**S - 单一职责原则 (Single Responsibility)**
- 每个类/模块只负责一件事
- 示例: Loader 只负责加载，Processor 只负责处理

**O - 开闭原则 (Open/Closed)**
- 对扩展开放，对修改关闭
- 示例: 通过插件扩展功能，无需修改核心代码

**L - 里氏替换原则 (Liskov Substitution)**
- 子类可以替换父类
- 示例: 所有 Plugin 子类都可以互换使用

**I - 接口隔离原则 (Interface Segregation)**
- 不应强迫依赖不需要的接口
- 示例: Mixin 提供可选的功能组合

**D - 依赖倒置原则 (Dependency Inversion)**
- 依赖抽象，不依赖具体实现
- 示例: 依赖 StorageBackend 接口，而非具体实现

---

## 📊 性能考虑

### 零拷贝设计
**实现**: Memmap 存储

**优势**:
- 避免数据复制
- 减少内存占用
- 提升 I/O 性能

### 延迟计算
**实现**: 插件依赖图

**优势**:
- 按需计算
- 避免不必要的计算
- 支持流式处理

### 缓存策略
**实现**: 血缘追踪缓存

**优势**:
- 自动缓存失效
- 增量计算
- 避免重复计算

---

## 🔍 代码导航

### 阅读源码建议

#### 入口级
1. `cli.py` - 命令行入口
2. `core/dataset.py` - Dataset API
3. `core/plugins/builtin/standard.py` - 标准插件

#### 核心级
1. `core/context.py` - Context 实现
2. `core/plugins/core/base.py` - 插件基类
3. `core/processing/processor.py` - 数据处理器

#### 高级级
1. `core/storage/memmap.py` - 存储实现
2. `core/execution/manager.py` - 执行管理器
3. `core/foundation/` - 基础工具

---

## 🎓 架构学习路径

### 第一步：理解全貌（30 分钟）
```
ARCHITECTURE.md
  ↓
PROJECT_STRUCTURE.md
  ↓
运行示例代码
```

### 第二步：深入核心（1 小时）
```
CONTEXT_PROCESSOR_WORKFLOW.md
  ↓
阅读 context.py 源码
  ↓
阅读 dataset.py 源码
```

### 第三步：专题研究（2 小时）
```
选择感兴趣的模块：
├── 插件系统 → core/plugins/
├── 存储层 → core/storage/
├── 执行层 → core/execution/
└── 数据处理 → core/processing/
```

---

## 💡 常见问题

**Q: 为什么选择插件架构？**
A: 插件架构提供最大的灵活性和可扩展性，用户可以轻松添加自定义处理逻辑。

**Q: Context 和 Dataset 的区别是什么？**
A: Context 是底层插件管理器，Dataset 是高层链式 API。Dataset 内部使用 Context。

**Q: 血缘追踪如何工作？**
A: 通过 SHA1 哈希插件代码、版本、配置和依赖，生成唯一标识作为缓存键。

**Q: 为什么使用 Memmap？**
A: Memmap 实现零拷贝内存映射，大幅减少内存占用和 I/O 时间。

---

## 🔗 相关资源

### 实现细节
- [API 参考](api-reference.md) - 具体 API 实现
- [功能特性](features.md) - 功能实现说明

### 开发指南
- [开发指南](development.md) - 代码规范和最佳实践
- [插件开发](../plugin_guide.md) - 插件开发教程

### 社区资源
- GitHub 源码
- 设计文档（ADR）
- 贡献指南

---

**开始探索架构** → [ARCHITECTURE.md](../ARCHITECTURE.md) 🏗️
