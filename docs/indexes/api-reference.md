# 📚 API 参考索引

**导航**: [文档中心](../README.md) > API 参考

完整的 API 文档、配置选项和插件开发指南。

---

## 📖 核心文档

### 1. API 完整参考 ⭐
**文档**: [api_reference.md](../api_reference.md) | [HTML 版本](../api_reference.html)

**内容**:
- 所有公共 API 的详细文档
- 类、方法、函数签名
- 参数说明和返回值
- 使用示例

**适合**:
- 查找特定 API 的详细说明
- 了解完整的 API 列表
- 开发插件或扩展

**组织结构**:
```
api_reference.md
├── 核心类 (Core Classes)
│   ├── WaveformDataset
│   ├── Context
│   └── Plugin
├── 数据处理 (Processing)
│   ├── WaveformLoader
│   ├── WaveformProcessor
│   └── EventAnalyzer
├── 工具函数 (Utilities)
│   ├── I/O 函数
│   ├── 可视化工具
│   └── DAQ 接口
└── 插件系统 (Plugin System)
    ├── 标准插件
    └── 插件基类
```

---

### 2. 配置参考 ⚙️
**文档**: [config_reference.md](../config_reference.md)

**内容**:
- 全局配置选项
- 插件特定配置
- 配置优先级说明
- 配置示例

**适合**:
- 自定义系统行为
- 优化性能参数
- 配置插件选项

**主要配置项**:
| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `n_channels` | int | 2 | 通道数量 |
| `threshold` | float | 10.0 | 检测阈值 |
| `cache_dir` | str | `.cache` | 缓存目录 |
| `enable_progress` | bool | True | 显示进度条 |

**示例**:
```python
# 全局配置
ctx.set_config({'n_channels': 2, 'threshold': 50})

# 插件特定配置（推荐，避免冲突）
ctx.set_config({'threshold': 50}, plugin_name='peaks')

# 查看当前配置
ctx.show_config('plugin_name')
```

---

### 3. 插件开发指南 🔌
**文档**: [plugin_guide.md](../plugin_guide.md)

**内容**:
- 插件架构说明
- 创建自定义插件
- 插件生命周期
- 最佳实践

**适合**:
- 开发自定义数据处理逻辑
- 扩展系统功能
- 贡献新插件

**插件开发快速开始**:
```python
from waveform_analysis.core.plugins.core.base import Plugin

class MyPlugin(Plugin):
    \"\"\"自定义插件示例\"\"\"

    provides = "my_data"
    depends_on = ["st_waveforms"]
    version = "1.0.0"

    def compute(self, context, run_id, st_waveforms, **kwargs):
        # 你的处理逻辑
        result = process_data(st_waveforms)
        return result

# 注册插件
ctx.register_plugin(MyPlugin())
```

---

## 🔍 快速查找

### 我想查找...

#### 特定类的 API
→ [api_reference.md](../api_reference.md) > 搜索类名

#### 配置选项
→ [config_reference.md](../config_reference.md) > 配置表

#### 如何开发插件
→ [plugin_guide.md](../plugin_guide.md) > 插件开发

#### 某个方法的用法
→ [api_reference.md](../api_reference.md) > 搜索方法名

---

## 📊 API 分类导航

### 核心类 (Core Classes)

**WaveformDataset**
- 主要的数据处理接口
- 链式 API 设计
- 内置缓存机制
- → [api_reference.md#WaveformDataset](../api_reference.md)

**Context**
- 插件管理器
- 配置管理
- 数据血缘追踪
- → [api_reference.md#Context](../api_reference.md)

**Plugin**
- 插件基类
- 依赖声明
- 版本管理
- → [plugin_guide.md](../plugin_guide.md)

### 数据处理 (Processing)

**WaveformLoader**
- 数据加载
- 多格式支持
- 流式加载
- → [api_reference.md#WaveformLoader](../api_reference.md)

**WaveformProcessor**
- 波形处理
- 特征提取
- 批量处理
- → [api_reference.md#WaveformProcessor](../api_reference.md)

**EventAnalyzer**
- 事件分析
- 统计计算
- 可视化支持
- → [api_reference.md#EventAnalyzer](../api_reference.md)

### 工具函数 (Utilities)

**I/O 函数**
- 文件读写
- 格式转换
- 批量导入导出
- → [api_reference.md#io-utilities](../api_reference.md)

**可视化工具**
- 波形绘图
- 血缘图可视化
- 交互式图表
- → [api_reference.md#visualization](../api_reference.md)

**DAQ 接口**
- DAQ 数据读取
- 元数据解析
- 多通道支持
- → [api_reference.md#daq-utilities](../api_reference.md)

---

## 🎯 使用场景

### 场景 1: 查找某个方法的签名
1. 打开 [api_reference.md](../api_reference.md)
2. 使用浏览器搜索（Ctrl+F）查找方法名
3. 查看参数列表和返回值类型
4. 查看示例代码

### 场景 2: 配置系统行为
1. 打开 [config_reference.md](../config_reference.md)
2. 找到相关配置项
3. 查看默认值和可选值
4. 使用 `ctx.set_config()` 设置

### 场景 3: 开发自定义插件
1. 阅读 [plugin_guide.md](../plugin_guide.md)
2. 了解插件架构和生命周期
3. 参考标准插件示例
4. 实现 `compute()` 方法
5. 注册和测试插件

---

## 📝 API 设计原则

### 一致性
- 统一的命名规范（snake_case）
- 一致的参数顺序
- 统一的返回值格式

### 可发现性
- 丰富的文档字符串
- 类型提示支持
- IDE 自动补全

### 向后兼容
- 语义化版本管理
- 弃用警告机制
- 迁移指南

---

## 🔗 相关资源

### 深入学习
- [架构设计](architecture.md) - 理解 API 设计背后的架构
- [开发指南](development.md) - 代码规范和最佳实践

### 实践应用
- [功能特性](features.md) - 了解高级功能的 API 使用
- [入门指南](getting-started.md) - 从基础开始学习 API

### 社区资源
- [GitHub Repository](https://github.com/your-repo) - 查看源代码
- [Issue Tracker](https://github.com/your-repo/issues) - 报告问题
- [Discussions](https://github.com/your-repo/discussions) - 讨论和问答

---

## 💡 常见问题

**Q: API 文档是自动生成的吗？**
A: 是的，使用 `waveform-docs generate` 命令可以从代码的文档字符串自动生成。

**Q: 如何查看某个类的所有方法？**
A: 在 api_reference.md 中搜索类名，或使用 Python 的 `dir(ClassName)` 查看。

**Q: 配置项太多记不住怎么办？**
A: 使用 `ctx.list_plugin_configs()` 查看所有可用配置项，或直接查 config_reference.md。

**Q: 插件开发有模板吗？**
A: 有的，查看 plugin_guide.md 中的模板和示例。

---

## ✅ API 使用检查清单

使用 API 前确保你：

- [ ] 了解基本的类和方法命名规范
- [ ] 知道如何查找 API 文档
- [ ] 理解参数类型和返回值
- [ ] 查看过相关示例代码
- [ ] 了解配置选项的作用
- [ ] 知道如何处理错误和异常

---

**开始探索 API** → [api_reference.md](../api_reference.md) 📚
