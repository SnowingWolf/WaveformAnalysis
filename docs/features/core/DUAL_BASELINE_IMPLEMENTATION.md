# 双 Baseline 字段实施总结

## 实施日期
2026-01-28

## 概述
成功在 WaveformStruct 中实现了双 Baseline 字段支持，允许同时保存：
1. **baseline**: WaveformStruct 自己计算的 baseline（从 CSV 的 baseline_start:baseline_end 列）
2. **baseline_upstream**: 上游插件提供的 baseline（可选）

## 修改的文件

### 1. 核心数据结构
**文件**: `waveform_analysis/core/processing/dtypes.py` (新建)

**修改内容**:
- 将 ST_WAVEFORM_DTYPE、create_record_dtype、DEFAULT_WAVE_LENGTH 等定义从 waveform_struct.py 移到独立的 dtypes.py
- 在 ST_WAVEFORM_DTYPE 中添加 `baseline_upstream` 字段（float64）
- 在 create_record_dtype() 中添加 `baseline_upstream` 字段
- 在 RECORDS_DTYPE 中添加 `baseline_upstream` 字段

**新的 ST_WAVEFORM_DTYPE 结构**:
```python
ST_WAVEFORM_DTYPE = [
    ("baseline", "f8"),           # WaveformStruct 计算的 baseline
    ("baseline_upstream", "f8"),  # 上游插件提供的 baseline (新增)
    ("timestamp", "i8"),
    ("event_length", "i8"),
    ("channel", "i2"),
    ("wave", "f4", (800,)),
]
```

### 2. WaveformStruct 类
**文件**: `waveform_analysis/core/processing/waveform_struct.py`

**修改内容**:
- 从 dtypes.py 导入 ST_WAVEFORM_DTYPE 等定义
- `__init__()`: 添加 `upstream_baselines` 参数
- `from_adapter()`: 添加 `upstream_baselines` 参数
- `_structure_waveform()`:
  - 添加 `channel_idx` 参数
  - 添加 baseline_upstream 字段赋值逻辑
  - 如果提供了 upstream_baselines 且长度匹配，使用上游值
  - 否则填充 NaN
- `structure_waveforms()`: 传递 channel_idx 参数给 _structure_waveform()

**关键逻辑**:
```python
# 赋值 baseline_upstream 字段
if self.upstream_baselines is not None and channel_idx < len(self.upstream_baselines):
    upstream_bl = self.upstream_baselines[channel_idx]
    if upstream_bl is not None and len(upstream_bl) == len(waves):
        waveform_structured["baseline_upstream"] = upstream_bl
    else:
        waveform_structured["baseline_upstream"] = np.nan
else:
    waveform_structured["baseline_upstream"] = np.nan
```

### 3. StWaveformsPlugin
**文件**: `waveform_analysis/core/plugins/builtin/cpu/st_waveforms.py` (新建)

**修改内容**:
- 添加 `use_upstream_baseline` 配置选项（默认 False）
- 添加 `resolve_depends_on()` 方法实现动态依赖
  - 如果启用 use_upstream_baseline，添加 "baseline" 依赖
- 修改 `compute()` 方法：
  - 获取 use_upstream_baseline 配置
  - 如果启用，从 context 获取上游 baseline 数据
  - 将 upstream_baselines 传递给 WaveformStruct

**配置选项**:
```python
options = {
    "daq_adapter": Option(default="vx2730", type=str),
    "use_upstream_baseline": Option(default=False, type=bool),
}
```

## 使用方式

### 方式 1: 默认行为（不使用上游 baseline）
```python
from waveform_analysis.core.context import Context

ctx = Context()
# ... 注册插件 ...

st_waveforms = ctx.get_data('run_001', 'st_waveforms')

# baseline: WaveformStruct 计算的值
# baseline_upstream: NaN（未提供）
print(st_waveforms[0]['baseline'][:5])          # [100.5, 101.2, ...]
print(st_waveforms[0]['baseline_upstream'][:5]) # [nan, nan, ...]
```

### 方式 2: 使用上游 baseline
```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin

# 创建自定义 baseline 计算插件
class CustomBaselinePlugin(Plugin):
    provides = "baseline"
    depends_on = ["waveforms"]

    def compute(self, context, run_id, **kwargs):
        waveforms = context.get_data(run_id, "waveforms")
        baselines = []
        for waves in waveforms:
            # 使用自定义算法（如中位数）
            bl = np.median(waves[:, 50:100], axis=1)
            baselines.append(bl)
        return baselines

ctx = Context()
ctx.register_plugin(CustomBaselinePlugin())
# ... 注册其他插件 ...

# 启用上游 baseline
ctx.set_config({"st_waveforms.use_upstream_baseline": True})

st_waveforms = ctx.get_data('run_001', 'st_waveforms')

# baseline: WaveformStruct 计算的值（平均值）
# baseline_upstream: CustomBaselinePlugin 计算的值（中位数）
print(st_waveforms[0]['baseline'][:5])          # [100.5, 101.2, ...]
print(st_waveforms[0]['baseline_upstream'][:5]) # [100.3, 101.0, ...]
```

### 方式 3: 在后续插件中使用
```python
class MyAnalysisPlugin(Plugin):
    provides = "my_analysis"
    depends_on = ["st_waveforms"]
    options = {
        "use_upstream_baseline": Option(default=False, type=bool),
    }

    def compute(self, context, run_id, **kwargs):
        st_waveforms = context.get_data(run_id, "st_waveforms")
        use_upstream = context.get_config(self, "use_upstream_baseline")

        for st_ch in st_waveforms:
            # 选择使用哪个 baseline
            if use_upstream and not np.all(np.isnan(st_ch["baseline_upstream"])):
                baselines = st_ch["baseline_upstream"]
            else:
                baselines = st_ch["baseline"]

            # 使用 baseline 进行分析...
```

## 测试验证

**测试文件**: `tests/test_dual_baseline.py`

**测试覆盖**:
1. ✅ ST_WAVEFORM_DTYPE 包含两个 baseline 字段
2. ✅ create_record_dtype() 包含两个 baseline 字段
3. ✅ 无上游 baseline 时，baseline_upstream 为 NaN
4. ✅ 有上游 baseline 时，正确保存上游值
5. ✅ 上游 baseline 长度不匹配时，填充 NaN
6. ✅ 多通道情况下，每个通道使用对应的上游 baseline

**运行测试**:
```bash
python3 tests/test_dual_baseline.py
```

**测试结果**:
```
✓ ST_WAVEFORM_DTYPE 包含两个 baseline 字段
✓ create_record_dtype() 包含两个 baseline 字段
✓ 无上游 baseline 测试通过
✓ 有上游 baseline 测试通过
✓ 上游 baseline 长度不匹配测试通过
✓ 多通道测试通过

所有测试通过！✓
```

## 向后兼容性

### ✅ 完全向后兼容
1. **默认行为不变**:
   - 如果不启用 use_upstream_baseline，baseline_upstream 为 NaN
   - 现有代码继续使用 baseline 字段，无需修改

2. **现有插件无需修改**:
   - BasicFeaturesPlugin、HitFinderPlugin 等继续使用 baseline 字段
   - 不会受到 baseline_upstream 字段的影响

3. **可选功能**:
   - 新功能完全可选，通过配置启用
   - 不启用时，性能和行为与之前完全相同

## 性能影响

### 内存开销
- 每个事件增加 8 字节（一个 float64 字段）
- 对于 100 万事件：增加约 8 MB 内存
- 影响可忽略

### 计算开销
- 只是数组赋值操作，计算开销可忽略
- 如果不启用 use_upstream_baseline，不会获取上游数据

## 数据验证

### 自动验证
- 检查 upstream_baselines 长度是否与 waveforms 匹配
- 长度不匹配时填充 NaN 并记录警告
- 上游数据获取失败时记录警告并继续执行

### 日志输出
```python
# 成功获取上游 baseline
context.logger.info(f"使用上游 baseline，共 {len(upstream_baselines)} 个通道")

# 获取失败
context.logger.warning(f"无法获取上游 baseline: {e}，将使用 NaN 填充")
```

## 应用场景

### 1. 对比不同 baseline 算法
```python
# 对比平均值 vs 中位数
diff = st_waveforms[0]['baseline'] - st_waveforms[0]['baseline_upstream']
print(f"平均差异: {np.mean(diff):.2f}")
```

### 2. 使用更复杂的 baseline 算法
```python
# 上游插件可以实现滤波后的 baseline 计算
class FilteredBaselinePlugin(Plugin):
    def compute(self, context, run_id, **kwargs):
        waveforms = context.get_data(run_id, "waveforms")
        baselines = []
        for waves in waveforms:
            # 应用低通滤波
            filtered = apply_lowpass_filter(waves)
            bl = np.mean(filtered[:, 50:100], axis=1)
            baselines.append(bl)
        return baselines
```

### 3. 调试和验证
```python
# 检查 baseline 计算是否准确
mask = np.abs(st_waveforms[0]['baseline'] - st_waveforms[0]['baseline_upstream']) > 5
if np.any(mask):
    print(f"发现 {np.sum(mask)} 个事件的 baseline 差异超过 5")
```

## 注意事项

### 1. 数据类型一致性
- 两个 baseline 字段都使用 float64 (f8)
- 使用 NaN 表示缺失值（而非 0，避免混淆）

### 2. 通道索引对应
- upstream_baselines 列表的索引必须与 waveforms 列表对应
- 第 i 个 upstream_baselines 元素对应第 i 个通道

### 3. 长度验证
- 每个通道的 upstream_baseline 数组长度必须与该通道的事件数匹配
- 不匹配时自动填充 NaN

### 4. 配置管理
- use_upstream_baseline 默认为 False，保持向后兼容
- 需要显式启用才会使用上游 baseline

## 未来扩展

### 可能的改进
1. 支持多个上游 baseline（baseline_upstream_1, baseline_upstream_2, ...）
2. 添加 baseline 质量指标（如标准差、置信度）
3. 自动选择最佳 baseline（基于质量指标）
4. 支持 baseline 插值和平滑

### 兼容性保证
- 所有未来扩展都将保持向后兼容
- 新字段将作为可选字段添加
- 现有代码无需修改

## 总结

### 实施成果
✅ 成功添加 baseline_upstream 字段到 ST_WAVEFORM_DTYPE
✅ WaveformStruct 支持接收和保存上游 baseline
✅ StWaveformsPlugin 支持动态依赖和配置
✅ 完全向后兼容，现有代码无需修改
✅ 所有测试通过
✅ 性能影响可忽略

### 关键优势
- **灵活性**: 支持多种 baseline 计算方法
- **可扩展性**: 易于添加新的 baseline 算法
- **可调试性**: 可以对比不同算法的结果
- **向后兼容**: 不影响现有代码和工作流

### 文档更新
- ✅ 实施计划文档
- ✅ 代码注释和文档字符串
- ✅ 使用示例和测试用例
- ✅ 本总结文档

---

**实施者**: Claude Sonnet 4.5
**审核状态**: 待审核
**版本**: 1.0
