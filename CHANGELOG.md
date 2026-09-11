# Changelog

## v2.0.0 — 2026-09-11

本版本汇总 v1.5.0（2026-08-03）以来的改动，包含截至 `84bd5a8` 的 126 个开发提交及本次发布整理。重点是文档系统升级、模块与公开导入整理、分析与可视化改进，以及缓存和磁盘占用修复。因公开 API 与部分字段语义发生变化，版本升级为 2.0.0。

### 文档系统

- 文档站迁移至 Next.js，恢复并统一丰富的插件参考、dtype 字段说明、流程图、依赖/lineage 图和 CLI 页面；改善导航、窄屏布局、键盘交互与静态加载。
- 新增隔离文档构建流程：从发布源码生成站点、校验静态导出及清单，并将预构建站点随 Python 包分发。使用预构建站点无需重新运行 Node 构建。
- 文档 CLI 的规范入口为 `waveform_analysis.documentation.cli:main`。升级安装后应使用发行包生成的 `waveform-docs` 启动脚本。

### 包结构与开发工作流

- 插件实现按独立 bundle 组织，并随包分发相关 manifest、技能说明和依赖声明。
- 新增 `waveform_analysis.plugins` 公开入口；文档、采集、分析、可视化实现归入各自职责包。保留已测试的旧导入兼容入口与对象身份，但不应继续依赖未承诺的内部模块路径。
- 根包、插件导出与 CLI 采用延迟加载，减少无关初始化。
- 更新仓库 Agent 工作流与任务契约，加入隔离 Executor/Reviewer 执行、审查与交接机制。

### 分析与可视化

- 优化 records-backed peaklet 处理、通道聚合、波形准备及部分 Numba 路径；位置重建复用批量通道数据，减少重复构建 Accessor。
- 改进 S1-S2 orphan 候选生成并修正过滤时的评分边界；修复重复峰通道波形以及重复位置布局语义。
- 新增自适应二维分层采样、corner histogram 的 symlog 支持、S2 候选波形绘制及 PDF 图形导出工具，统一二维位置 dashboard。
- `energy_reconstruction` 目前仅提供结构占位：能量为 NaN 并带未实现标记，不代表已有可用于物理分析的能量重建算法。

### 缓存与 V1725 磁盘占用

- 修复重算时下游 lineage 缓存失效与缓存键稳定性问题。
- V1725 磁盘合并成功后，校验最终计数、文件尺寸和波形索引边界，关闭中间映射并回收本次原始分片与排序中间文件。
- 最终 `records`、`wave_pool` 继续由磁盘引用持有，读取能力保持；共享构建插件版本为 `0.14.3`。
- 该修复减少合并后的持续占用，不限制合并期间峰值，不自动删除历史临时目录，也不解决进程强杀后的全部残留。

### 升级与迁移

1. 删除了 `Context.clear_time_index()` 和 `Context.get_time_index_stats()`。时间索引由 `time_range()` / `build_time_index()` 管理，调用方需移除对旧管理 API 的依赖。
2. `events.s1_time` / `s2_time` 修正为皮秒（ps）；检查下游时间换算，避免继续依赖旧的错误缩放。
3. `peaklet_features` / `peaks` 的 `fall_time` 改为累计面积分位数 `t90 - t50`（ns），不再使用 `t90 - time_peak`。依赖旧定义的筛选阈值、图表和模型需要重新核对。
4. 建议采用 `from waveform_analysis import Context`，插件类及 plugin set 从 `waveform_analysis.plugins` 导入。升级后重启 Notebook 内核和长驻进程；已有缓存是否重用由各插件版本与 lineage 判定。

### 验证

本地发布候选已完成以下验证：

- Python 3.12 快速层：1779 passed，2 skipped；慢速层：15 passed。
- 全仓库 Black、Ruff、插件依赖与 shim 完备性检查通过；两套插件参考各生成 37 页且无漂移。
- TypeScript 类型检查通过，Vitest 共 26 项通过；隔离的 Next.js 静态构建成功，包内外站点模型一致。
- schema smoke 通过：`raw_files=2`、`st_waveforms=24`、`hit=0`、`df=24`、`events=12`。
- 以 v1.5.0 为基线的五目标性能检查通过；代表性输入为 1,228,800 samples，时间与峰值内存变化均低于 10% 和 15% 阈值。
- 完整 `release_artifact_sync` 聚合闸门通过，未跳过测试或性能检查。

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
