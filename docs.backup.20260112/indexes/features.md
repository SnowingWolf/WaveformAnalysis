# ✨ 功能特性索引

**导航**: [文档中心](../README.md) > 功能特性

WaveformAnalysis 的所有功能特性详细说明和使用指南。

---

## 🎯 功能分类导航

### 📊 数据处理功能

#### 流式处理 (Streaming)
**文档**: [STREAMING_GUIDE.md](../STREAMING_GUIDE.md)

**功能亮点**:
- ✅ 内存高效的大数据处理
- ✅ 支持超大数据集（TB 级）
- ✅ 自动分块和并行处理
- ✅ 实时数据流处理

**使用场景**:
- 数据集太大无法一次性加载到内存
- 需要实时处理持续产生的数据
- 要求最小的内存占用

**快速开始**:
```python
from waveform_analysis.core.streaming import get_streaming_context

# 创建流式处理上下文
stream_ctx = get_streaming_context(ctx, run_id="run_001", chunk_size=50000)

# 流式处理数据
for chunk in stream_ctx.get_stream("st_waveforms_stream"):
    process_chunk(chunk)
```

**相关文档**: [MEMORY_OPTIMIZATION.md](../MEMORY_OPTIMIZATION.md)

---

#### 缓存机制 (Caching)
**文档**: [CACHE.md](../CACHE.md)

**功能亮点**:
- ✅ 自动缓存计算结果
- ✅ 血缘追踪和智能失效
- ✅ 支持内存和磁盘缓存
- ✅ 零配置开箱即用

**使用场景**:
- 重复运行相同的分析流程
- 避免重复计算耗时操作
- 快速恢复中断的处理

**快速开始**:
```python
# 缓存自动生效
ds = WaveformDataset(run_name="my_run", cache_dir="./cache")
ds.load_raw_data()  # 第一次：从文件加载
ds.load_raw_data()  # 第二次：从缓存加载（快速）

# 清除缓存
ds.clear_cache()
```

**相关文档**: [ARCHITECTURE.md](../ARCHITECTURE.md)

---

#### CSV 头部处理
**文档**: [CSV_HEADER_HANDLING.md](../CSV_HEADER_HANDLING.md)

**功能亮点**:
- ✅ 自动检测 CSV 头部格式
- ✅ 支持多种头部类型
- ✅ 智能列名映射
- ✅ 容错处理

**使用场景**:
- 处理不同格式的 CSV 文件
- 自动适配列名变化
- 批量导入异构数据

---

### ⚡ 性能优化功能

#### 内存优化 (Memory Optimization)
**文档**: [MEMORY_OPTIMIZATION.md](../MEMORY_OPTIMIZATION.md) ⭐

**功能亮点**:
- ✅ 节省 70-80% 内存使用
- ✅ 加速 10 倍处理速度
- ✅ 保留所有统计特征
- ✅ 完全后向兼容

**核心参数**:
```python
dataset = WaveformDataset(
    run_name="...",
    load_waveforms=False  # ← 关键参数：跳过波形加载
)
```

**适用场景**:
- ✅ 大数据集处理（内存不足）
- ✅ 只需要统计特征，不需要原始波形
- ✅ 批量处理多个运行
- ✅ 服务器端自动化任务

**效果对比**:
| 指标 | load_waveforms=True | load_waveforms=False | 改进 |
|------|---------------------|----------------------|------|
| 内存使用 | ~800 MB | ~150 MB | **↓ 81%** |
| 处理时间 | ~45 秒 | ~4 秒 | **↑ 11x** |
| 特征精度 | 完整 | 完整 | **相同** |

**详细指南**: [HOW_TO_SKIP_WAVEFORMS.md](../HOW_TO_SKIP_WAVEFORMS.md)

---

#### 性能优化最佳实践
**文档**: [PERFORMANCE_OPTIMIZATION.md](../PERFORMANCE_OPTIMIZATION.md)

**功能亮点**:
- ✅ 并行处理技巧
- ✅ I/O 优化策略
- ✅ 算法优化建议
- ✅ 性能分析工具

**主要技术**:
- Numba JIT 编译加速
- 多进程并行处理
- NumPy 向量化优化
- 智能缓存策略

**快速开始**:
```python
# 启用 Numba 加速
ds.group_events(use_numba=True)

# 使用多进程
from waveform_analysis.core.execution import get_executor
with get_executor('cpu_intensive', max_workers=4) as executor:
    results = executor.map(process_func, data_chunks)
```

**性能对比**: [OPTIMIZATION_SUMMARY.md](../OPTIMIZATION_SUMMARY.md)

---

### 🚀 高级功能

#### 执行器管理 (Executor Management)
**文档**: [EXECUTOR_MANAGER_GUIDE.md](../EXECUTOR_MANAGER_GUIDE.md)

**功能亮点**:
- ✅ 统一的并行执行接口
- ✅ 自动负载均衡
- ✅ 资源池复用
- ✅ 超时和取消支持

**预定义配置**:
- `io_intensive`: I/O 密集型任务
- `cpu_intensive`: CPU 密集型任务
- `large_data`: 大数据处理
- `small_data`: 小数据快速处理

**快速开始**:
```python
from waveform_analysis.core.execution import get_executor

# 使用预定义配置
with get_executor('io_intensive') as executor:
    results = executor.map(load_file, file_list)

# 自定义配置
with get_executor('custom', max_workers=8, timeout=300) as executor:
    results = executor.map(process_data, data_list)
```

**框架总结**: [EXECUTOR_FRAMEWORK_SUMMARY.md](../EXECUTOR_FRAMEWORK_SUMMARY.md)

---

#### 依赖分析 (Dependency Analysis)
**文档**: [DEPENDENCY_ANALYSIS_GUIDE.md](../DEPENDENCY_ANALYSIS_GUIDE.md)

**功能亮点**:
- ✅ 自动构建依赖图（DAG）
- ✅ 智能执行顺序优化
- ✅ 并行执行机会识别
- ✅ 依赖冲突检测

**使用场景**:
- 理解数据处理流程
- 优化执行顺序
- 调试插件依赖问题

**可视化血缘图**:
```python
# 生成血缘可视化
ctx.plot_lineage("df_paired", kind="plotly", verbose=2)

# LabVIEW 风格（静态）
ctx.plot_lineage("df_paired", kind="labview", interactive=True)
```

---

#### 进度追踪 (Progress Tracking)
**文档**: [PROGRESS_TRACKING_GUIDE.md](../PROGRESS_TRACKING_GUIDE.md)

**功能亮点**:
- ✅ 实时进度显示
- ✅ 多级嵌套进度条
- ✅ Jupyter Notebook 支持
- ✅ 可定制的进度回调

**快速开始**:
```python
# 自动进度条（推荐）
ctx.set_config({'enable_progress': True})

# 手动进度追踪
from waveform_analysis.core.foundation.progress import ProgressTracker

with ProgressTracker(total=100, desc="Processing") as tracker:
    for i in range(100):
        process_item(i)
        tracker.update(1)
```

---

#### Numba 多进程优化
**文档**: [NUMBA_MULTIPROCESS_GUIDE.md](../NUMBA_MULTIPROCESS_GUIDE.md)

**功能亮点**:
- ✅ Numba JIT 加速
- ✅ 多进程并行化
- ✅ 自动向量化
- ✅ 性能剖析工具

**适用场景**:
- CPU 密集型计算
- 大规模循环操作
- 数值计算优化

**示例**:
```python
# 启用 Numba 加速的分组
ds.group_events(use_numba=True, time_window_ns=100)
```

---

## 🔍 按使用场景查找

### 场景 1: 我的内存不够用
**解决方案**:
1. [MEMORY_OPTIMIZATION.md](../MEMORY_OPTIMIZATION.md) - 使用 `load_waveforms=False`
2. [STREAMING_GUIDE.md](../STREAMING_GUIDE.md) - 流式处理大数据
3. [CACHE.md](../CACHE.md) - 使用磁盘缓存

### 场景 2: 处理速度太慢
**解决方案**:
1. [PERFORMANCE_OPTIMIZATION.md](../PERFORMANCE_OPTIMIZATION.md) - 性能优化技巧
2. [EXECUTOR_MANAGER_GUIDE.md](../EXECUTOR_MANAGER_GUIDE.md) - 并行处理
3. [NUMBA_MULTIPROCESS_GUIDE.md](../NUMBA_MULTIPROCESS_GUIDE.md) - JIT 加速

### 场景 3: 需要处理超大数据集
**解决方案**:
1. [STREAMING_GUIDE.md](../STREAMING_GUIDE.md) - 流式处理
2. [MEMORY_OPTIMIZATION.md](../MEMORY_OPTIMIZATION.md) - 内存优化
3. [EXECUTOR_MANAGER_GUIDE.md](../EXECUTOR_MANAGER_GUIDE.md) - 并行执行

### 场景 4: 想要可视化数据流程
**解决方案**:
1. [DEPENDENCY_ANALYSIS_GUIDE.md](../DEPENDENCY_ANALYSIS_GUIDE.md) - 血缘图可视化
2. [ARCHITECTURE.md](../ARCHITECTURE.md) - 架构图

### 场景 5: 需要实时处理反馈
**解决方案**:
1. [PROGRESS_TRACKING_GUIDE.md](../PROGRESS_TRACKING_GUIDE.md) - 进度追踪
2. [STREAMING_GUIDE.md](../STREAMING_GUIDE.md) - 流式处理

---

## 📊 功能对比表

| 功能 | 内存占用 | 处理速度 | 复杂度 | 适用场景 |
|------|----------|----------|--------|----------|
| 内存优化 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | 大数据集 |
| 流式处理 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | 超大数据 |
| 缓存机制 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | 重复分析 |
| 并行处理 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | CPU 密集 |
| Numba加速 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 数值计算 |

评分：⭐ 低/简单 → ⭐⭐⭐⭐⭐ 高/复杂

---

## 🎓 推荐学习路径

### 入门级（必学功能）
```
1. 缓存机制 (CACHE.md)
2. 内存优化 (MEMORY_OPTIMIZATION.md)
3. 进度追踪 (PROGRESS_TRACKING_GUIDE.md)
```

### 进阶级（性能提升）
```
1. 性能优化 (PERFORMANCE_OPTIMIZATION.md)
2. 执行器管理 (EXECUTOR_MANAGER_GUIDE.md)
3. Numba 加速 (NUMBA_MULTIPROCESS_GUIDE.md)
```

### 高级级（大数据处理）
```
1. 流式处理 (STREAMING_GUIDE.md)
2. 依赖分析 (DEPENDENCY_ANALYSIS_GUIDE.md)
3. 优化总结 (OPTIMIZATION_SUMMARY.md)
```

---

## 💡 最佳实践

### 默认启用（推荐）
- ✅ 缓存机制（自动）
- ✅ 进度追踪（enable_progress=True）
- ✅ 内存优化（load_waveforms=False，适用时）

### 按需启用
- 📊 流式处理（数据 > 可用内存）
- ⚡ 并行处理（多核 CPU 可用）
- 🚀 Numba 加速（计算密集型任务）

### 高级配置
- 🔧 自定义执行器配置
- 📈 性能剖析和调优
- 🎨 血缘图可视化

---

## 🔗 相关资源

### 基础知识
- [入门指南](getting-started.md) - 基本概念
- [API 参考](api-reference.md) - API 使用

### 深入理解
- [架构设计](architecture.md) - 系统架构
- [开发指南](development.md) - 开发规范

### 实践案例
- 示例代码（`examples/` 目录）
- 测试用例（`tests/` 目录）

---

**开始使用功能** → 选择一个文档开始探索！ ✨
