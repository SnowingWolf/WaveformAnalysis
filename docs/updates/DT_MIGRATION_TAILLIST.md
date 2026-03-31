# dt 迁移尾单

**日期**: 2026-03-30
**状态**: 迁移主路径已完成，以下为收口项

## 本轮已清理

- 示例代码中的旧键注释改为主键 `dt`：
  - `examples/records_pipeline_example.py`
  - `examples/records_view.py`
- 配置文档中的主术语改为 `dt`：
  - `docs/features/context/CONFIGURATION.md`
- 迁移说明中的时间换算表述改为 `dt`：
  - `docs/updates/V1725_EXISTING_CHAIN_INTEGRATION.md`

## 兼容保留项（当前不建议直接删改）

这些位置仍出现旧术语，但背后要么是兼容层、要么是尚未迁移的独立 API、要么是测试刻意覆盖，不应只改文本：

- preview 工具 API 仍使用参数名 `sampling_interval_ns`：
  - `waveform_analysis/utils/preview.py`
  - `docs/features/utils/waveform_preview.md`
  - `examples/preview_quickstart.md`
- 配置兼容层与适配器元数据仍保留 `dt_ns` / `events_dt_ns` / `records_dt_ns` 映射：
  - `waveform_analysis/core/config/resolver.py`
  - `waveform_analysis/core/config/adapter_info.py`
- 兼容测试仍需保留旧键覆盖：
  - `tests/plugins/test_threshold_hit_plugin.py`
  - `tests/plugins/test_signal_peaks_stream_plugin.py`
  - `waveform_analysis/core/config/tests/test_config.py`

## 待后续代码迁移的文档/示例

这些内容当前仍引用旧术语，但更适合在对应代码 API 一并迁移时处理：

- 教程 notebook 中的 `dt_ns` 示例与输出：
  - `tutorial.ipynb`
  - `tutorial_advanced.ipynb`
- preview 文档中的 `sampling_interval_ns` 参数说明，应在 preview API 改为 `dt` 后统一重生成/重写。

## 建议的下一步顺序

1. 若要统一用户面 API，优先迁移 `waveform_analysis/utils/preview.py` 的 `sampling_interval_ns -> dt`。
2. 完成 preview API 迁移后，同步更新：
   - `docs/features/utils/waveform_preview.md`
   - `examples/preview_quickstart.md`
3. 最后清理 notebook 教程中的历史输出与配置键，避免中途再次失真。
