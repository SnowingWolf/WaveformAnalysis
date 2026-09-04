# Changelog

## Unreleased

### Breaking changes

- 移除 `Context.clear_time_index()` 与 `Context.get_time_index_stats()` 公开 API。时间索引由 `time_range()`/`build_time_index()` 隐式管理，不再提供独立的清空/统计入口。

### Features

- 插件索引 web 页：为 7 个插件集合（io/waveform/hit/peaks/basic_features/tabular/events）区块加入真实波形配图，由 `examples/generate_plugin_set_images.py` 从真实 DAQ 数据经真实插件链（hit → hit_merged → peaklets → peaks）生成。

### Refactoring and performance

- 修正源码分支的发行版本元数据为 `1.5.0`；文档站源码构建优先读取 tracked `pyproject.toml`，避免被旧 editable install 的包元数据污染。
- 将文档、可视化、分析与采集实现从 `waveform_analysis.utils` 迁入按职责划分的规范包，同时保留旧导入路径、对象身份和 monkeypatch 兼容性。
- `PositionReconstructionPlugin` 改为批量消费 `peaklet_channels`，避免逐事件构造 Accessor，并升级到 `0.4.0` 以正确失效缓存 lineage。
- 新增 `waveform_analysis.plugins` 公共 facade，并将 `Context`、插件类、profile 与 plugin set 的用户导入统一到公开入口；旧的 `core`/`utils` 导入路径继续保留兼容性。
- 延迟 `waveform_analysis` core 导出、插件 bundle 与 CLI runtime imports；help/version/参数错误路径不加载业务模块，同时保持 console entry point 与既有 monkeypatch 目标。
- 本次导入拓扑调整不改变任何插件 version、dtype、缓存 lineage 或处理行为。

## v1.5.0

This release focuses on Context 公共 API 收敛、峰重建与 peaklet 管线优化、S1-S2 配对与访问器、可视化 dashboard 交互增强，以及离线文档站点的大规模重构。

### Highlights

- Context 公共 API 平衡收敛（第一阶段）：移除显式配置兼容 API、序列化 tuple 选项、组合 Context 插件域。
- 峰重建：新增 position geometry 与事件重建；position_reconstruction XY 计算向量化，约 10-30x 加速。
- peaklet 管线：peaklet_waveforms 支持多进程与混合 Numba/Python 处理、跨记录检测向量化、波形池复用；hit 与 peaklet 插件拆分包。
- hit_merged 增加 merged_id 字段并修复跨记录波形求和；支持合并多个 merged_index 波形绘制。
- S1-S2 配对：新增 S1S2PairAccessor；修复配对 rank 字段 int16 溢出；插件集重组为 4 层层级并恢复 plugins_events 命名。
- 可视化：dashboard 2D 直方图加入 box-select 回调与 LogNorm、散点降采样、WebGL 错误容错、直方图默认 bins 40→100、特征信息可定制显示。
- 离线文档站点重构：交互式插件 DAG 文档站、导航与架构文档合并（6 页→4 页）、agent 协作工作台。

### Validation

- Release baseline: `v1.3.0`
- Required gates:
  - `python scripts/release_artifact_sync.py --base v1.3.0`
  - `python -m pytest tests/`

## v1.3.0

This release focuses on S1/S2 配对与峰分类重构。

### Highlights

- 新增 S1-S2 配对插件（两层架构）。
- peaklet_s1_s2 重命名为 peak_classification；支持 LABEL_S1_S2、accept_any/reject_any 与可配置 priority_order。
- hit_merged_features 支持增益标定与可配置归一化模式。
- 可视化：修复 sum waveform 计算并新增 PeakChannelAccessor；导出 create_peak_plotter。

### Validation

- Release baseline: `v1.2.0`
- Required gates:
  - `python scripts/release_artifact_sync.py --base v1.2.0`
  - `python -m pytest tests/`

## v1.2.0

This release focuses on Peaklet S1/S2 分类、峰通道 veto masks、DAQ 概览增强与可视化性能优化。

### Highlights

- 新增 PeakletS1S2ClassifierPlugin 与 S1/S2 判别；修正 peaklet_channels 的 peaklet_id → peak_id 字段名。
- Peaks 通道角色 veto masks；hit_merged 新增 time_start/time_end/is_single_record 字段。
- DAQAnalyzer 概览支持缓存状态显示、时间范围过滤与 max_rows 限制。
- Context 报告插件执行耗时。
- 可视化：corner_hist Numba JIT 加速与叠加/透明度/灵活布局；corner plot cut line；hit query 与 peak waveform 工具函数。
- PeakletWaveformPlugin 增加 Numba 加速。

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
