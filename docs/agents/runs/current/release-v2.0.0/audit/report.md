# WaveformAnalysis v2.0.0 发布前探测报告

日期：2026-09-11。结论：**发布验证未通过；尚未创建或发布 v2.0.0。**

本报告覆盖已核对的 Git 差异、发布契约、文档产物、测试及检查脚本。完整清单用于防止摘要遗漏，不代表每个提交的全部运行路径均已独立验证。

## 1. 范围与执行身份

- 工作源码：`/mnt/data/Run3/WaveformAnalysis`，`develop`，工作区干净。
- 发布工作区：`/mnt/data/Run3/WaveformAnalysis-release`，`release/v2.0.0`，包含未提交的发布准备改动。
- 上一版本：`v1.5.0`，提交 `715c8ce35a93d04f7641b4b149e56b7be6ea01e4`。
- 本次源码 HEAD：`84bd5a85378e4181544ae81111395cb8efc5c0f8`。
- `v1.5.0..HEAD`：126 个提交，完整 SHA/日期/标题见附录及 `commits.tsv`。
- v1.5.0 不是此 HEAD 的直接祖先：反向差集中有旧发布元数据提交。不能把此次范围简单等同于缓存远端分支的 ahead 数。
- 按用户要求启动了 3 个 `gpt-5.6-luna`、`max` Agent：兼容性、文档、发布门禁各一个。**三个均因模型使用额度耗尽，在报告前失败。**没有将其他模型冒充 Luna，也没有获得三方审查通过。
- 后续核对由主 Agent 在本机执行；不替代尚缺的独立 Reviewer 放行。

## 2. 已确认的发布阻断项

### B1. 文档模型固定旧插件版本，真实构建和 11 个测试失败

当前 records 共享实现已升级 `0.14.2 → 0.14.3`。文档验证仍固定旧版本：

| 文件 | 位置/事实 |
| --- | --- |
| `waveform_analysis/documentation/site_model.py` | 2085、2090：要求 records 为 0.14.2 |
| `docs/site-next/lib/site-model.ts` | 748、749：同样要求 0.14.2 |
| `docs/site-next/lib/site-model.test.ts` | 12：预期 0.14.2 |
| `docs/site-next/fixture/site-model.v1.json` | 项目 1.5.0、records 0.14.2 |
| `tests/test_cli_docs_site_publish.py` | 43：旧版本测试夹具 |
| `tests/test_site_model.py` | 发布工作区的 107 行已改为 0.14.3，但验证器尚未同步 |

真实构建在 Python 模型校验阶段终止，尚未执行 npm 命令：

```text
SiteModelError: records plugin must be v0.14.2 with raw_files as its first dependency
```

构建报告：`/tmp/wa-release-v200-docs/runs/release-v200-20260911/report.json`，`status=failed`，`commands=[]`，耗时 3.665 秒。本次没有产出并暂存新的静态站点。

11 个测试均可追溯到这一阻断：9 个直接报 SiteModelError，另 2 个测试对构建报告的预期失败，分别是 `commands[0]` 导致 IndexError、子进程期望构建成功但实际收到上述错误。完整名称见第 4 节，完整栈见 `full-failure-traces.txt`。

最小修复需要同步 Python/TypeScript 校验、测试和生成夹具，再从最终发布源码重建。不能只改一个断言或移除校验来绕过失败。此报告阶段未实施这些源码修复。

### B2. 随包静态文档落后于待发布版本

`waveform_analysis/documentation/site_dist/site-model.v1.json` 仍为项目 **1.5.0**、records **0.14.2**；发布 `pyproject.toml` 已为 **2.0.0**。

`pyproject.toml` 的 package-data 包含 `documentation/site_dist/**/*`。当前直接构建 wheel 会携带旧文档。必须重建并核对模型、站点与 manifest，再检查安装后的 wheel。源 Markdown 的同步检查不能替代这一步。

### B3. 最终产物和独立审查未完成

- v2.0.0 wheel/sdist 的最终构建、独立目录安装、安装后 CLI 与预构建文档导出：未验证。
- 当前版本的前端构建、TypeScript/Vitest、浏览器和窄屏/键盘行为：本轮尚无成功证据。
- 真正对比 v1.5.0 的性能门禁：尚未运行。
- 用户指定的 Luna Max 三方审查：额度阻断，无报告。
- 发布说明“验证”段仍是明确标注的待填写内容，不能直接当成最终 Release 正文。

## 3. 门禁结果与检查脚本的覆盖限制

| 检查 | 实际结果 | 解释 |
| --- | --- | --- |
| `pytest tests/` | FAIL | 1442 passed、11 failed、2 skipped、15 deselected；651.95 秒；38 warnings |
| 真实隔离文档构建 | FAIL | B1 阻断；npm 未执行；无新 site_dist |
| 版本与 CHANGELOG | PASS | 仅证明元数据/变更说明检查通过 |
| auto/agent 生成文档一致性 | PASS | Markdown 生成器同步；不等于静态站构建成功 |
| Doc Sync / Anchor | PASS | 锚点检查错误 0、警告 0；不证明全部文档语义正确 |
| schema + smoke | PASS | 检查 431 文件、39 项 dtype 报告、契约问题 0；解释见第 6 节 |
| 插件影响扫描 | FAIL / 需审查 | 166 个改动插件文件，74 个高风险原始条目；归并见第 5 节 |
| 静态 release 汇总脚本 | 有限制的 PASS | 使用了 `--skip-tests --skip-perf`；两项不能算验证通过 |
| bundle 内测试 | 未单独执行 | `pytest tests/` 没有覆盖第二个 testpaths 根 |
| slow 测试 | 未执行 | 本次有 15 项被 `not slow` 排除 |
| Python 3.10/3.11 矩阵 | 未执行 | 当前运行环境为 Python 3.12；不代表全部支持版本通过 |
| 性能回归 | 未执行 | 未生成有效 v1.5.0 性能对比 |
| 最终安装包验收 | 未执行 | 需要先生成一致的静态站点与最终包 |
| 独立发布 Reviewer | BLOCKED | Luna Max 额度耗尽 |

需要修正对“全量”和“PASS”的理解：

1. `pyproject.toml:105` 的 testpaths 是 `tests` 和 `waveform_analysis/core/plugins/builtin`；发布脚本显式调用 `pytest tests/`，会遗漏 bundle 内的测试。本次发现 **34 个 bundle 测试文件**。文件数不等于测试用例数。
2. `pyproject.toml:111` 默认 `-m 'not slow'`；15 deselected 不是通过。CI 另外配置 slow 层与 Python 版本矩阵，本机结果不能替代远端 CI。
3. `release_artifact_sync.py` 对按参数跳过的测试和性能项仍返回 `ok=true`，导致汇总 `overall_ok=true`。本报告依照每项执行事实判定状态。
4. `performance_regression_check.py:169–198` 在基线 worktree 创建失败时退回当前代码 benchmark，可能形成当前对当前比较。**本次没有执行性能检查，因此这是静态确认的风险路径，不是本轮已发生的假通过。**后续必须核对 baseline 来源和 fallback_note。
5. 当前已安装的旧 `waveform-docs` 启动脚本引用被迁移的 `waveform_analysis.utils.cli_docs`；源码声明的新入口为 `waveform_analysis.documentation.cli:main`。模块方式生成成功不代表新 wheel 的启动脚本已验收。未修改共享 Python 环境。

## 4. 全部 11 个失败测试

以下列表由测试最终汇总核对生成。运行命令及完整输出：`/tmp/wa-release-200-pytest.log`。

1. `tests/test_cli_docs_site_publish.py::test_next_build_requires_explicitly_installed_dependencies`
2. `tests/test_docs_build.py::test_failure_report_and_exit`
3. `tests/test_docs_build.py::test_fresh_process_leaves_entire_workspace_unchanged`
4. `tests/test_site_model.py::test_site_model_v1_uses_real_plugin_and_guide_facts_without_html`
5. `tests/test_site_model.py::test_site_model_rejects_navigation_children_with_unknown_routes`
6. `tests/test_site_model.py::test_site_model_builder_has_no_markdown_html_renderer`
7. `tests/test_site_model.py::test_site_model_preserves_rich_reference_content_and_accessor_classification`
8. `tests/test_site_model.py::test_site_model_meets_pre_next_rich_content_coverage_baseline`
9. `tests/test_site_model.py::test_public_guide_baseline_tracks_source_and_typed_content_independently`
10. `tests/test_site_model.py::test_markdown_blocks_preserve_ordered_lists_links_multiple_code_and_tables`
11. `tests/test_site_model.py::test_route_migration_map_covers_all_routes_without_emitting_aliases`

## 5. 插件影响扫描：74 条原始记录的归并

74 条记录按类名归并为 **37 个类**。其中 36 个类可在前后找到对应实现（RawFileNamesPlugin 从两个旧副本合并为一个），另有新增 EnergyReconstructionPlugin。原始扫描把路径迁移识别为删除/新增，因此不应宣称发现了 74 个实际回归。

下面保留全部类及版本表达式。此表是静态对应关系，不是每个算法均无回归的证明；继承/常量版本需要继续解析，动态 depends_on、配置语义和 lineage 仍须独立核验。

| 类 | v1.5.0 版本表达式 | 当前版本表达式 |
| --- | --- | --- |
| `BasicFeaturesPlugin` | `'4.1.0'` | `'4.1.0'` |
| `CacheAnalysisPlugin` | `'0.1.0'` | `'0.1.0'` |
| `DataFramePlugin` | `'1.7.0'` | `'1.7.0'` |
| `EventPlugin` | `'0.0.1'` | `'0.0.3'` |
| `GroupedEventsPlugin` | `'0.0.1'` | `'0.0.1'` |
| `PairedEventsPlugin` | `'0.0.1'` | `'0.0.1'` |
| `FilteredWaveformsPlugin` | `FILTER_ENGINE_VERSION` | `FILTER_ENGINE_VERSION` |
| `PeakClassificationPlugin` | `'1.2.1'` | `'1.2.1'` |
| `HitFinderPlugin` | `'3.0.0'` | `'3.0.0'` |
| `PositionReconstructionPlugin` | `'0.2.1'` | `'0.4.0'` |
| `RawFileNamesPlugin` | `'0.0.2' / '0.0.2'` | `'0.0.2'` |
| `WavePoolFilteredPlugin` | `FILTER_ENGINE_VERSION` | `FILTER_ENGINE_VERSION` |
| `_RecordsBundlePluginBase` | `'0.14.2'` | `'0.14.3'` |
| `RecordsAsymmetryMaskPlugin` | `'0.2.0'` | `'0.2.0'` |
| `RecordsDetectorMaskPlugin` | `'0.1.0'` | `'0.1.0'` |
| `RecordsVetoMaskPlugin` | `'0.1.0'` | `'0.1.0'` |
| `_RecordsChannelRoleMaskPlugin` | `继承/动态` | `继承/动态` |
| `S1S2PairCandidatesPlugin` | `'0.1.3'` | `'0.2.0'` |
| `S1S2PairSelectionPlugin` | `'0.2.0'` | `'0.3.0'` |
| `WaveformWidthPlugin` | `'3.0.0'` | `'3.0.0'` |
| `WaveformWidthIntegralPlugin` | `'2.7.0'` | `'2.7.0'` |
| `WaveformsPlugin` | `'0.10.0'` | `'0.10.0'` |
| `EnergyReconstructionPlugin` | `不存在` | `'0.1.0'` |
| `ThresholdHitPlugin` | `'1.2.0'` | `'1.2.2'` |
| `HitGroupedPlugin` | `'0.5.0'` | `'0.5.0'` |
| `HitMergeClustersPlugin` | `'1.1.0'` | `'1.1.0'` |
| `HitMergePlugin` | `'2.1.0'` | `'2.1.0'` |
| `HitMergedComponentsPlugin` | `'1.1.0'` | `'1.1.0'` |
| `HitMergedFeaturesPlugin` | `'0.5.1'` | `'1.1.3'` |
| `PeakletChannelsPlugin` | `'1.0.1'` | `'2.0.5'` |
| `PeakletComponentsPlugin` | `'1.4.0'` | `'1.4.0'` |
| `PeakletFeaturesPlugin` | `'4.1.0'` | `'5.0.0'` |
| `PeakletWaveformPoolPlugin` | `'2.0.0'` | `'3.0.0'` |
| `PeakletWaveformPlugin` | `'1.4.0'` | `'2.1.1'` |
| `PeakletPlugin` | `'1.2.0'` | `'1.2.0'` |
| `PeaksPlugin` | `'4.0.1'` | `'5.0.0'` |
| `SignalPeaksStreamPlugin` | `'1.2.0'` | `'1.2.0'` |

完整路径、类行号、基类、provides、depends_on、output_dtype 表达式见 `plugin-relocation-map.json`；原始条目见 `impact.log`。

## 6. dtype 扫描：39 项报告不等于 39 项字段破坏

按 dtype 名称重新对应旧路径和新路径：**19 个已有 dtype 的字段/类型映射相等，新增 1 个 ENERGY_RECONSTRUCTION_DTYPE**。这解释了 19×2+1=39 项原始新增/删除报告。

已有 19 项：

- `BASIC_FEATURES_DTYPE`
- `EVENT_DTYPE`
- `PEAK_CLASSIFICATION_DTYPE`
- `HIT_DTYPE`
- `POSITION_RECONSTRUCTION_DTYPE`
- `S1_S2_PAIR_CANDIDATES_DTYPE`
- `WAVEFORM_WIDTH_DTYPE`
- `WAVEFORM_WIDTH_INTEGRAL_DTYPE`
- `THRESHOLD_HIT_DTYPE`
- `HIT_MERGED_COMPONENTS_DTYPE`
- `HIT_MERGED_DTYPE`
- `HIT_MERGE_CLUSTERS_DTYPE`
- `HIT_MERGED_FEATURES_DTYPE`
- `PEAKLET_CHANNELS_DTYPE`
- `PEAKLET_COMPONENTS_DTYPE`
- `PEAKLET_DTYPE`
- `PEAKLET_FEATURES_DTYPE`
- `PEAKLET_WAVEFORMS_DTYPE`
- `PEAKS_DTYPE`

证据为 `schema.json`、`schema-by-name.json`、`dtype-declarations.json`。比较的是提取出的字段与类型映射，不能据此独立证明运行时 offsets/alignment/itemsize、所有字段排列或物理含义相同。尤其 events 时间单位和 fall_time 定义确实发生了语义变化，见下一节。

schema smoke 成功：raw_files 2、st_waveforms 24、hit 0、df 24、events 12。这个小型 smoke 不覆盖全部插件和真实生产数据。

## 7. v2.0.0 必须写明的迁移事项

| 变化 | 影响与迁移 |
| --- | --- |
| 删除 `Context.clear_time_index()`、`get_time_index_stats()` | 移除旧调用，依据当前 `time_range()` / `build_time_index()` API 管理索引；二者并非旧统计 API 的同义替换 |
| `events.s1_time` / `s2_time` 修正为 ps | 当前直接继承配对数据中的皮秒值；下游不能继续叠加旧错误缩放，重查单位换算和历史数据比较 |
| `peaklet_features` / `peaks` 的 `fall_time` | 变为累计面积分位数 `(t90-t50)/1000` ns，旧定义是与 time_peak 比较；对应版本 5.0.0，重查筛选阈值、图表和训练模型 |
| 包结构与导入 | 推荐根包 Context、`waveform_analysis.plugins` 公开插件入口及各 domain 包；仍有兼容 facade，不应宣称全部 utils 路径都已删除 |
| CLI 安装入口 | 新包应生成指向 `waveform_analysis.documentation.cli:main` 的 waveform-docs；不要复用未经验证的旧启动脚本 |
| 缓存与进程 | 多个插件版本及 lineage 逻辑变化；按依赖链判定缓存有效性，升级后重启已有 Notebook/长驻进程，不保证全部旧缓存原样重用 |
| energy_reconstruction | 仅结构占位，能量值 NaN 且含 `FLAG_ENERGY_NOT_IMPLEMENTED`，不是已完成的物理重建 |

代码证据：`events/plugin.py:205–206`，`peaklet_features/plugin.py:118`，`energy_reconstruction/plugin.py:43,174–196`，完整源文件均位于发布工作区 `waveform_analysis/core/plugins/builtin/` 下。

## 8. 126 个提交的用户可见内容归类

以下为主题摘要；逐提交完整记录在附录，避免只看摘要遗漏较小改动。

1. **文档内容**：真实插件概述、workflow 叙述和流程图；dtype 物理单位；丰富的插件/API/CLI 参考；缓存架构、bundle 指南；文档归并去重和旧过程文档退出学习入口。
2. **文档站**：迁移至 Next.js 静态站；typed site model；插件分类、搜索索引去重；lineage 颜色、正交连线、缩放线宽、密度、点击/悬停预览；侧栏换行、窄屏切换、CLI 导航、键盘交互；静态分发优化。
3. **文档构建与打包**：隔离构建工作区、模型与清单验证、随包预构建站点、无需 Node 的预构建复制路径。上述是代码中引入的能力，当前 v2.0.0 构建仍受 B1/B2 阻断。
4. **插件组织**：shared 库、registry、hit/peaklet/records/masks/events 等迁移独立 bundle；RawFileNamesPlugin 重复实现合并；manifest、SKILL、requirements 和 package-data 适配。
5. **公开导入及领域拆分**：documentation、analysis、acquisition、visualization 从 utils 迁移；accessor、reader、discovery、渲染实现拆分；utils 收敛为兼容 facade；对象身份和导入顺序修复；公开 plugins facade；根包/插件包/CLI 延迟加载。
6. **Context 与缓存**：重算时级联失效下游 lineage；缓存键稳定性修复；复用层间线程池并缩短数据锁；移除时间索引管理公开 API；历史缓存复用日志说明。
7. **hit / peaklet 热路径**：Numba canonical 波形路径和 merged-feature fallback；merged-feature 通道热点优化；peaklet 通道聚合/CSR；降低流水线内存、冷路径及 records-backed 波形准备成本。
8. **配对与位置**：S1-S2 orphan 生成向量化及过滤后的 score 边界修复；位置重建批量通道访问；保留重复 position layout 语义。
9. **查询与绘图**：PeakChannelAccessor 增加 hit/merged-hit 查询；去重峰通道波形；统一二维位置 dashboard；自适应二维分层采样；corner histogram symlog；S2 候选波形；PDF 图形导出。
10. **字段语义和新增产物**：events 时间单位修复，fall_time 分位数定义，energy_reconstruction 结构占位，详见迁移说明。
11. **Agent 与质量流程**：工作流 v6/task.yaml；managed Executor/Reviewer MVP；PR 提交逐项说明检查；质量门禁、共享测试 helper、导入契约、Python CI/3.10 兼容修复、Ruff baseline/Black、性能抽样稳定化；graph 工作流移至独立仓库。
12. **V1725 合并后回收**：已提交修复 `84bd5a8`，详见下一节。

不能误记为本次首次新增：v1.5.0 已有 S1-S2 pairing/accessor、position reconstruction、初代离线文档站、dashboard 2D/框选、Numba 与多进程流水线、pyarrow 支持。新增摘要应描述本区间的具体增量。

## 9. V1725 修复的准确边界

- 确认最终计数、文件尺寸、波形 offset/length 边界与总长度，检查目录归属和源/最终路径不重叠。
- 成功合并后关闭中间映射，删除本次原始分片以及排序中间 `records_merged_*.dat`，清理空目录。
- 保留最终 records 与 wave_pool，继续由 RecordsBundleRef 持有和按已有 cleanup 释放。
- 只在拥有输入的 V1725 构建链调用回收；通用 `_merge_records_part_refs()` 不删除外部调用者输入。
- 此前 58 个相关定向测试及独立代码审查通过；本次大范围测试额外发现了关联文档版本 pin 未同步的问题。
- **未解决/未承诺**：合并时峰值占用限制、TMPDIR 配置、历史 `/tmp/v1725_parts_*` 清理、进程强杀的全部残留、最终文件自动生命周期重设计、生产大规模数据回放。

## 10. 后续修复和放行顺序

1. 修订发布任务 scope，加入受影响的 Python/TypeScript 模型校验、夹具和测试路径；保留当前失败证据。
2. 同步模型契约和测试数据，从当前源码生成 fixture，修复版本不一致。
3. 先复测失败项；用新的 run ID 执行真实隔离文档构建，检查最终静态站、manifest、版本并纳入发布 diff。
4. 执行受影响文档测试及 frontend 检查，再按仓库 testpaths 覆盖测试；补齐 slow、bundle 与所需 Python 矩阵证据。
5. 跑真实旧基线性能检查，明确拒绝 current-vs-current fallback；对 37 类插件映射完成实际契约/lineage 审查。
6. 构建 wheel/sdist，在独立安装环境中检查入口、包数据和 node-free 文档导出；完成发布说明验证段及最终文档一致性检查。
7. 获得独立 Reviewer 通过后 scoped 提交、创建 v2.0.0 标签及 GitHub Release。用户指定 Luna Max 的审查当前受额度阻断，不能静默换模型后声称满足。

## 11. 当前提交与发布状态

- 已提交 V1725 修复：`84bd5a85378e4181544ae81111395cb8efc5c0f8`。
- **未提交：v2.0.0 发布准备仍有测试/构建失败及独立审查缺口，不能作为完成版本提交交付。**
- 主工作区干净；发布工作区保留 CHANGELOG、版本、发布说明、任务记录/索引及测试断言的准备改动。
- 未创建 v2.0.0 tag、未上传 v2.0.0 发布资产、未发布 GitHub Release、未上传 PyPI。

## 附录 A：全部提交

| SHA | 日期 | 提交标题 |
| --- | --- | --- |
| 1ba275c2b7dc978b7f3cc7e013ef52e388051acb | 2026-08-03 | test(contracts): 清理引用不存在特性/夹具不匹配的失效测试 |
| bfab8ebcae56ffe8e5aa31bf8e234cefda4eaa7b | 2026-08-03 | refactor(tests): 合并重复测试 helper 到 tests/utils.py 共享工具 |
| 81fd9849c317493023c161df10abcb381e7bfd37 | 2026-08-03 | test(cache): 新增共享 build_cache_context helper |
| c1ffc039a81308faec76b9998a2a724bdb6bb7c5 | 2026-08-03 | docs(plugins): add rich agent_doc narratives to peaks/records/filtering core plugins |
| bfa3bbe5fdff6d6e4370df74ca5fdcf5391455ea | 2026-08-03 | feat(docs): auto-derive plugin overview/workflow and tiered doc badges |
| 7c7306ddc46d46fbfa72f47d784450fcc11ff6fa | 2026-08-03 | docs: fill real physical units for plugin output dtype fields in dtype_field_notes.yaml |
| 07431cd75f6b49aa1aba4f383d28f833f977fa91 | 2026-08-03 | fix(events): keep s1_time/s2_time in ps; fill real field units |
| 25eff896de523a95522a46b785659c669be0d2e9 | 2026-08-03 | docs(hit_merged): refine workflow_steps with bold titles |
| 4bc234155ae83ba9205b3a4d8e866b578d297b04 | 2026-08-03 | feat(docs): plugin internal-process mermaid flowchart |
| 4fe52e5fbfeb007fc30225ed277278f20d54eeb5 | 2026-08-03 | style(docs): naturalize hit_merged flowchart wording + polish mermaid display |
| abd126e1d81581f75c1d4d6d5882ad41b5eb8851 | 2026-08-03 | fix(docs): make lineage wire stroke width scale with zoom |
| cb3623919c3d4c598b1d8c4f6d290f145252c10b | 2026-08-04 | chore: enforce PR commit descriptions |
| 04001a87f373431899419f6ed328b036634824d8 | 2026-08-04 | style(docs): unify local lineage graph colors to site green theme |
| 5113edc0f18db528182b29d06c2e249101445382 | 2026-08-04 | fix(docs): use orthogonal polyline edges in local lineage graphs |
| 2fc4d7bd11be558c513ff7708589bda494680040 | 2026-08-04 | fix(docs): quote hit_merged flowchart decision node label |
| 92f3365ff106e3bc7966f9bafe76749575172810 | 2026-08-04 | refactor(docs): dedupe plugin search index entries |
| a0b1fa58b5c71fffda992d936a32594ec244548a | 2026-08-04 | feat: add PDF figure export utility |
| 253d1c6a700cc970bc10d1e3fa78e63b054f706c | 2026-08-04 | feat: add energy_reconstruction plugin (structure placeholder) |
| 98c5df71e8b4bb186b5331fad5dea91c0177c3b8 | 2026-08-04 | fix(execution): cascade-invalidate downstream lineage caches on recompute |
| bf6b0eeaeca75554febbba3fd6dceaa8bb6de41f | 2026-08-04 | feat(docs): add plugin kind labels and click/hover previews to lineage graph |
| b9fcfb2e118cf03db28999dcd9b105e66706698a | 2026-08-04 | docs(plugins): regenerate auto plugin reference pages |
| 036b6c671d1c6bfd81e6142a2b884fab934c6cc4 | 2026-08-04 | perf(context): reuse thread pool across layers and shorten _data_lock |
| abeb321bcbe0ce07345c74f0075b68544c8fd43d | 2026-08-04 | docs(architecture): add plugin cache architecture document |
| 6eed9c87883fec2ffe7e71bda464dcd1c58906af | 2026-08-04 | docs(site): add plugin cache architecture page to HTML site |
| f2ca9e725b2f87388ec9a89f0a45fff251363f39 | 2026-08-04 | refactor(plugins): 插件 skill 化重构 Phase 0-3 — shared 库、registry、hit/peaklet 家族迁移 bundle |
| 427c9c973f69caefe93aaa79f45a5df0f9e35a92 | 2026-08-04 | refactor(plugins): Phase 4a hit 家族迁移 bundle（hit/hit_threshold/hit_grouped/hit_merged_features） |
| 7cdd3721b25ea8a23cd3624e786dde392e9b63d1 | 2026-08-04 | refactor(plugins): Phase 4b records/masks/events 迁移 bundle |
| 79591b00273805bd8feb4c2cd59b451d4a043ada | 2026-08-04 | refactor(plugins): Phase 4c 单插件模块迁移 bundle + RawFileNamesPlugin 双副本合并 |
| 35422c8031b12fc8e07e2e5d0af116ee870cf2a6 | 2026-08-04 | Merge branch 'worktree-agent-ae99a144' into develop |
| 859c543186bd08ed60e80a456c2f36598d42a460 | 2026-08-04 | Merge branch 'worktree-agent-acc93a09' into develop |
| 3e27dfc5c1e860b3b85bc62fb6925240f98ee4f4 | 2026-08-04 | fix(plugins): test_records_veto_mask 引用 4a 迁移后的 test_hit_threshold 模块 |
| a91c191d0208a76ecc79c0fca4599f7d800cd650 | 2026-08-04 | docs(plugins): 重新生成插件文档（per-plugin bundle module 路径）+ CI/Makefile/package-data 适配 |
| 2c239ebd0f5802ffbbd5aa4c9ec6abe065b6d37c | 2026-08-04 | docs(preview): 更新插件重构 HTML 预览反映完成状态 |
| 958409c64d11aa5c65c352b30a2dede4cdb72398 | 2026-08-05 | refactor(context): 移除时间域索引管理公开 API 并清理引擎死代码 |
| 04cc0e2537175a5e31c2b184cd74142528f8b07a | 2026-08-05 | docs: add plugin bundle guide to site |
| 27620b9728e77dc8ca7ea1967c413bdbf7253483 | 2026-08-05 | docs: refine documentation unification preview |
| 41475d7c3b3103f8532f280bcbdaca1ab58c0d7e | 2026-08-06 | docs: 内容迁移执行——正式文档归并到对应栏目、过程性总结删除、插件文档去重 |
| cd96f7b6aa5f659449f4bbd24805fee7c6949edd | 2026-08-13 | fix(peaks): fall_time 改为 50%-90% 累计面积分位数定义 |
| e013baeba30a19839f0ef6c3403a96c0cba0d15a | 2026-08-17 | fix: deduplicate peak channel waveforms |
| 87cc00966a746f097864235a04be385dcfa29d17 | 2026-08-17 | perf: route peaklet waveforms through numba canonical path |
| 804cd5c89ba6f947f642e7fcbaf862642769cc2c | 2026-08-18 | docs: document peaklet waveform numba routing |
| a19eb5091e214c8396f0f617c6ad5df39942aa2d | 2026-08-18 | perf: route hit merged fallback through numba |
| 7bc757744d7d0e1fca1597557975b627ba6dd5ca | 2026-08-18 | perf: optimize merged feature channel hot paths |
| 8809771355914e9517da708298a5d435956e6641 | 2026-08-18 | perf: streamline peaklet channel aggregation |
| 66159be6c8c51a3ca2897206493d21ce157910db | 2026-08-18 | perf: optimize peaklet channel CSR path |
| b6f4cfc84ae5fe6912ffa15a103336bef856404e | 2026-08-19 | perf: bound peaklet pipeline memory |
| 2394893a5599e6b6ba7f28e56a48b9e8277f585f | 2026-08-19 | perf: optimize records-backed peaklet cold paths |
| efb643b8b3d275ef220654987a16b228a3b7a66a | 2026-08-19 | docs: complete site documentation migration |
| 0bc56668c0d2ebf81fc391287fb0097cd94b49f7 | 2026-08-19 | perf: finalize quality gates |
| 08b0f06bc0b99e3f023c2b22a3ebe53a7e4272f1 | 2026-08-19 | docs: strengthen documentation quality gates |
| b7a24b243145c813467b7f0f1f2526dd0b64bb6a | 2026-08-26 | chore(migration): move graph workflow to standalone repository |
| b19df8b3e2a1931856280b2e7b9349f7bbf04f23 | 2026-08-26 | refactor: unify 2d position dashboard |
| 91aba88f32514939d65b301a2178eeb94fa33544 | 2026-08-26 | docs: improve plugin reference quality |
| dd1665679f32aef2a092e931ace06e265071dafe | 2026-08-26 | feat: expose hit queries through peak accessor |
| 797eb33a0311f803d2c9eee1ec1be158ab6fc603 | 2026-08-26 | docs: update peak channel API guides |
| 132bf8c22ed36fe0d1b4f29371aae083f1661931 | 2026-08-26 | docs: remove redundant peak plotting guide |
| 714bb2ec4883a01e39b4b27891b69ee34a057ecc | 2026-08-26 | docs: fold peak classification config into plugin reference |
| 9ea47430db490b3181fce1ba1a252eea0b271eb6 | 2026-08-26 | docs: remove redundant hit threshold guide |
| a58c6944c927b84fff669464b0f68000384e370a | 2026-08-26 | docs: consolidate plugin and accessor references |
| d75907baaf402b8e1a521a623c16e6d28f9859d1 | 2026-08-26 | docs: remove obsolete CSV header guide |
| 8a616630ef6f942de76dabc06e3552dbffe0df42 | 2026-08-26 | docs: consolidate context execution architecture |
| 3b182a6555b75255310fddab49f0bcf236d470de | 2026-08-26 | docs: integrate dashboard and plugin references |
| 35d832a35e873dce4fffa406284b35138ffbea4a | 2026-08-27 | fix: stabilize lineage cache keys |
| 0bde2c70062908fdfd31498ff01d128837d00ff0 | 2026-08-27 | refactor(plugins): vectorize S1-S2 orphan generation |
| 59470d032c4f07704105f3e2636bf9e20e280703 | 2026-08-27 | fix(plugins): preserve pair score bounds when filtering orphans |
| 568d642a767d36097473f3fe1ee50f46997eda59 | 2026-08-27 | docs(agents): record orphan hotpath rework evidence |
| 41ef3059ce6e2106cd5f2b6e7066c97560781eb7 | 2026-08-27 | docs(agents): approve orphan hotpath review |
| 1ac75bebc948b40e2437950e1fb3568cbd4a40ac | 2026-08-27 | feat: add adaptive 2d stratified sampling |
| 572d9ebfaece2793fd1bde5704fd02affbfa3cbd | 2026-08-27 | docs: explain historical cache reuse logs |
| 220361a92429bec6462cc3b3bc51efb804e93025 | 2026-08-27 | feat: add S2 candidate waveform plotting |
| a2b0943c86b883ba4828aa78fb175e081ca72421 | 2026-08-28 | refactor: optimize peaklet waveform preparation |
| 2b5f8643927d21bbebd0ce4ef83b0d1b16f6ca88 | 2026-08-28 | fix: improve documentation sidebar wrapping |
| 99d757dc6ee48c44490f932581a5f3a729106675 | 2026-08-28 | feat: add symlog support to corner hist |
| 2015f532319b9357f0e503b63e3430ca35521cf6 | 2026-08-28 | fix: repair Python CI failures |
| c8ff4a6c4c839daa3a753bf4a4c3bb2e9599dfae | 2026-08-28 | fix: pin CI Ruff baseline |
| c61d4256da31e1f63fccd1951f83ec1c6422f687 | 2026-08-28 | style: satisfy repository Black check |
| dae0171e7ffaca7c3c46290323478bc1cadb5d76 | 2026-08-28 | fix: restore Python 3.10 test compatibility |
| f289db1a90eaa55eb8c40115f5aee4e24db9dcf2 | 2026-08-30 | refactor: move documentation tooling out of utils |
| 68f89af0dc75771f68aa035de6a464b88477b374 | 2026-08-30 | refactor: split plugin documentation generator |
| 8ad76f9f8e2261fc9d3858615a53e280545dc6e9 | 2026-08-30 | refactor: split documentation site generator |
| 97ebbf3fb30a02e3446da233da1ad848b8d4f5b8 | 2026-08-31 | test: freeze remaining utils compatibility contracts |
| fb5bb8243d4d51ad8ea46e87d97c140624d9d93c | 2026-08-31 | refactor: move visualization tooling out of utils |
| 261e977bbd36b6dc7fe8f8a194d0828917749123 | 2026-08-31 | refactor: split visualization implementations |
| 9f92b73f86fd9f12487acbc897ea4b9a42f3f3bc | 2026-08-31 | refactor: move analysis helpers out of utils |
| 6f90f8ab56a96205639bdcab13478ca7aeae315b | 2026-08-31 | refactor: split analysis accessors |
| e6d8f18d00998b9c7c4658e2bc10ddf53b378fbf | 2026-08-31 | perf: batch position reconstruction channel access |
| f8dc910bbc3e8f72a1aa558bfe8d3d57a71b95cc | 2026-08-31 | refactor: move acquisition tooling out of utils |
| a656a3fe2cd385fe73ccb93169cfe1e7b06803d8 | 2026-08-31 | refactor: split acquisition readers and services |
| 8267fc251a15022711d6845f349f9a8fdef668f0 | 2026-08-31 | refactor: reduce utils to compatibility facade |
| 7790e3a561cbf0cd330eff2a5ea0984bb27cd8dd | 2026-08-31 | feat: add agent workflow v6 |
| f0de482d0eb37f369785b4c2a4b55a959ff955ae | 2026-08-31 | fix: preserve utils visualization facade identity |
| 5cba0e71d7ebd524812bec0d804076fdd7e5c2a5 | 2026-08-31 | refactor: complete visualization implementation split |
| b6396fcdc2de18b7cf05f23ac8636f22d939c82a | 2026-08-31 | refactor: complete analysis accessor split |
| 851458ede1c09d633147ce7626c9eb25446e0f34 | 2026-08-31 | refactor: complete acquisition reader and discovery split |
| cb8875f62ddfaf44fb16b64f61e65e244004abf0 | 2026-08-31 | fix: preserve duplicate position layout semantics |
| a73d2e6d7521c448916227d233fe1aa8138c60ee | 2026-08-31 | docs: sync plugin source fingerprints |
| 5d7dca1debce576aefe299dbc3cb061059b34cbb | 2026-08-31 | docs: document canonical utils subsystem ownership |
| 44bff79d63b15b56f76a8e55b058ad51fef813f1 | 2026-08-31 | fix: make split entry points import-order safe |
| 023d5a1b31484ffd2b06060d0fc2126771276ace | 2026-08-31 | test: freeze import topology contracts |
| accff61533c1e101c1667dec8c51987f18a61050 | 2026-08-31 | feat: add public plugins facade |
| b38f3074571a8a97329c5bad42394cfbac9e7877 | 2026-08-31 | refactor: lazy-load core package exports |
| 11622959af224d1f42084480169efd3a4e010c23 | 2026-08-31 | refactor: lazy-load plugin package exports |
| 33a9770ba73c6a578baed8834be3bc06030211a4 | 2026-08-31 | refactor: defer cli runtime imports |
| 13209e5fc6d75cbde2d9b760f4dda3a86bd4630a | 2026-08-31 | docs: standardize public import paths |
| f6cabebc35b5cacdde1b83c1e83324726cb95757 | 2026-08-31 | docs: sync agent task indexes |
| 72d4da60cc1b11ab13aedee6251edf86eb73ea83 | 2026-08-31 | test: isolate lazy export contracts |
| d58b64852ea8230a1eee6cf1785361143a474a1d | 2026-08-31 | docs: resync agent task indexes after rework |
| 3a88b032b83d19f24df4dd19bb2a0c9a82091b0e | 2026-08-31 | docs: record import topology changes |
| 59438b87c23d48493cbfd6fe71ab3fb91452bc98 | 2026-08-31 | test: stabilize performance regression sampling |
| 68e731969e9cb594f3311b44883f873dc0138dbe | 2026-09-01 | feat: migrate documentation site to Next.js |
| bef3c6ad438ba6b3262adfb7b89d443453dc987e | 2026-09-01 | chore: record Next.js documentation migration handoff |
| f8ed4533eefc1b6c7d4545b4947d84372291f052 | 2026-09-01 | fix: compact lineage dtype display |
| 2fe4319151fe34ab33b0e7bb1f88dedeb9617cc0 | 2026-09-01 | chore: record lineage density handoff |
| 44094a8e32fcf5ff235a03ed1ad7e0d9ace48d2f | 2026-09-01 | fix: restore rich documentation references |
| e5944fa30eae19240c491eaeaaec5415f420c45e | 2026-09-01 | chore: record rich docs recovery handoff |
| 7a9514f90de6da3a541ff429112e3f754a379ac3 | 2026-09-02 | refactor: optimize static documentation delivery |
| c2dde9b4c23bb9ea970555ee169a35e9a6a5e98c | 2026-09-02 | chore: record documentation optimization handoff |
| 1b1a0b8237c5a9c95580c789f77ee973fe6ad73d | 2026-09-02 | fix: restore lineage sidebar toggle on narrow screens |
| 55e914ecff40bfdf6d789a09333f1bdd26bc3d1b | 2026-09-02 | fix: expose CLI pages in docs navigation |
| eb1c6bb7772c476ebd24dad2d2c0233f1640c81c | 2026-09-04 | fix: synchronize 1.5.0 release metadata and docs |
| e939550222a871e74aa7e49df1b2afd6b73b72ac | 2026-09-07 | fix: preserve documentation structure and keyboard behavior |
| e2c6c5b97d73763fc141b33f90f2453ace77c2be | 2026-09-08 | feat: add managed Executor Reviewer workflow MVP |
| 235da1c2ea9d0871e6b26bb87464eecba6f5a3e0 | 2026-09-08 | chore: managed task d449f269ed32 attempt 1 |
| 8b39b9acc06b4bd4da80d22e1afc8e927ab91267 | 2026-09-08 | chore: managed task d449f269ed32 attempt 2 |
| 0e9a415820ec40abbd558343186bdd1cba9831f3 | 2026-09-08 | chore: managed task d449f269ed32 attempt 3 |
| 84bd5a85378e4181544ae81111395cb8efc5c0f8 | 2026-09-11 | fix: reclaim V1725 intermediate shards after validated merge |

## 附录 B：完整证据索引

- `snapshot.json`：基线、工作区和 Agent 失败情况。
- `commits.tsv`：126 个完整提交 SHA、日期与标题。
- `changed-files.tsv`：基线至源码 HEAD 的完整路径变更记录（不含尚未提交的发布准备文件）。
- `failed-tests.json`、`full-failure-traces.txt`：全部失败项和错误栈。
- `/tmp/wa-release-200-pytest.log`：完整 tests/ 测试输出、覆盖率及警告。
- `/tmp/wa-release-v200-docs/runs/release-v200-20260911/report.json`：真实构建失败报告。
- `impact.log`、`plugin-relocation-map.json`：74 条插件影响记录与 37 类对应。
- `schema.json`、`schema.log`、`schema-by-name.json`、`dtype-declarations.json`：schema 与 smoke 证据。
- `static-release-check.json`、`static-release-check.log`：明确跳过测试/性能的静态发布汇总。

未执行和受阻项目已列出；本报告不提供“绝对无遗漏/零回归”保证。
