# Release Notes - v1.4.0

**发布日期**: 2026-06-29
**基线版本**: v1.3.1 → v1.4.0
**分支**: release/v1.4.0

---

## 🎯 版本亮点

### 1. Plugin Set 架构重组 (Breaking Change with Compatibility)
将原有的 3 层架构重构为更清晰的 4 层架构，提升可维护性和模块化程度。

**新架构**:
```
io → waveform → hit → peaks → basic_features → tabular → event
```

**变更详情**:
- **新增 `hit` plugin_set** (15 个插件)：专门负责 hit 检测、合并和 peaklet 构建
- **精简 `peaks` plugin_set** (从 19 个减少到 4 个)：仅保留 peak 级别的处理
- **重命名 `events.py` → `event.py`**：函数名从 `plugins_events` 改为 `plugins_event`
- **向后兼容**：保留 `plugins_events` 别名，旧代码无需修改

**迁移指南**:
- 使用 `cpu_default` profile 的用户：无需任何改动，自动使用新架构
- 自定义 plugin 列表的用户：建议更新为新的 4 层结构，但旧代码仍可运行

---

## ✨ 新功能

### S1-S2 配对功能完整支持
- 在 `event` plugin_set 中注册 S1-S2 配对插件 (commit: 97d514f)
- 新增配对示例文档和教程 (commit: ea15830)

### 可视化增强
- **特征信息显示优化** (commit: d3598e1)
  - 移动特征信息到右上角
  - 支持多行显示
- **自定义特征和 hit 窗口显示** (commit: 88a3d59)
- **波形时间轴对齐修复** (commit: 5df5faa)
  - 修复 sum waveform 与 channel waveforms 的时间轴对齐问题

### 工具类改进
- `PeakChannelAccessor` 使用 peaklet channel 特征 (commit: dce3d71)
- 向量化索引构建，用 numpy groupby 替代 Python 循环 (commit: 95cfad5)

---

## 🐛 Bug 修复

### 关键修复
- **修复 S1-S2 配对 rank 字段的 int16 溢出** (commit: ff69e0e)
  - 问题：rank 值超出 int16 范围导致数据损坏
  - 解决：将相关字段类型升级为 int32

### 向后兼容修复
- 恢复 `plugins_events` 命名以保持向后兼容 (commit: 7909e69)
- 标记所有 event plugin_set 插件为 deprecated (commit: 821e695)

---

## 📚 文档更新

- 新增 Run6 Xe 教学 notebook (commit: 425601b)
- 新增 S1-S2 配对使用示例 (commit: ea15830)
- 丰富配对候选来源说明 (commit: 01a7ac9)

---

## 🔧 依赖变更

- **新增必需依赖**: `pyarrow` (commit: bffe75a)

---

## 📊 详细变更列表

### Plugin Set 架构 (2cd90fd)

**新 4 层架构**:

1. **waveform** (5 plugins): 波形提取和 records
2. **hit** (15 plugins): hit 检测、合并和 peaklet 构建
   - `HitFinderPlugin`
   - `RecordsAsymmetryMaskPlugin`
   - `RecordsDetectorMaskPlugin`
   - `RecordsVetoMaskPlugin`
   - `ThresholdHitPlugin`
   - `HitMergeClustersPlugin`
   - `HitMergePlugin`
   - `HitMergedComponentsPlugin`
   - `HitMergedFeaturesPlugin`
   - `PeakletPlugin`
   - `PeakletComponentsPlugin`
   - `PeakletWaveformPlugin`
   - `PeakletWaveformPoolPlugin`
   - `PeakletFeaturesPlugin`
   - `PeakletChannelsPlugin`

3. **peaks** (4 plugins): peak 构建和分类
   - `PeaksPlugin`
   - `WaveformWidthPlugin`
   - `S1S2ClassifierPlugin`
   - `PeakClassificationPlugin`

4. **event** (3 plugins): event 分组和配对
   - `EventGroupPlugin`
   - `S1S2PairCandidatesPlugin`
   - `S1S2PairPlugin`

---

## ⚠️ 破坏性变更

### 1. Plugin Set 函数名变更
- **旧**: `plugins_events()`
- **新**: `plugins_event()`
- **兼容性**: 保留 `plugins_events` 别名，旧代码仍可运行，但会触发 deprecation 警告

### 2. CPU Default Profile 更新
- **旧**: `io → waveform → peaks → basic_features → tabular → events`
- **新**: `io → waveform → hit → peaks → basic_features → tabular → event`

---

## 🧪 测试状态

- ✅ 所有测试通过
- ✅ 向后兼容性测试通过
- ✅ 新架构功能测试通过

---

## 📦 升级建议

### 从 v1.3.x 升级

1. **最小化升级** (推荐大多数用户):
   ```python
   # 无需修改代码，直接升级即可
   pip install --upgrade waveform-analysis
   ```

2. **完整升级** (自定义 plugin 列表的用户):
   ```python
   # 旧代码 (仍可工作，但建议更新)
   from waveform_analysis.core.plugins.plugin_sets import plugins_events

   # 新代码 (推荐)
   from waveform_analysis.core.plugins.plugin_sets import plugins_event
   from waveform_analysis.core.plugins.plugin_sets import plugins_hit
   ```

3. **添加新依赖**:
   ```bash
   pip install pyarrow
   ```

---

## 🔗 相关链接

- **完整变更日志**: 14 个提交，涵盖架构重构、bug 修复和功能增强
- **关键提交**:
  - `2cd90fd`: Plugin Set 4 层架构重组
  - `ff69e0e`: S1-S2 配对 int16 溢出修复
  - `97d514f`: 注册 S1-S2 配对插件
  - `95cfad5`: PeakChannelAccessor 性能优化

---

## 🙏 贡献者

- snowjohn
- Claude Opus 4.8 (Co-Author)

---

## 📅 下一步计划

- v1.4.1: 进一步优化性能和内存使用
- v1.5.0: 扩展可视化功能，支持更多自定义选项
