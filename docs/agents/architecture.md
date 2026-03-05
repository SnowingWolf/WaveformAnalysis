# Agent Architecture

## 核心分层
- Context: DAG 协调、配置、lineage、缓存
- Plugins: CPU/streaming/jax(规划中)/legacy
- Storage: memmap + cache 管理
- Execution: executor 与超时控制
- Processing/Data: 数据处理与查询导出

## 数据流（简版）
`raw_files -> st_waveforms -> (filtered_waveforms) -> features/hit -> df -> events`

## 关键判断
- 若输出字段/语义变更：必须升级插件 `version`
- 若仅文案或注释变更：无需升级 `version`
