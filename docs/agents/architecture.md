# Agent Architecture

## 核心分层
- Context: DAG 协调、配置、lineage、缓存
- Plugins: CPU/streaming/jax(规划中)/legacy
- Storage: memmap + cache 管理
- Execution: executor 与超时控制
- Processing/Data: 数据处理与查询导出

## 数据流（简版）
`raw_files -> st_waveforms -> (filtered_waveforms) -> features/hit -> df -> events`

`raw_files -> records + wave_pool -> (wave_pool_filtered) -> record-backed features/hit`

## Records 相关约定
- `records` 与 `wave_pool` 是正式插件产物
- `wave_pool_filtered` 是基于 `records + wave_pool` 构建的正式滤波波形池，主要服务
  `wave_source=records` 的计算插件
- `RecordsBundle(records, wave_pool)` 仅作为内部共享构建缓存
- 非 `v1725` 适配器下，`records + wave_pool` 也直接从 `raw_files` 增量构建，不再先完整物化
  `st_waveforms`
- 需要 records-backed 波形访问时，统一使用 `records_view(ctx, run_id)`
- `records_view(...)` 可通过 `wave_pool_name=` 在原始 `wave_pool` 与
  `wave_pool_filtered` 之间切换
- `records_view(...)` 不做内部 bundle fallback，调用方必须确保正式 `wave_pool` 已注册并可产出
- 当插件配置 `wave_source="records"` 且 `use_filtered=True` 时，应自动读取
  `wave_pool_filtered`，而不是尝试切到 `filtered_waveforms`

## 关键判断
- 若输出字段/语义变更：必须升级插件 `version`
- 若仅文案或注释变更：无需升级 `version`
