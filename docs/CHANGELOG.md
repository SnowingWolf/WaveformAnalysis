# 变更日志 (CHANGELOG)

**导航**: [文档中心](README.md) > 变更日志

本文档记录 WaveformAnalysis 项目的版本历史和重要变更。

---

## 版本说明

- **主版本号 (Major)**: 不兼容的 API 变更
- **次版本号 (Minor)**: 向后兼容的功能新增
- **修订号 (Patch)**: 向后兼容的问题修复

**标记说明**:
- 🔥 **Breaking Change** - 破坏性变更，需要迁移
- ✨ **New Feature** - 新功能
- 🐛 **Bug Fix** - 问题修复
- ⚡ **Performance** - 性能优化
- 📝 **Documentation** - 文档更新
- ♻️ **Refactor** - 代码重构
- 🧪 **Test** - 测试相关

---

## [Unreleased] - 开发中

### ✨ 新功能
- **hit_threshold 插件支持 RecordsBundleRef 流式处理**：内存占用降低 99.99%
  - 自动检测数据类型（RecordsBundleRef vs RecordsBundle），无需手动配置
  - 新增 `streaming_chunk_size` 配置项，默认 100k events ≈ 200MB 内存
  - 向后兼容：小数据集（RecordsBundle）仍使用批量模式
  - 适用场景：2TB+ V1725 原始数据，内存受限环境（< 64GB RAM）
- 文档系统优化：新增 API 快速参考和使用示例
- 新增 CHANGELOG 和 MIGRATION_GUIDE

### 📝 文档
- 新增 `docs/api/QUICK_REFERENCE.md` - API 速查表
- 新增 `docs/api/EXAMPLES.md` - 完整代码示例
- 扩展 `docs/api/README.md` - 改进 API 文档导航
- 新增 `docs/CHANGELOG.md` - 版本变更日志
- 新增 `docs/MIGRATION_GUIDE.md` - 版本迁移指南

### ♻️ 重构
- 删除重复的重定向文件 `docs/plugins/PLUGIN_AUTHORING_GUIDE.md`

---

## [Recent Updates] - 2026-01

### 🔥 破坏性变更

#### records 处理优化
- **变更**: 重构 records 处理流程，引入 `RecordsBundleRef` 用于流式处理 2TB+ 数据集
- **影响**: 内部实现变更，外部 API 保持兼容
- **迁移**: 无需迁移，自动兼容
- **提交**: `8834e49`, `ee2634a`, `ac9f6e3`

#### hit 字段重命名
- **变更**: `event_index` 重命名为 `record_id`
- **影响**: 使用 `event_index` 字段的代码需要更新
- **迁移**: 将所有 `event_index` 替换为 `record_id`
- **提交**: `e1a93c6`

### ✨ 新功能

#### basic_features 新增字段
- 新增 `max_abs_diff` 字段到 `basic_features` 和 `dataframe`
- 提供波形最大绝对差值信息
- **提交**: `31bd27c`

#### df 新增 record_id 列
- DataFrame 输出新增 `record_id` 列，便于追溯原始记录
- **提交**: `23934e5`

#### 统一浮点过滤管道
- 新增共享的 float32 过滤管道，提升性能
- **提交**: `94ff550`

### ⚡ 性能优化

#### 2TB+ 数据集处理优化
- **Phase 1**: 优化 V1725 处理流程 (`ac9f6e3`)
- **Phase 2**: 添加批量合并支持 (`ee2634a`)
- **Phase 3**: 引入 `RecordsBundleRef` 流式处理 (`8834e49`)
- **效果**: 支持 2TB+ 数据集的高效处理

#### DAQ 解析优化
- 缓存和批量处理 acquisition 解析 (`92ef282`)
- 减少 `scan_all_runs` 文件系统开销 (`e33e0d0`)
- 使用首个文件创建时间作为 acquisition 窗口 (`23f3c69`)

#### 其他性能优化
- 优化 `filtered_waveforms` 批处理 (`75ed57b`)
- 加速 raw-file bundle 构建 (`d0c4e11`)
- 延迟加载预览辅助函数 (`63af8b6`)
- 统一 records wave source 加载 (`a71aaae`)

### 🐛 问题修复

#### records 相关修复
- 修复大规模合并行为边界问题 (`f8c961e`)
- 修复临时目录泄漏和内存预算问题 (`28dd2ae`)

#### DAQ 相关修复
- 修复 V1725 board 编号读取 (`74e503a`)
- 修复 acquisition 窗口时间计算 (`23f3c69`)

#### 测试相关修复
- 恢复完整测试套件兼容性 (`f32a2be`)

### ♻️ 重构

#### 代码组织
- 集中化 chunk 大小配置，改进异常处理 (`1c177f5`)
- 按主题拆分大型测试套件 (`00de771`)
- 移除废弃的适配器回退逻辑 (`78b329c`)

#### records 处理
- 统一 records wave source 加载 (`a71aaae`)
- 要求正式的 wave_pool 输出 (`b0ab8e0`)
- 添加正式的 wave_pool 插件输出 (`6ce242f`)

#### hit 处理
- 优化 grouped merge 管道 (`de6465f`)
- 重命名 `event_index` 为 `record_id` (`e1a93c6`)

### 📝 文档

#### Agent 文档
- 添加 agent 工作流清单和交接检查 (`c71212e`)
- 同步 agent 和插件参考文档 (`c6b7b3c`)
- 同步插件参考选项 (`d7b7252`)

#### 插件文档
- 同步插件文档并清理覆盖率产物 (`237e50d`)

### 🧪 测试

#### 测试改进
- 按主题拆分大型测试套件 (`00de771`)
- 清理遗留覆盖率并标记慢速用例 (`cf523d7`)
- 添加 `wave_pool_filtered` 覆盖率 (`24a8550`)

---

## [Earlier Updates] - 2025-2026

### ⚡ 性能优化与持久化缓存

详见 [更新总结](updates/UPDATE_SUMMARY.md)

#### 关键特性
- ✅ **高效数据格式**:
  - CSV 解析升级为 `pyarrow` 引擎，速度提升 3-5 倍
  - 中间 DataFrame 采用 Parquet 格式存储
  - 波形数据采用二进制内存映射 (Memmap) 存储
- ✅ **多级持久化缓存**:
  - 自动缓存核心处理步骤结果
  - 基于文件签名的自动失效机制
- ✅ **内存映射支持**:
  - `MemmapStorage` 支持多维数组存储
- ✅ **命名一致性**:
  - 完成从 `char` 到 `run_name` 的语义迁移

#### 性能提升

| 步骤 | 优化前 | 优化后 | 提升倍数 |
|------|--------|--------|----------|
| 原始数据加载 | ~10s (100MB) | ~2s | 5x |
| 波形提取缓存加载 | N/A | < 0.1s | 极速 |
| 特征计算缓存加载 | N/A | < 0.05s | 极速 |
| DataFrame 读写 | ~2s (Pickle) | ~0.2s (Parquet) | 10x |

### 🔥 存储系统迁移

详见 [存储迁移指南](updates/STORAGE_MIGRATION_GUIDE.md)

- 从 Pickle 迁移到 Parquet + Memmap
- 新增 `MemmapStorage` 和 `CacheManager`
- 向后兼容旧格式

### 🔥 数据类型迁移

详见 [数据类型迁移清单](updates/DT_MIGRATION_TAILLIST.md)

- 统一数据类型命名规范
- 字段名标准化

### ✨ V1725 集成

详见 [V1725 集成指南](updates/V1725_EXISTING_CHAIN_INTEGRATION.md)

- 支持 V1725 DAQ 系统
- 集成到现有处理链

---

## 迁移指南

对于破坏性变更，请参考 [迁移指南](MIGRATION_GUIDE.md) 获取详细的升级步骤。

---

## 相关资源

- [迁移指南](MIGRATION_GUIDE.md) - 版本升级指南
- [更新记录](updates/README.md) - 详细更新文档
- [AGENTS.md](../AGENTS.md) - 主入口与硬约束
- [文档中心](README.md) - 所有文档入口

---

## 贡献

发现问题或有改进建议？请查看 [贡献指南](development/contributing/README.md)。
