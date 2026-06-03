# API 参考

**导航**: [文档中心](../README.md) > API 参考

完整的 API 文档、使用示例和配置说明。

---

## 核心 API 文档

### 快速查找

| 文档 | 说明 |
|------|------|
| [API 快速参考](QUICK_REFERENCE.md) | 核心 API 速查表，包含常用类、方法和数据类型 |
| [API 使用示例](EXAMPLES.md) | 完整代码示例，涵盖常见使用场景 |

### 核心组件

| 组件 | 文档 | 说明 |
|------|------|------|
| **Context** | [配置管理](../features/context/CONFIGURATION.md) | 数据处理主入口，插件编排和存储管理 |
| **Plugin** | [插件开发指南](../plugins/guides/PLUGIN_AUTHORING_GUIDE.md) | 插件基类，定义数据处理逻辑 |
| **Storage** | [数据访问](../features/context/DATA_ACCESS.md) | 存储后端和缓存管理 |
| **Executor** | [执行器管理](../features/advanced/EXECUTOR_MANAGER_GUIDE.md) | 并行处理和任务调度 |

### 插件 API

| 文档 | 说明 |
|------|------|
| [内置插件索引](../plugins/reference/builtin/auto/INDEX.md) | 自动生成的内置插件 API 文档 |
| [Agent 插件索引](../plugins/reference/agent/INDEX.md) | 自动生成的 Agent 插件 API 文档 |
| [适配器系统](../plugins/reference/ADAPTER_SYSTEM_GUIDE.md) | 适配器架构和插件行为 |

---

## 学习路径

### 新手入门

1. **快速开始**: [快速开始指南](../user-guide/QUICKSTART_GUIDE.md) - 5 分钟上手
2. **API 速查**: [API 快速参考](QUICK_REFERENCE.md) - 核心 API 一览
3. **代码示例**: [API 使用示例](EXAMPLES.md) - 完整示例代码

### API 查找

1. **速查表**: [API 快速参考](QUICK_REFERENCE.md) - 快速查找常用 API
2. **代码补全**: 使用 IDE 查看 docstring（推荐）
3. **插件文档**: [内置插件索引](../plugins/reference/builtin/auto/INDEX.md) - 查看插件 API

### 插件开发

1. **入门教程**: [简单插件指南](../plugins/tutorials/SIMPLE_PLUGIN_GUIDE.md) - 写第一个插件
2. **开发指南**: [插件开发指南](../plugins/guides/PLUGIN_AUTHORING_GUIDE.md) - 深入学习
3. **高级特性**: [流式插件](../plugins/guides/STREAMING_PLUGINS_GUIDE.md) - 处理大数据集
4. **配置系统**: [配置管理](../features/context/CONFIGURATION.md) - 了解配置选项

### 高级用法

1. **并行处理**: [执行器管理](../features/advanced/EXECUTOR_MANAGER_GUIDE.md)
2. **流式处理**: [流式插件指南](../plugins/guides/STREAMING_PLUGINS_GUIDE.md)
3. **自定义存储**: [数据访问](../features/context/DATA_ACCESS.md)
4. **性能优化**: [批处理器](../features/context/BATCH_PROCESSOR.md)

---

## 核心概念

### Context

Context 是数据处理的主入口，负责：
- 插件注册和管理
- 数据存储和缓存
- 配置管理
- 依赖解析

**示例**:
```python
from waveform_analysis import Context

ctx = Context(storage_dir='./strax_data')
data = ctx.get_array(run_id='run_001', targets='records')
```

### Plugin

Plugin 定义数据处理逻辑，包括：
- 依赖声明 (`depends_on`)
- 输出定义 (`provides`, `dtype`)
- 计算逻辑 (`compute`)
- 配置选项 (`Option`)

**示例**:
```python
from waveform_analysis import Plugin, Option

class MyPlugin(Plugin):
    depends_on = ('records',)
    provides = 'my_data'
    dtype = [('time', np.int64), ('value', np.float32)]

    my_option = Option(default=10, help='示例选项')

    def compute(self, records):
        # 处理逻辑
        return result
```

### 数据类型

常用数据类型：
- **records**: 原始波形记录
- **hits**: 检测到的信号脉冲
- **basic_features**: 基础波形特征
- **s1_s2**: S1/S2 事件分类

详见 [内置插件索引](../plugins/reference/builtin/auto/INDEX.md)

---

## 常见任务

### 数据获取

```python
# 获取 NumPy 数组
records = ctx.get_array(run_id='run_001', targets='records')

# 获取 DataFrame
df = ctx.get_df(run_id='run_001', targets='basic_features')

# 时间范围查询
data = ctx.get_array(
    run_id='run_001',
    targets='records',
    time_range=(0, 100)  # 前 100 秒
)
```

### 插件注册

```python
# 注册自定义插件
ctx.register(MyPlugin)

# 使用插件
data = ctx.get_array(run_id='run_001', targets='my_data')
```

### 配置管理

```python
# 设置全局配置
ctx.set_config({
    'sample_rate': 1000,
    'threshold': 50
})

# 插件特定配置
ctx.set_config({
    'MyPlugin.my_option': 20
})
```

更多示例见 [API 使用示例](EXAMPLES.md)

---

## 相关资源

### 文档导航

- [文档中心](../README.md) - 所有文档入口
- [AGENTS.md](../../AGENTS.md) - 主入口与硬约束
- [Agent 文档索引](../agents/INDEX.md) - Agent 专题导航

### 功能文档

- [功能特性](../features/README.md) - 功能说明
- [插件系统](../plugins/README.md) - 插件体系
- [架构设计](../architecture/README.md) - 系统架构

### 开发文档

- [开发指南](../development/README.md) - 开发规范
- [贡献指南](../development/contributing/README.md) - 如何贡献
- [测试指南](../development/CONTRACT_TESTS.md) - 契约测试

### 版本管理

- [变更日志](../CHANGELOG.md) - 版本历史
- [迁移指南](../MIGRATION_GUIDE.md) - 版本升级
