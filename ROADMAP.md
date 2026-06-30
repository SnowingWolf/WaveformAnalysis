# Development Roadmap

本文档记录 WaveformAnalysis 项目的未来开发计划和功能路线图。

---

## 版本规划

### v1.5.0 - S1/S2 分析增强

**目标发布时间**: TBD
**主题**: 增强 S1/S2 peak 分析能力，支持更复杂的物理场景

#### 1. S1/S2 Peak Valley 分割 (Peak Splitting)

**背景**:
在某些情况下，单个 peak 中可能同时包含 S1 和 S2 信号（例如，S1 和 S2 时间间隔非常短时），当前的 peak finder 会将它们识别为一个 peak。需要实现基于波形谷值（valley）的分割算法，将这类复合 peak 正确分离。

**功能需求**:
- 实现 valley-based peak splitting 算法
- 检测 peak 内部的显著谷值点
- 基于谷值位置将单个 peak 分割为多个独立 peak
- 保留原始 peak 的元数据用于溯源
- 支持配置分割阈值参数（valley depth, minimum separation 等）

**技术方案**:
- 新增插件: `PeakValleySplitterPlugin`
- 插入位置: `peaks` plugin_set，在 `S1S2ClassifierPlugin` 之前
- 输入: `peaks` (合并后的 peaks)
- 输出: `peaks_split` (分割后的 peaks，保留指向原始 peak 的引用)
- 算法: 基于一阶导数零点或二阶导数极值检测 valley

**相关文件**:
- 实现: `waveform_analysis/core/plugins/builtin/peaks/peak_valley_splitter.py`
- 测试: `tests/plugins/test_peak_valley_splitter.py`
- 文档: `docs/plugins/reference/agent/PeakValleySplitterPlugin.md`

**优先级**: High
**复杂度**: Medium
**预计工作量**: 3-5 days

---

#### 2. S1 多 S2 配对选择 (Multiple S2 Selection)

**背景**:
在实际物理事件中，一个 S1 可能对应多个 S2 信号（例如，电子在液体中发生多次散射）。当前的 `S1S2PairSelectionPlugin` 为**每个 S2 选择最优 S1**（S2-centric），需要扩展支持**为每个 S1 选择多个 S2**（S1-centric）的场景。

**现状分析**:
- ✅ 候选生成阶段（`S1S2PairCandidatesPlugin`）已经支持一对多关系
- ✅ 已记录 `n_s1_candidates_for_s2` 和 `n_s2_candidates_for_s1`
- ⚠️ 选择阶段（`S1S2PairSelectionPlugin`）当前逻辑：为每个 S2 选最优 S1
- ❌ 缺少：为每个 S1 选择 top-N 个 S2 的逻辑

**功能需求**:
- 扩展 `selection_mode` 支持双向选择:
  - 现有（S2-centric）: `largest`, `nearest`, `best_score`, `all`
  - **新增（S1-centric）**: `s1_to_top_n_s2`, `s1_to_all_s2`
- 为每个 S1 选择 top-N 个 S2（按 score 或其他标准排序）
- 支持配置最大 S2 数量限制（避免极端情况）
- 在输出中保留选择模式和排名信息

**技术方案**:
- **修改插件**: `S1S2PairSelectionPlugin`
- **新增配置选项**:
  ```python
  selection_mode: str = "largest"  # 现有 + 新增 "s1_to_top_n_s2"
  max_s2_per_s1: int = 5  # S1-centric 模式下每个 S1 最多选择的 S2 数量
  s2_ranking_criterion: str = "area"  # "area" | "score" | "time"
  ```
- **修改逻辑**:
  - 在 `_select_best_pairs()` 中增加 S1-centric 分支
  - 复用现有的 `rank_for_s1` 字段进行排序
  - 利用现有的 `selected` 标志标记最终选中的配对

**相关文件**:
- 修改: `waveform_analysis/core/plugins/builtin/cpu/s1_s2_pair_selection.py`
- 测试: `tests/plugins/test_s1_s2_pairing.py` (扩展测试用例)
- 文档: `docs/plugins/reference/agent/S1S2PairSelectionPlugin.md` (更新)
- 示例: `examples/s1_s2_multiple_s2_per_s1.ipynb`

**优先级**: High
**复杂度**: Low-Medium（基础架构已完善，主要是逻辑扩展）
**预计工作量**: 2-3 days

---

#### 3. S1/S2 质量选择增强 (Enhanced Quality Selection)

**背景**:
在配对过程中，不同的 S1 和 S2 peak 质量差异很大。当前的配对系统已有基础的质量控制机制，需要扩展为更完整、可配置的质量筛选系统。

**现状分析**:
- ✅ `S1S2PairCandidatesPlugin` 已支持:
  - 最小面积阈值: `min_s1_area`, `min_s2_area`
  - 质量标志: `FLAG_S1_LOW_QUALITY`, `FLAG_S2_LOW_QUALITY` (已定义但未充分使用)
- ✅ `S1S2PairSelectionPlugin` 已支持:
  - 质量打分: `score_s1_quality`, `score_s2_quality`, `score_ratio`
  - 竞争检测: `FLAG_CLOSE_COMPETITOR`
- ⚠️ 缺少系统化的质量标准配置和筛选报告

**功能需求**:
- **增强候选生成阶段** (`S1S2PairCandidatesPlugin`):
  - 扩展质量阈值配置（面积、宽度、通道数、信噪比）
  - 充分利用现有的 `FLAG_S1_LOW_QUALITY` 和 `FLAG_S2_LOW_QUALITY`
  - 添加配对级别约束（drift time 范围、S2/S1 ratio 范围）
- **增强选择阶段** (`S1S2PairSelectionPlugin`):
  - 细化质量打分算法（可配置权重）
  - 支持基于质量标志的过滤
  - 输出质量统计信息

**技术方案**:
- **方案 A（推荐）**: 扩展现有两个插件的配置选项
  - 修改: `S1S2PairCandidatesPlugin` - 增强阈值配置
  - 修改: `S1S2PairSelectionPlugin` - 增强打分和筛选逻辑
  - 优点: 复用现有架构，保持两阶段设计的一致性

- **方案 B（备选）**: 新增后处理插件
  - 新增: `S1S2QualityFilterPlugin`
  - 插入位置: 在 `S1S2PairSelectionPlugin` 之后
  - 输入: `s1_s2_pairs`
  - 输出: `s1_s2_pairs_filtered`
  - 优点: 不影响现有插件，可独立开关

**配置扩展（方案 A）**:
```python
# S1S2PairCandidatesPlugin 新增配置
quality_thresholds = {
    "s1_area_range": (10, 10000),      # PE
    "s2_area_range": (100, 1000000),   # PE
    "s1_width_range": (10, 1000),      # ns
    "s2_width_range": (100, 20000),    # ns
    "s1_min_channels": 3,
    "s2_min_channels": 5,
    "drift_time_range": (0, 100000),   # ns (用于替代 min/max_drift_time)
    "log10_s2_s1_range": (0.5, 3.0),   # log10(S2/S1)
}

# S1S2PairSelectionPlugin 新增配置
quality_filter_mode = "strict"  # "off" | "warn" | "strict"
min_quality_score = 0.5  # 最小质量分数阈值
```

**相关文件**:
- 修改: `waveform_analysis/core/plugins/builtin/cpu/s1_s2_pair_candidates.py`
- 修改: `waveform_analysis/core/plugins/builtin/cpu/s1_s2_pair_selection.py`
- 测试: `tests/plugins/test_s1_s2_pairing.py` (扩展测试用例)
- 文档: 更新两个插件的文档页面
- 示例: `examples/s1_s2_quality_selection.ipynb`

**优先级**: Medium
**复杂度**: Low-Medium（基础设施已有，主要是配置扩展和逻辑完善）
**预计工作量**: 2-4 days

---

#### 4. 位置重建 (Position Reconstruction)

**背景**:
在双相时间投影室（TPC）中，通过分析 S2 信号在不同 PMT 通道上的分布，可以重建粒子相互作用在 X-Y 平面的位置。Z 坐标则由漂移时间确定。位置重建是物理分析的核心功能，用于 fiducialization（排除边界事件）、空间相关修正、以及物理分析。

**功能需求**:
- **X-Y 位置重建**:
  - 基于 S2 通道波形的光分布模式
  - 支持多种算法:
    - 重心法 (Center of Gravity)
    - 最大似然法 (Maximum Likelihood)
    - 神经网络法 (Neural Network, 预留)
  - 输出位置坐标、不确定度、算法置信度
- **Z 位置重建**:
  - 基于 S1-S2 漂移时间
  - 考虑电场强度、温度、压力修正
  - 输出 Z 坐标和不确定度
- **位置质量评估**:
  - 重建算法收敛性检查
  - 边界事件标记
  - 多解检测（如果存在）
- **探测器几何和 PMT 响应**:
  - 支持可配置的探测器几何参数
  - 支持 PMT 位置映射和响应校准
  - 支持增益不均匀性修正

**技术方案**:
- **新增插件组** (位置重建子系统):
  - `PositionReconstructionXYPlugin`: X-Y 平面位置重建
  - `PositionReconstructionZPlugin`: Z 方向位置重建（基于漂移时间）
  - `Position3DPlugin`: 合成 3D 坐标（可选）
- **插入位置**: `event` plugin_set，在 `S1S2PairSelectionPlugin` 之后
- **依赖数据**:
  - `s1_s2_pairs`: 配对结果（用于 drift time）
  - `peaklet_channels` 或 `peak_channels`: 通道级波形信息
  - `channel_metadata`: PMT 位置和增益信息
- **输出字段**:
  ```python
  position_dtype = [
      ("pair_id", "i8"),           # 关联到配对
      ("x", "f4"), ("y", "f4"), ("z", "f4"),  # 重建坐标 (mm)
      ("x_err", "f4"), ("y_err", "f4"), ("z_err", "f4"),  # 不确定度
      ("r", "f4"),                 # 径向坐标 r = sqrt(x^2 + y^2)
      ("algorithm", "U16"),        # 使用的算法
      ("chi2", "f4"),              # 拟合优度
      ("n_channels_used", "i2"),   # 用于重建的通道数
      ("flags", "u4"),             # 重建质量标志
  ]
  ```

**算法选项**:
```python
# PositionReconstructionXYPlugin 配置
position_algorithm = "cog"  # "cog" | "ml" | "nn" (预留)
min_channels_for_position = 5  # 最小通道数要求
use_top_array_only = False  # 仅使用顶部 PMT 阵列
apply_gain_correction = True  # 是否应用增益修正
fiducial_radius = 350.0  # mm, 用于标记边界事件

# PositionReconstructionZPlugin 配置
drift_velocity = 1.335  # mm/us, 典型液氙漂移速度
cathode_z = -1000.0  # mm, 阴极位置
gate_z = 0.0  # mm, 栅极位置
```

**相关文件**:
- 新增: `waveform_analysis/core/plugins/builtin/cpu/position_reconstruction_xy.py`
- 新增: `waveform_analysis/core/plugins/builtin/cpu/position_reconstruction_z.py`
- 新增: `waveform_analysis/core/plugins/builtin/cpu/position_3d.py` (可选)
- 工具: `waveform_analysis/utils/position/` (算法实现、几何工具)
- 测试: `tests/plugins/test_position_reconstruction.py`
- 文档: `docs/plugins/reference/agent/PositionReconstructionXYPlugin.md`
- 示例: `examples/position_reconstruction_tutorial.ipynb`

**实现阶段**:
- **Phase 1**: 基础架构和重心法
  - 插件框架、数据结构
  - 简单的重心算法实现
  - 基本的 Z 坐标计算
- **Phase 2**: 高级算法
  - 最大似然法实现
  - 增益和几何修正
  - 不确定度估计
- **Phase 3**: 质量控制和优化
  - 边界检测和 fiducialization
  - 性能优化（Numba 加速）
  - 多种探测器几何支持

**优先级**: High
**复杂度**: High
**预计工作量**: 10-15 days (分阶段实现)

**依赖和注意事项**:
- 需要准确的探测器几何参数和 PMT 映射
- 需要 PMT 增益校准数据
- 最大似然法需要光响应函数（Light Response Function, LRF）
- 神经网络方法需要训练数据集和模型管理

---

## 实现顺序建议

### 优先级 1: 配对系统完善（v1.5.0 核心）
这些功能完善现有的 S1/S2 配对系统，工作量小、见效快，优先完成：

1. **S1 多 S2 选择** (2-3 days)
   - 扩展现有 `S1S2PairSelectionPlugin`
   - 复用已有基础设施
   - 为后续物理分析提供灵活性

2. **质量选择增强** (2-4 days)
   - 扩展现有两个配对插件的配置
   - 完善质量控制机制
   - 可与功能 1 并行开发

### 优先级 2: 信号分割（v1.5.0 扩展）
独立性强，但需要更多测试和调优：

3. **Peak Valley 分割** (3-5 days)
   - 独立的新插件
   - 为复杂信号场景提供支持
   - 需要充分的测试数据验证

### 优先级 3: 位置重建（v1.6.0 或独立模块）
复杂度最高，可作为独立的大功能开发：

4. **位置重建** (10-15 days, 分阶段)
   - 新的子系统，涉及多个插件
   - 依赖探测器几何和校准数据
   - 建议分阶段实现：
     - Phase 4.1: 基础架构 + 重心法 (5 days)
     - Phase 4.2: 高级算法 + 修正 (5 days)
     - Phase 4.3: 质量控制 + 优化 (5 days)

### 推荐路线
- **快速迭代路线**: 功能 1 → 功能 2 → 功能 3 → 发布 v1.5.0 → 功能 4 → 发布 v1.6.0
- **并行开发路线**: (功能 1 + 功能 2) 并行 → 功能 3 → 发布 v1.5.0 → 功能 4 (分阶段) → 发布 v1.6.0

---

## 依赖和风险

### 技术依赖
- **Peak valley 分割**: 可靠的波形数据和降噪
- **多 S2 选择**: 准确的 S1/S2 分类（已有）
- **质量选择**: 充分的物理参数校准数据
- **位置重建**:
  - 探测器几何参数（PMT 位置、探测器尺寸）
  - PMT 增益校准数据
  - 光响应函数（用于 ML 算法）

### 潜在风险
- **Valley 分割**: 低信噪比情况下可能产生假分割
- **多 S2 选择**: 极端情况下可能显著增加输出数据量
- **质量选择**: 阈值参数需要针对不同探测器和运行条件调优
- **位置重建**:
  - 算法性能高度依赖校准质量
  - 不同探测器几何需要独立验证
  - ML 算法需要大量训练数据

### 缓解措施
- **Valley 分割**: 提供保守的默认参数，避免过度分割
- **多 S2 选择**:
  - 设置合理的 `max_s2_per_s1` 默认值
  - 提供 warning 机制检测异常情况
- **质量选择**: 提供不同探测器的配置模板和推荐参数
- **位置重建**:
  - 从简单算法（重心法）开始，逐步增加复杂度
  - 提供位置重建质量检查工具
  - 文档中明确说明校准数据要求

---

## 相关资源

### 参考文献
- TBD: 添加相关的物理分析论文和算法参考

### 相关 Issue/Discussion
- TBD: 链接到 GitHub issues 或内部讨论

### 数据集
- TBD: 用于测试和验证的标准数据集

---

## 版本规划总结

### v1.5.0 - S1/S2 分析增强
**主要功能**:
1. S1/S2 Peak Valley 分割
2. S1 多 S2 配对选择
3. S1/S2 质量选择增强

**预计总工作量**: 7-12 days
**目标发布**: TBD

### v1.6.0 - 位置重建
**主要功能**:
4. 位置重建（X-Y-Z 坐标）

**预计总工作量**: 10-15 days
**目标发布**: TBD

---

## 版本历史

- 2026-06-30: 初始版本，添加 v1.5.0 三个核心功能 + v1.6.0 位置重建功能规划
