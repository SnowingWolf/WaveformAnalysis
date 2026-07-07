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

**现状分析**:
- ✅ 框架已有 `PositionReconstructionPlugin` 骨架（v0.0.0）
  - 位置: `waveform_analysis/core/plugins/builtin/cpu/position_reconstruction.py`
  - 数据结构完整（32 字段，包括 x, y, z, 误差、质量指标、标志位）
  - Z 坐标已实现（drift_time × drift_velocity）
  - XY 坐标预留接口（待实现）
- ✅ 数据流已就绪: `s1_s2_pairs` → `position_reconstruction` → `events`
- ✅ `PeakChannelAccessor` 可获取通道级数据
- ❌ 缺少 PMT 几何布局系统
- ❌ 缺少 XY 坐标重建算法

**功能需求**:
- **PMT 几何布局系统**:
  - 支持 PMT 位置映射（board, channel → x, y 坐标）
  - 支持增益校正（每个 PMT 的 gain 参数）
  - 支持全局配置或 run-specific 配置
  - 提供 fallback 默认布局（7-PMT 配置）
- **X-Y 位置重建**:
  - 电荷重心法 (Center of Gravity, CoG)
  - 基于 S2 通道光分布计算加权重心
  - 应用 PMT 增益校正
  - 输出位置坐标、质量标志
- **Z 位置重建**:
  - 基于 S1-S2 漂移时间（已实现）
  - 可配置漂移速度参数
- **位置质量评估**:
  - 边界事件标记（`FLAG_EDGE_EVENT`）
  - 低信号质量标记（`FLAG_LOW_S2_SIGNAL`）
  - 重建成功标志（`FLAG_XY_RECONSTRUCTED`, `FLAG_Z_RECONSTRUCTED`）
- **数据访问增强**:
  - 扩展 `S1S2PairAccessor` 添加位置访问方法
  - 支持获取重建位置数据

**技术方案**:

**方案决策**（已确认）:
- ✅ 复用现有 `PositionReconstructionPlugin`（升级 v0.0.0 → v0.1.0）
- ✅ PMT 布局作为全局配置管理
- ✅ v0.1.0 仅实现电荷重心法（CoG），暂不支持算法切换
- ✅ 使用框架现有缓存机制
- ✅ 可视化保持为独立模块（不集成到框架）

**实施内容**:

1. **新建几何模块**: `waveform_analysis/core/hardware/geometry.py`
   - 移植自 `xihu_fast_analysis/layout.py`
   - 类: `PmtEntry`, `PmtLayout`, `load_pmt_layout()`
   - 配置方式:
     ```python
     ctx.set_config({
         "detector_geometry": {
             "pmt_mapping": [
                 {"board": 0, "channel": 15, "pmt_no": 1,
                  "x_mm": -26.8, "y_mm": 17.7, "gain": 9.2e6},
                 # ... 更多 PMT
             ],
             "default_gain": 9.2e6,
             "detector_radius": 62.5,  # mm
         }
     })
     ```

2. **升级 PositionReconstructionPlugin** (v0.0.0 → v0.1.0):
   - 实现电荷重心算法:
     ```python
     # 伪代码
     channels = PeakChannelAccessor.get_peak_channels(s2_peak_id)
     sum_q, sum_qx, sum_qy = 0, 0, 0
     for ch in channels:
         pmt = layout.entry_for_readout(ch.board, ch.channel)
         q_corrected = ch.area / pmt.gain
         sum_q += q_corrected
         sum_qx += q_corrected * pmt.x_mm
         sum_qy += q_corrected * pmt.y_mm
     x = sum_qx / sum_q
     y = sum_qy / sum_q
     ```
   - 配置选项:
     - `drift_velocity` (mm/ns): 漂移速度，默认 1.3
     - `min_s2_area_for_xy`: XY 重建的最小 S2 面积
     - `edge_threshold_mm`: 边缘事件判定阈值
   - 质量标志设置:
     - `FLAG_XY_RECONSTRUCTED`: XY 成功重建
     - `FLAG_EDGE_EVENT`: 边界事件
     - `FLAG_LOW_S2_SIGNAL`: S2 信号过弱

3. **扩展 S1S2PairAccessor** (最小增强):
   - 添加方法: `get_positions()` 获取位置数据
   - 保持简洁，不添加复杂过滤功能

**相关文件**:
- 新增: `waveform_analysis/core/hardware/geometry.py`
- 修改: `waveform_analysis/core/plugins/builtin/cpu/position_reconstruction.py` (v0.0.0 → v0.1.0)
- 修改: `waveform_analysis/utils/s1_s2_pair_accessor.py` (添加位置访问方法)
- 新增: `tests/plugins/test_position_reconstruction.py`
- 新增: `examples/export_positions_for_visualization.py` (可视化数据导出)
- 参考: `/home/wangjun/workspace/Westlake_TPC/xihu_fast_analysis/xihu_fast_analysis/`
  - `pipeline.py` (XY 重建算法，82-113 行)
  - `layout.py` (PMT 布局系统)
  - `dashboard.py` (可视化参考)

**实现阶段**:
- **Phase 1: 基础功能** (v0.1.0, 优先实施)
  - PMT 几何布局系统（全局配置）
  - 电荷重心法 XY 重建
  - 基础测试
  - 预计工作量: 6-9 小时

- **Phase 2: 增强功能** (v0.2.0+, 未来工作)
  - 高级重建算法（最大似然、神经网络）
  - 不确定度估计（填充 x_err, y_err, z_err）
  - 位置相关修正（电场、光收集效率）
  - 性能优化（Numba/GPU 加速）

**验证标准** (Definition of Done):
- [ ] PMT 布局可从全局配置正确加载
- [ ] XY 坐标对所有有效 S2 正确计算
- [ ] 增益校正正确应用
- [ ] 质量标志正确设置
- [ ] 单元测试通过
- [ ] 与 xihu_fast_analysis 结果一致（误差 < 1%）

**优先级**: High
**复杂度**: Medium (Phase 1), High (Phase 2+)
**预计工作量**:
- Phase 1 (v0.1.0): 6-9 小时
- Phase 2+ (v0.2.0+): 10-15 天 (未来)

**依赖和注意事项**:
- 需要准确的 PMT 位置和增益参数
- 需要测试数据验证重建结果
- 高级算法（Phase 2+）需要光响应函数和训练数据
- 详细实施计划见: `.claude/plans/purring-singing-sonnet.md`

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
