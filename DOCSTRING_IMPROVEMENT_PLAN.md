# Docstring 完善计划

> 日期: 2026-01-11
> 当前覆盖率: 80.7% (580/719)
> 目标覆盖率: 95%+

---

## 📊 当前状态

### 覆盖率统计

| 类型 | 总数 | 已有文档 | 覆盖率 | 缺失 |
|------|------|----------|--------|------|
| 📦 模块 | 68 | 63 | 92.6% | 5 |
| 🏛️ 类 | 103 | 94 | 91.3% | 9 |
| ⚙️ 函数 | 139 | 113 | 81.3% | 26 |
| 🔧 方法 | 409 | 310 | 75.8% | 99 |
| **总计** | **719** | **580** | **80.7%** | **139** |

### 缺失最多的文件 (Top 10)

```
26 - waveform_analysis/core/storage/compression.py
12 - waveform_analysis/core/plugins/builtin/standard.py
 9 - waveform_analysis/core/processing/processor.py
 9 - waveform_analysis/core/foundation/utils.py
 8 - waveform_analysis/core/storage/backends.py
 8 - waveform_analysis/utils/daq/daq_analyzer.py
 7 - waveform_analysis/utils/daq/daq_run.py
 7 - waveform_analysis/core/foundation/mixins.py
 6 - waveform_analysis/fitting/models.py
 5 - waveform_analysis/core/foundation/model.py
```

---

## 🎯 完善计划（分阶段）

### Phase 1: 核心 API 文档 (优先级: 🔥 高)

**目标**: 完善用户最常用的核心 API

#### 1.1 标准插件 compute 方法 (12个)

所有标准插件的 `compute()` 方法必须有清晰的文档：

```python
# 需要完善的插件:
- RawFilesPlugin.compute()
- WaveformsPlugin.compute()
- StWaveformsPlugin.compute()
- HitFinderPlugin.compute()
- BasicFeaturesPlugin.compute()
- PeaksPlugin.compute()
- ChargesPlugin.compute()
- DataFramePlugin.compute()
- GroupedEventsPlugin.compute()
- PairedEventsPlugin.compute()
- FilterPlugin.compute()
- WaveformRecognitionPlugin.compute()
```

**模板**:
```python
def compute(self, run_id, **kwargs):
    """
    计算 [数据类型名称]

    从 [依赖数据] 中提取/计算 [输出数据]。
    [简要说明计算逻辑或特殊处理]

    Args:
        run_id: 运行标识符
        **kwargs: 依赖数据（通过 Context 自动注入）
            - dependency_name: 依赖数据说明

    Returns:
        [返回值类型]: [返回值说明]

    Examples:
        >>> # 通过 Context 调用（推荐）
        >>> ctx.get_data('run_001', 'data_name')

        >>> # 或直接调用插件
        >>> plugin = PluginClass()
        >>> result = plugin.compute('run_001', dependency=data)
    """
```

#### 1.2 核心类的 __init__ 方法 (15个)

重要类的初始化方法必须文档化：

```python
# 需要完善的类:
- ExecutorManager.__init__
- TimeoutManager.__init__
- HelpSystem.__init__
- CacheMixin.__init__
- PluginMixin.__init__
- StepMixin.__init__
- EventAnalyzer.__init__
- Chunk.__init__
- WaveformLoader.__init__
- WaveformProcessor.__init__
- ... (更多)
```

**模板**:
```python
def __init__(self, param1, param2, ...):
    """
    初始化 [类名]

    [简要说明这个类的用途]

    Args:
        param1: 参数1说明
        param2: 参数2说明

    Examples:
        >>> obj = ClassName(param1=value1)
        >>> # 使用对象
    """
```

---

### Phase 2: 模块和类级文档 (优先级: 🔸 中)

#### 2.1 缺失模块 docstring (5个)

```python
# 需要添加模块文档的文件:
- waveform_analysis/fitting/models.py
- waveform_analysis/utils/daq/daq_run.py
- waveform_analysis/utils/io.py
- waveform_analysis/utils/visualization/visulizer.py
- waveform_analysis/utils/visualization/waveform_visualizer.py
```

**模板**:
```python
"""
[模块名称] - [简要说明]

[详细说明模块功能和用途]

主要功能:
- 功能1: 说明
- 功能2: 说明

Examples:
    >>> from waveform_analysis.xxx import YYY
    >>> # 使用示例
"""
```

#### 2.2 缺失类 docstring (9个)

```python
# 需要添加类文档:
- EdgeModel
- LineageGraphModel
- NodeModel
- PortModel
- TempWrapper
- ResultData
- WaveformStruct
- LandauGaussFitter
- LandauGaussFitter2
```

**模板**:
```python
class MyClass:
    """
    [类名] - [简要说明]

    [详细说明类的用途和职责]

    Attributes:
        attr1: 属性1说明
        attr2: 属性2说明

    Examples:
        >>> obj = MyClass(...)
        >>> obj.method()
    """
```

---

### Phase 3: 工具函数和方法 (优先级: 🔹 低)

#### 3.1 公共工具函数 (约20个)

```python
# 需要完善的工具函数:
- get_plugin_title()
- get_plugins_from_context()
- flush_buffer()
- energy_rec()
- hist_count_ratio()
- lr_log_ratio()
- draw_wire()
- get_downstream_y_avg()
- browse() (两个)
- ... (更多)
```

#### 3.2 存储和压缩相关 (compression.py 26个)

这个文件缺失最多，需要系统化完善。

#### 3.3 装饰器和内部函数

大部分是装饰器内部的 `decorator()` 和 `wrapper()` 函数，优先级较低。

---

## 🔧 执行策略

### 批量完善原则

1. **按文件分组**: 同一文件的缺失一次性完善
2. **使用模板**: 确保风格一致
3. **包含示例**: 每个公共 API 至少一个示例
4. **类型提示**: 配合类型提示使用（如果已有）
5. **测试验证**: 完善后运行文档生成器验证

### Docstring 风格指南

**采用 Google Style**:
```python
def function_name(arg1: type, arg2: type) -> return_type:
    """
    简要说明（一行）

    详细说明（可选，多行）

    Args:
        arg1: 参数1说明
        arg2: 参数2说明

    Returns:
        返回值说明

    Raises:
        ExceptionType: 异常说明（如果有）

    Examples:
        >>> result = function_name(val1, val2)
        >>> print(result)
        expected_output

    Note:
        特殊注意事项（可选）
    """
```

---

## 📈 预期成果

完成后的目标覆盖率：

| 类型 | 目标覆盖率 | 预计缺失 |
|------|-----------|---------|
| 模块 | 100% | 0 |
| 类 | 100% | 0 |
| 函数 | 90%+ | < 14 |
| 方法 | 85%+ | < 61 |
| **总体** | **95%+** | **< 36** |

**改进幅度**: 从 80.7% → 95%+ (提升 14%+)

---

## ✅ 验证步骤

完成每个阶段后：

1. **运行分析脚本**:
   ```bash
   python /tmp/analyze_docstrings.py
   ```

2. **重新生成文档**:
   ```bash
   waveform-docs generate all --with-context --output docs/
   ```

3. **检查文档质量**:
   - 参数列表格式是否正确
   - 示例代码是否清晰
   - 类型信息是否准确

4. **测试代码示例**:
   ```bash
   # 提取并测试 docstring 中的示例
   python -m doctest waveform_analysis/path/to/module.py -v
   ```

---

## 🎯 开始执行

从 **Phase 1.1** 开始，优先完善核心插件的 `compute()` 方法。

**预计工作量**:
- Phase 1: ~2 小时（27个高优先级项）
- Phase 2: ~1.5 小时（14个中优先级项）
- Phase 3: ~3 小时（98个低优先级项）
- **总计**: 约 6-7 小时

**执行建议**: 分批完成，每批 10-15 个，及时验证。
