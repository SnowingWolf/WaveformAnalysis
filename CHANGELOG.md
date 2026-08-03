# Changelog

## v1.5.0

v1.5.0 是自 v1.3.0 以来的重大版本，合并了原计划的 v1.4.0（从未单独发布）与 v1.5.0
的全部变更。本版本以 Plugin Set 4 层架构重组为主线，带来完整的 S1-S2 配对分析
能力、位置重建（position reconstruction）、peaklet 流水线性能优化、可视化增强
以及全新的离线文档站点。

### Highlights

- **Plugin Set 4 层架构重组**（破坏性变更，带兼容层）：将原有 3 层架构重构为
  `io → waveform → hit → peaks → basic_features → tabular → event` 4 层。
  - 新增 `hit` plugin_set（15 个插件）：专门负责 hit 检测、合并与 peaklet 构建。
  - 精简 `peaks` plugin_set（从 19 个减少到 4 个）：仅保留 peak 级别处理。
  - `events.py` 重命名为 `event.py`，`plugins_events()` 更名为 `plugins_event()`，
    保留 `plugins_events` 别名触发 deprecation 警告，旧代码无需修改。
  - 后续迭代：peaklet 插件从 Hit set 移入 Peaks set，event/tabular plugin set 重组，
    进一步收敛插件职责。
- **S1-S2 配对功能完整支持**：`S1S2PairCandidatesPlugin` / `S1S2PairPlugin` /
  `S1S2PairSelectionPlugin` 注册进 `event` plugin_set，新增 `S1S2PairAccessor`
  结构化访问 S1-S2 配对数据（含配对候选来源、排名信息），并提供使用示例文档。
- **Position geometry 与事件重建**：新增 PMT 几何与探测器布局支持，升级
  `PositionReconstructionPlugin`（v0.2.1）实现基于电荷重心法（CoG）的 XY 重建
  与基于漂移时间的 Z 重建，配合 `EventPlugin` 完成完整事件重建链
  `s1_s2_pairs → position_reconstruction → events`。
- **peaklet pipeline 优化**：重构 peaklet 流水线，`peaklet_waveforms` 采用混合
  Numba/Python 处理、多进程支持与向量化 cross-record 检测（bincount），并新增
  `merged_id` 字段修复跨 record 波形求和。
- **hit_merged_features fallback Numba 优化**（version 0.5.0）：fallback 路径改用
  Numba prange kernel，并补充结果校验。
- **可视化增强**：dashboard 增加 2D 直方图、box-select 回调、对数颜色刻度
  （LogNorm）、直方图控件与选择联动，3D/散点渲染优化（降采样、WebGL 错误容忍），
  默认直方图 bins 从 40 提升到 100；集成 xihu_fast_analysis dashboard 风格
  2D density map。
- **离线文档站点**：新增可交互的离线文档站点（含插件 DAG lineage 图、
  plotly 谱系边、可点击 lineage、插件引用卡片分组），发布 verified agent 文档
  与文档 DAG 协议，并支持多 merged_index 波形合并绘制。
- **Context 公共 API**：第一阶段 Context 公共 API 平衡收敛，组合 context 插件域，
  补充富 context 插件文档。
- **新依赖**：`pyarrow` 成为必需依赖。

### 性能优化

- `peaklet_waveforms`：混合 Numba/Python 处理、多进程支持、向量化 cross-record
  检测（bincount 10-30x 加速类路径）。
- `hit_merged_features` fallback：Numba prange kernel 优化。
- `position_reconstruction`：XY 计算向量化，10-30x 提速。
- `PeakChannelAccessor`：numpy groupby 替代 Python 循环构建索引；波形查找缓存。
- S1-S2 候选展开与 peak pipeline 热路径向量化。
- dashboard 3D 渲染、散点降采样与交互延迟优化。

### Bug 修复

- 修复 S1-S2 配对 rank 字段 int16 溢出（升级为 int32，防止数据损坏）。
- 保留并恢复 `plugins_events` 命名以保持向后兼容。
- 保留有符号 peaklet 波形、追踪 peaklet waveform pool lineage。
- 修复 V1725 事件边界保持与 VX2730 采集窗口。
- 修复 sum waveform 与 channel waveforms 时间轴对齐。
- 移除 records / numba import hazards，序列化 tuple 选项类型。
- 修复 dashboard 交互延迟、HTML 布局抖动、WebGL shader 错误与 null 值过滤。
- S1-S2 候选宽度保持 ns 单位；position 漂移速度默认 mm/ns。

### 弃用与兼容性

- `S1S2ClassifierPlugin` 标记为 deprecated，S1/S2 分析请使用现代配对链路。
- `event` plugin_set 全部插件标记为 deprecated（保留 `plugins_event`/`plugins_events`
  兼容入口）。
- 移除显式配置兼容 API，retire peak channel compatibility API。
- 新增 compact workflow fast paths，引入测试分层（`-m 'not slow'`）。

### 文档

- 新增 Run6 Xe 教学 notebook、S1-S2 配对使用示例与 `S1S2PairAccessor` 示例。
- 新增/完善 Accessor 参考页、plugin 文档 DAG、agent 协作工作台与 agent profile
  文档。
- 归档历史报告与 notebook 至 `archive/reports/`。

### Validation

- Release baseline: `v1.3.0`（v1.4.0 未单独发布，内容并入本版本）
- Required gates:
  - `python scripts/release_artifact_sync.py --base v1.3.0`
  - `python -m pytest tests/`（快速层 1349 passed + slow 层 15 passed）

## v1.3.0

This release builds on v1.2.0 with peak-channel access utilities, corrected
sum-waveform visualization, and new example workflows for channel inspection
and plotting.

### Highlights

- Added `PeakChannelAccessor` for structured per-channel peak inspection with
  lazy waveform loading and plotting helpers.
- Fixed `plot_peak_channels_with_sum` / `create_peak_plotter` to reuse the
  peaklet sum waveform instead of recomputing it from raw records.
- Added example scripts and docs for peak-channel access and sum-waveform
  comparison.

### Validation

- Release baseline: `v1.2.0`
- Required gates:
  - `python scripts/release_artifact_sync.py --base v1.2.0`
  - `python -m pytest tests/`

## v1.2.0

This release builds on v1.1.0 with peaklet classification improvements,
visualization utilities, DAQ/cache usability updates, and additional quality
documentation.

### Highlights

- Added and refined peaklet S1/S2 classification support, including channel role
  veto masks, save policy documentation, and corrected component configuration
  handling.
- Expanded peak and hit analysis helpers with `peak_id` alignment fixes,
  `hit_merged` timing fields, and waveform query utilities.
- Improved visualization workflows with optimized `corner_hist` execution,
  overlay/transparency support, flexible layout controls, and cut-line helpers.
- Enhanced DAQ and context observability with cache status display, time range
  filtering, row limits, plugin execution timing, and global execution config
  reporting.
- Added optimization and testing documentation for performance-sensitive
  workflows, and kept release performance gates aligned with the records-backed
  `hit_threshold` dependency chain.

### Validation

- Release baseline: `v1.1.0`
- Required gates:
  - `python scripts/release_artifact_sync.py --base v1.1.0`
  - `python -m pytest tests/`

## v1.1.0

This release focuses on records/v1725 processing performance, peaklet and peaks
plugin coverage, visualization utilities, and stricter release quality checks.

### Highlights

- Optimized v1725 records building with streaming part generation, run-scoped
  merge stages, controlled parallel merge execution, progress reporting, and
  profiler/debug metadata.
- Improved DAQ/v1725 overview scanning, records-backed data access, polarity
  application, and `records_view` signal fast paths for larger datasets.
- Expanded peaks and peaklet plugin support, including peaklet channel/features/
  waveforms plugins, waveform-backed peaklets, records asymmetry masks, and
  updated peak lineage features.
- Optimized hit merge and `hit_merged_features` execution paths with
  pre-allocation and Numba-backed hot paths where appropriate.
- Added lineage visualization fixes, statistical plotting utilities, and top
  level visualization exports.
- Strengthened agent workflow documentation, plugin version policy, generated
  plugin references, release gates, and regression test coverage.

### Validation

- Release baseline: `v1.0.0`
- Required gates:
  - `python scripts/release_artifact_sync.py --base v1.0.0`
  - `python -m pytest tests/`
