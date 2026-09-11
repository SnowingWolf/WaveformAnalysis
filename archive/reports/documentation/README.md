# 文档与算法预览历史归档

这里保留曾经用于设计讨论、重构规划或阶段性算法说明的 HTML 预览。它们仅供历史追溯，不是当前行为或 API 契约的真源；不进入 `docs/site-guides.yaml` 的公开文档白名单，也不进入 Next 站点的导航或搜索索引。

当前行为、插件契约、文档导航和发布站点均以活动源码、插件 manifest、`docs/` Markdown、Next site model 及随包 `site_dist` 为准。这些归档文件也不属于 wheel/sdist 的发布内容。

| 原路径 | 归档路径 | 历史用途 | 当前正式替代入口 |
|---|---|---|---|
| `docs_unification_preview.html` | `archive/reports/documentation/docs_unification_preview.html` | 文档导航统一、`site-guides` schema 和内容迁移的设计与实施进度预览 | [`docs/site-guides.yaml`](../../../docs/site-guides.yaml)、[`docs/site-next/`](../../../docs/site-next/)、[`waveform_analysis/documentation/site_guides.py`](../../../waveform_analysis/documentation/site_guides.py) |
| `plugin_restructure_preview.html` | `archive/reports/documentation/plugin_restructure_preview.html` | 插件 per-plugin bundle、shared 算法属主和兼容 shim 的重构目录预览 | [`waveform_analysis/core/plugins/builtin/`](../../../waveform_analysis/core/plugins/builtin/)、[`docs/plugins/reference/agent/`](../../../docs/plugins/reference/agent/)、[`docs/site-next/`](../../../docs/site-next/) |
| `s1_s2_pairing_visualization.html` | `archive/reports/documentation/s1_s2_pairing_visualization.html` | S1-S2 配对候选生成、贪心选择和诊断场景的早期可视化说明 | [`s1_s2_pair_candidates.md`](../../../docs/plugins/reference/agent/s1_s2_pair_candidates.md)、[`s1_s2_pairs.md`](../../../docs/plugins/reference/agent/s1_s2_pairs.md)、[`s1_s2.md`](../../../docs/plugins/reference/agent/s1_s2.md)、[`docs/site-next/`](../../../docs/site-next/) |

归档正文保留原始讨论上下文；若当前实现或公开文档发生变化，不应直接从这些 HTML 推断结论。
