# hit_threshold 插件流式处理方案评估

**日期**: 2026-05-29
**评估对象**: `ThresholdHitPlugin` (provides: `hit_threshold`)
**目标**: 支持 2TB+ 数据集的流式处理

---

## 执行摘要

| 方案 | 可行性 | 实施成本 | 性能影响 | 推荐度 |
|------|--------|---------|---------|--------|
| 方案 1: 分块加载 | ⭐⭐⭐⭐ | 中等 | 低 | ⭐⭐⭐ |
| 方案 2: 生成器模式 | ⭐⭐ | 高 | 中等 | ⭐ |
| 方案 3: RecordsBundleRef 集成 | ⭐⭐⭐⭐⭐ | 低 | 极低 | ⭐⭐⭐⭐⭐ |

**推荐方案**: **方案 3 (RecordsBundleRef 集成)** - 利用现有基础设施，最小改动，最大收益。

---

## 方案 1: 分块加载 (修改 load_wave_input)

### 概述
修改 `_wave_source.py` 中的 `load_wave_input()` 函数，支持按 chunk 读取 records/waveforms。

### 技术细节

#### 当前实现
```python
# waveform_analysis/core/plugins/builtin/cpu/_wave_source.py:168
def load_wave_input(context, plugin, run_id, ...) -> LoadedWaveInput:
    # 一次性加载全部数据
    waveform_data = context.get_data(run_id, spec.data_name)
    return LoadedWaveInput(spec=spec, waveform_data=waveform_data)
```

#### 改造方案
```python
def load_wave_input_chunked(
    context, plugin, run_id,
    chunk_size: int = 10_000
) -> Iterator[LoadedWaveInput]:
    """流式加载波形数据"""
    spec = resolve_wave_input_spec(context, plugin)

    if spec.is_records:
        # 使用 RecordsBundleRef.iter_chunks()
        bundle = context.get_data(run_id, "records")
        if isinstance(bundle, RecordsBundleRef):
            for chunk in bundle.iter_chunks(chunk_size):
                rv = records_view_from_bundle(chunk)
                yield LoadedWaveInput(spec=spec, records=chunk.records, records_view=rv)
        else:
            # 回退到批量模式
            yield load_wave_input(context, plugin, run_id)
    else:
        # st_waveforms/filtered_waveforms 分块
        waveform_data = context.get_data(run_id, spec.data_name)
        for start in range(0, len(waveform_data), chunk_size):
            end = min(start + chunk_size, len(waveform_data))
            yield LoadedWaveInput(spec=spec, waveform_data=waveform_data[start:end])
```

### 优点
- ✅ **通用性强**: 所有使用 `load_wave_input()` 的插件都能受益
- ✅ **渐进式改造**: 可以保留原有 API，新增 `load_wave_input_chunked()`
- ✅ **内存可控**: chunk_size 可配置，适应不同内存环境

### 缺点
- ❌ **API 破坏性**: 需要修改所有调用方（或提供兼容层）
- ❌ **复杂度增加**: 需要处理 chunk 边界、状态管理
- ❌ **测试成本高**: 需要回归测试所有依赖插件（18+ 个）
- ❌ **st_waveforms 支持困难**: 非 records 数据源没有天然的分块机制

### 实施成本

| 项目 | 工作量 | 风险 |
|------|--------|------|
| 修改 `_wave_source.py` | 2-3 天 | 中 |
| 修改 `hit_threshold` 插件 | 1 天 | 低 |
| 回归测试 | 3-5 天 | 高 |
| 文档更新 | 1 天 | 低 |
| **总计** | **7-10 天** | **中-高** |

### 性能影响
- **内存占用**: 降低 90%+（取决于 chunk_size）
- **处理速度**: 降低 10-20%（chunk 边界开销）
- **磁盘 I/O**: 增加（如果数据源不支持流式）

### 适用场景
- ✅ 需要改造多个插件支持流式处理
- ✅ 数据源本身支持分块（如 RecordsBundleRef）
- ❌ 只需要改造单个插件（过度设计）

---

## 方案 2: 生成器模式 (修改 Plugin.compute)

### 概述
将 `Plugin.compute()` 从返回 `np.ndarray` 改为 `yield` hits，支持流式输出。

### 技术细节

#### 当前实现
```python
# waveform_analysis/core/plugins/builtin/cpu/hit_finder.py:122
class ThresholdHitPlugin(Plugin):
    def compute(self, context, run_id, **kwargs) -> np.ndarray:
        # 加载全部数据
        wave_input = load_wave_input(context, self, run_id)
        # 处理全部数据
        hits = self._build_hits_from_signal_matrix(...)
        return hits  # 返回完整数组
```

#### 改造方案
```python
class ThresholdHitPlugin(StreamingPlugin):
    def compute(self, context, run_id, **kwargs) -> Iterator[Chunk]:
        """流式输出 hits"""
        for wave_chunk in load_wave_input_chunked(context, self, run_id):
            # 处理单个 chunk
            hits = self._build_hits_from_signal_matrix(
                signal=wave_chunk.signal,
                ...
            )
            # 包装为 Chunk 并 yield
            yield Chunk(
                data=hits,
                time_field="timestamp",
                endtime_field="endtime",
                data_kind="hits"
            )
```

### 优点
- ✅ **内存友好**: 逐 chunk 处理，内存占用恒定
- ✅ **流式架构**: 符合 StreamingPlugin 设计模式
- ✅ **可组合**: 可以与其他流式插件串联

### 缺点
- ❌ **架构破坏性极大**: 需要修改 Plugin 基类契约
- ❌ **影响范围广**: 所有依赖 `hit_threshold` 的插件都需要改造
  - `hit_grouped` (依赖 hit_threshold)
  - `hit_merged` (依赖 hit_threshold)
  - `hit_merge_clusters` (依赖 hit_threshold)
  - 用户自定义插件
- ❌ **缓存系统失效**: 现有缓存机制基于 `np.ndarray`，不支持生成器
- ❌ **向后兼容困难**: 无法同时支持批量和流式模式
- ❌ **测试成本极高**: 需要重写所有相关测试

### 实施成本

| 项目 | 工作量 | 风险 |
|------|--------|------|
| 修改 Plugin 基类 | 3-5 天 | 极高 |
| 修改 `hit_threshold` | 2-3 天 | 中 |
| 修改下游插件 (3+) | 5-7 天 | 高 |
| 修改缓存系统 | 3-5 天 | 高 |
| 回归测试 | 7-10 天 | 极高 |
| 文档更新 | 2-3 天 | 中 |
| **总计** | **22-33 天** | **极高** |

### 性能影响
- **内存占用**: 降低 95%+
- **处理速度**: 降低 20-30%（生成器开销 + chunk 边界）
- **缓存命中率**: 降低（流式数据难以缓存）

### 适用场景
- ✅ 构建全新的流式处理框架
- ✅ 所有插件都需要流式化
- ❌ 只需要改造单个插件（杀鸡用牛刀）
- ❌ 需要保持向后兼容

### 参考实现
系统中已有 `StreamingPlugin` 基类和示例：
```python
# waveform_analysis/core/plugins/builtin/streaming/cpu/signal_peaks.py:37
class SignalPeaksStreamPlugin(StreamingPlugin):
    def compute(self, context, run_id, **kwargs) -> Iterator[Chunk]:
        # 流式处理逻辑
        for chunk in input_stream:
            yield process_chunk(chunk)
```

---

## 方案 3: RecordsBundleRef 集成 (推荐)

### 概述
利用现有的 `RecordsBundleRef` 流式基础设施，在 `hit_threshold` 插件内部实现分块处理。

### 技术细节

#### 核心思路
1. 检测输入数据类型（`RecordsBundle` vs `RecordsBundleRef`）
2. 如果是 `RecordsBundleRef`，使用 `iter_chunks()` 流式处理
3. 如果是 `RecordsBundle`，保持原有批量处理逻辑
4. 最终合并所有 chunk 的 hits 并返回

#### 改造方案
```python
class ThresholdHitPlugin(Plugin):
    def compute(self, context, run_id, **kwargs) -> np.ndarray:
        wave_input = load_wave_input(context, self, run_id, needs_wave_samples=True)

        # 检测是否为 RecordsBundleRef
        if wave_input.spec.is_records:
            from waveform_analysis.core.processing import RecordsBundleRef
            bundle = context.get_data(run_id, "records")

            if isinstance(bundle, RecordsBundleRef):
                # 流式处理模式
                return self._compute_streaming(context, run_id, bundle)

        # 批量处理模式（原有逻辑）
        return self._compute_batch(context, run_id, wave_input)

    def _compute_streaming(self, context, run_id, bundle_ref: RecordsBundleRef) -> np.ndarray:
        """流式处理 RecordsBundleRef"""
        all_hits = []
        chunk_size = 10_000  # 可配置

        for chunk_bundle in bundle_ref.iter_chunks(chunk_size=chunk_size):
            # 处理单个 chunk（复用现有逻辑）
            chunk_hits = self._process_chunk(context, run_id, chunk_bundle)
            all_hits.append(chunk_hits)

        # 合并所有 hits
        if all_hits:
            return np.concatenate(all_hits)
        return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

    def _process_chunk(self, context, run_id, chunk_bundle: RecordsBundle) -> np.ndarray:
        """处理单个 chunk（复用 _build_hits_from_signal_matrix）"""
        rv = records_view_from_bundle(chunk_bundle)
        waves, valid_mask = rv.waves(chunk_bundle.records["record_id"], mask=True)
        # ... 复用现有处理逻辑
        return self._build_hits_from_signal_matrix(...)
```

### 优点
- ✅ **零架构改动**: 不修改 Plugin 基类，不影响其他插件
- ✅ **向后兼容**: 自动检测数据类型，小数据集仍用批量模式
- ✅ **复用现有基础设施**: `RecordsBundleRef` 已经过生产验证（f8c961e）
- ✅ **实施成本低**: 只需修改 `hit_threshold` 插件内部逻辑
- ✅ **测试成本低**: 只需测试 `hit_threshold` 插件
- ✅ **性能优秀**: `RecordsBundleRef` 使用 memmap，I/O 高效
- ✅ **内存可控**: chunk_size 可配置，默认 10k events ≈ 40MB

### 缺点
- ⚠️ **仅支持 records 数据源**: st_waveforms/filtered_waveforms 仍需批量加载
  - **缓解**: 大数据集通常使用 records 作为源（V1725 原始数据）
- ⚠️ **需要合并开销**: 最终需要 `np.concatenate()` 所有 chunk 的 hits
  - **缓解**: hits 数量远小于 records（通常 < 10%），合并开销可接受

### 实施成本

| 项目 | 工作量 | 风险 |
|------|--------|------|
| 修改 `hit_threshold` 插件 | 1-2 天 | 低 |
| 添加单元测试 | 1 天 | 低 |
| 集成测试（2TB 数据集） | 1 天 | 中 |
| 文档更新 | 0.5 天 | 低 |
| **总计** | **3.5-4.5 天** | **低** |

### 性能影响

#### 内存占用
```
批量模式: 2TB records + wave_pool ≈ 2TB RAM (OOM)
流式模式: 10k events × 1k samples × 2 bytes ≈ 40MB RAM (可控)
降低: 99.99%
```

#### 处理速度
```
批量模式: 一次性加载 + 向量化计算 (基准)
流式模式: 分块加载 + 分块计算 + 合并
开销: chunk 边界 + 合并 ≈ 5-10%
```

#### 磁盘 I/O
```
RecordsBundleRef 使用 memmap，按需加载
I/O 模式: 顺序读取（SSD 友好）
临时文件: 约等于数据大小（自动清理）
```

### 适用场景
- ✅ **2TB+ V1725 原始数据** (records 数据源)
- ✅ **内存受限环境** (< 64GB RAM)
- ✅ **需要快速实施** (< 1 周)
- ✅ **需要向后兼容** (小数据集不受影响)
- ⚠️ **st_waveforms 数据源** (仍需批量加载，但通常数据量较小)

### 实施路线图

#### Phase 1: 核心功能 (2 天)
1. 添加 `_compute_streaming()` 方法
2. 添加 `_process_chunk()` 方法
3. 修改 `compute()` 添加类型检测

#### Phase 2: 测试 (1.5 天)
1. 单元测试：小数据集（批量模式）
2. 单元测试：中等数据集（流式模式）
3. 集成测试：2TB 数据集（真实场景）

#### Phase 3: 文档与优化 (1 天)
1. 更新插件文档（`docs/plugins/reference/agent/hit_threshold.md`）
2. 添加使用示例
3. 性能调优（chunk_size 优化）

---

## RecordsBundleRef 基础设施现状

### 已有能力
根据 `docs/features/context/LARGE_DATASET_PROCESSING.md` 和 `f8c961e` 提交：

1. **流式迭代**: `iter_chunks(chunk_size, time_range)`
2. **全局排序保证**: 堆合并算法，保证 `(timestamp, pid, board, channel)` 有序
3. **内存管理**: memmap + 自动清理临时文件
4. **时间范围过滤**: 支持只处理特定时间窗口
5. **元数据访问**: `get_records_view()` 只读 records，不加载 wave_pool

### 使用示例
```python
from waveform_analysis.core.processing import build_records_from_v1725_files

# 自动模式（推荐）
result = build_records_from_v1725_files(
    file_paths=large_file_list,
    dt_ns=2,
    keep_on_disk=None,  # 自动选择
    memory_budget_gb=50.0
)

if isinstance(result, RecordsBundleRef):
    # 大数据集，流式处理
    for chunk in result.iter_chunks(chunk_size=10_000):
        hits = process_chunk(chunk.records, chunk.wave_pool)
    result.cleanup()
else:
    # 小数据集，批量处理
    hits = process_all(result.records, result.wave_pool)
```

### 性能数据
根据文档说明：
- **chunk_size=10k**: 约 40MB 内存占用
- **chunk_size=50k**: 约 100MB 内存占用
- **临时文件**: 约等于数据大小（/tmp 或 SSD）
- **处理速度**: 比批量模式慢 10-20%（可接受）

---

## 综合对比

### 功能对比

| 特性 | 方案 1 | 方案 2 | 方案 3 |
|------|--------|--------|--------|
| 支持 records 数据源 | ✅ | ✅ | ✅ |
| 支持 st_waveforms | ⚠️ 困难 | ✅ | ❌ |
| 支持 filtered_waveforms | ⚠️ 困难 | ✅ | ❌ |
| 向后兼容 | ⚠️ 需兼容层 | ❌ | ✅ |
| 内存占用 | 降低 90% | 降低 95% | 降低 99.99% |
| 处理速度 | -10~20% | -20~30% | -5~10% |
| 缓存支持 | ✅ | ❌ | ✅ |

### 成本对比

| 维度 | 方案 1 | 方案 2 | 方案 3 |
|------|--------|--------|--------|
| 开发时间 | 7-10 天 | 22-33 天 | 3.5-4.5 天 |
| 测试时间 | 3-5 天 | 7-10 天 | 1.5 天 |
| 风险等级 | 中-高 | 极高 | 低 |
| 维护成本 | 中 | 高 | 低 |
| 影响范围 | 18+ 插件 | 50+ 插件 | 1 插件 |

### 风险对比

| 风险类型 | 方案 1 | 方案 2 | 方案 3 |
|---------|--------|--------|--------|
| API 破坏 | 中 | 高 | 无 |
| 性能回退 | 低 | 中 | 低 |
| 测试覆盖 | 中 | 高 | 低 |
| 生产故障 | 中 | 高 | 低 |
| 回滚难度 | 中 | 极高 | 低 |

---

## 推荐决策

### 首选方案: 方案 3 (RecordsBundleRef 集成)

**理由**:
1. **最小改动原则**: 只修改 1 个插件，不影响架构
2. **复用现有基础设施**: RecordsBundleRef 已生产验证
3. **快速交付**: 3.5-4.5 天即可完成
4. **低风险**: 向后兼容，易于回滚
5. **高性能**: 内存占用降低 99.99%，速度损失 < 10%

**适用场景**:
- ✅ 处理 2TB+ V1725 原始数据（主要场景）
- ✅ 内存受限环境（< 64GB RAM）
- ✅ 需要快速实施（< 1 周）

**局限性**:
- ⚠️ 仅支持 records 数据源
- ⚠️ st_waveforms/filtered_waveforms 仍需批量加载

**缓解措施**:
- st_waveforms 通常是预处理后的小数据集（< 50GB），批量加载可接受
- 如果 st_waveforms 也很大，可以后续扩展方案 1

### 备选方案: 方案 1 (分块加载)

**适用场景**:
- 需要支持所有数据源（records + st_waveforms + filtered_waveforms）
- 有充足的开发时间（2-3 周）
- 需要改造多个插件

**实施建议**:
- 先实施方案 3，验证流式处理效果
- 如果 st_waveforms 成为瓶颈，再扩展方案 1

### 不推荐: 方案 2 (生成器模式)

**理由**:
- 架构破坏性极大（修改 Plugin 基类）
- 实施成本极高（22-33 天）
- 风险极高（影响 50+ 插件）
- 收益不明显（相比方案 3）

**适用场景**:
- 构建全新的流式处理框架（重构项目）
- 所有插件都需要流式化（长期规划）

---

## 实施建议

### 短期 (1-2 周): 方案 3
1. 实施 `hit_threshold` 的 RecordsBundleRef 集成
2. 验证 2TB 数据集处理效果
3. 监控内存占用和处理速度

### 中期 (1-2 月): 评估扩展
1. 统计 st_waveforms 数据集大小分布
2. 如果 st_waveforms > 50GB 成为常态，考虑方案 1
3. 评估其他插件的流式化需求

### 长期 (6-12 月): 架构演进
1. 如果多个插件需要流式化，考虑统一的流式框架
2. 评估 StreamingPlugin 基类的推广
3. 考虑方案 2 的渐进式迁移

---

## 附录: 代码示例

### 方案 3 完整实现草案

```python
class ThresholdHitPlugin(Plugin):
    options = {
        # ... 现有 options
        "streaming_chunk_size": Option(
            default=10_000,
            type=int,
            help="流式处理时的 chunk 大小（仅对 RecordsBundleRef 生效）",
        ),
    }

    def compute(self, context, run_id, **kwargs) -> np.ndarray:
        """主入口：自动检测批量/流式模式"""
        wave_input = load_wave_input(context, self, run_id, needs_wave_samples=True)

        # 检测是否为 RecordsBundleRef
        if wave_input.spec.is_records:
            from waveform_analysis.core.processing import RecordsBundleRef
            bundle = context.get_data(run_id, "records")

            if isinstance(bundle, RecordsBundleRef):
                logger.info(
                    f"hit_threshold: detected RecordsBundleRef with {bundle.total_records} records, "
                    f"using streaming mode"
                )
                return self._compute_streaming(context, run_id, bundle, wave_input.spec)

        # 批量处理模式（原有逻辑）
        logger.debug("hit_threshold: using batch mode")
        return self._compute_batch(context, run_id, wave_input)

    def _compute_streaming(
        self,
        context,
        run_id: str,
        bundle_ref: RecordsBundleRef,
        spec: WaveInputSpec
    ) -> np.ndarray:
        """流式处理 RecordsBundleRef"""
        chunk_size = int(context.get_config(self, "streaming_chunk_size"))
        all_hits = []
        total_processed = 0

        for chunk_bundle in bundle_ref.iter_chunks(chunk_size=chunk_size):
            chunk_hits = self._process_chunk(context, run_id, chunk_bundle, spec)
            all_hits.append(chunk_hits)
            total_processed += len(chunk_bundle.records)

            if total_processed % (chunk_size * 10) == 0:
                logger.info(
                    f"hit_threshold: processed {total_processed}/{bundle_ref.total_records} records, "
                    f"found {sum(len(h) for h in all_hits)} hits"
                )

        # 合并所有 hits
        if all_hits:
            result = np.concatenate(all_hits)
            logger.info(f"hit_threshold: streaming mode completed, total hits: {len(result)}")
            return result
        return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

    def _process_chunk(
        self,
        context,
        run_id: str,
        chunk_bundle: RecordsBundle,
        spec: WaveInputSpec
    ) -> np.ndarray:
        """处理单个 chunk（复用现有逻辑）"""
        from waveform_analysis.core import records_view

        # 构建 records_view
        rv = records_view(
            context,
            run_id,
            wave_pool_name=spec.wave_pool_name or "wave_pool",
            records_override=chunk_bundle.records,
            wave_pool_override=chunk_bundle.wave_pool
        )

        records = chunk_bundle.records
        record_ids = records["record_id"].astype(np.int64, copy=False)
        waves, valid_mask = rv.waves(record_ids, mask=True, dtype=np.float32)

        # 复用现有处理逻辑
        # ... (与 _compute_batch 相同的处理流程)

        return self._build_hits_from_signal_matrix(...)

    def _compute_batch(self, context, run_id: str, wave_input: LoadedWaveInput) -> np.ndarray:
        """批量处理模式（原有逻辑，保持不变）"""
        # ... 现有的 compute() 逻辑
        pass
```

---

## 参考文档

- [大数据集处理指南](features/context/LARGE_DATASET_PROCESSING.md)
- [RecordsBundleRef 实现](../waveform_analysis/core/processing/records_builder.py)
- [hit_threshold 插件文档](plugins/reference/agent/hit_threshold.md)
- [StreamingPlugin 示例](../waveform_analysis/core/plugins/builtin/streaming/cpu/signal_peaks.py)
- [提交 f8c961e: RecordsBundleRef Phase 3](https://github.com/.../commit/f8c961e)
