# 性能优化测试套件使用指南

本目录包含了完整的测试套件，用于验证波形分析系统的性能优化（Numba 加速、并行执行等）。

## 快速开始

### 运行所有快速测试（推荐）

```bash
# 运行所有非慢速测试（约 1-2 分钟）
./scripts/run_optimization_tests.sh
```

这将运行：
- 9 个 Numba 加速单元测试
- 22 个并行执行框架测试
- 13 个边界情况和压力测试
- 7 个端到端集成测试

### 运行慢速测试（可选）

```bash
# 运行大数据集和内存压力测试（约 5-10 分钟）
./scripts/run_slow_tests.sh
```

### 单独运行特定测试组

```bash
# 功能测试 A1: Numba 加速
pytest tests/plugins/test_performance_optimizations.py -v

# 功能测试 A2: 并行执行
pytest tests/core/test_parallel_execution.py -v

# 压力测试 B2: 边界情况（快速）
pytest tests/plugins/test_stress_tests.py -v -m "not slow"

# 集成测试 C1: 端到端测试
pytest tests/integration/test_end_to_end.py -v -m "not slow"
```

---

## 测试组织结构

### 测试组 A：功能测试

#### A1：Numba 加速单元测试
**文件**: `tests/plugins/test_performance_optimizations.py`

测试 Numba 加速功能的正确性：
- `TestPeakletsNumbaAcceleration`: 测试 peaklets 聚类的 Numba 实现
- `TestHitMergedFeaturesParallel`: 测试特征计算的并行模式
- `TestOptimizationConsistency`: 验证优化后输出的一致性

```bash
pytest tests/plugins/test_performance_optimizations.py::TestPeakletsNumbaAcceleration -v
```

#### A2：并行执行测试
**文件**: `tests/core/test_parallel_execution.py`

测试插件并行执行框架：
- `TestDependencyGraph`: 依赖图构建
- `TestCycleDetection`: 循环依赖检测
- `TestExecutionLayers`: 执行层分组
- `TestParallelExecution`: 并行执行验证
- `TestRealWorldScenario`: 真实场景测试

```bash
pytest tests/core/test_parallel_execution.py::TestParallelExecution -v
```

---

### 测试组 B：性能测试

#### B1：基准性能测试脚本
**文件**: `scripts/benchmark_optimization.py`

性能对比工具，支持保存基线和生成报告。

**用法示例**:

```bash
# 1. 运行基准测试并保存为基线
python scripts/benchmark_optimization.py \
  --run-id YOUR_RUN_ID \
  --data-root DAQ \
  --save-json \
  --output baseline.json

# 2. 在代码优化后，重新运行并对比
python scripts/benchmark_optimization.py \
  --run-id YOUR_RUN_ID \
  --data-root DAQ \
  --baseline baseline.json \
  --output performance_report.md

# 3. 查看报告
cat performance_report.md
```

**输出示例**:
```markdown
# 性能优化基准测试报告

## 执行摘要
- 总执行时间（基线）: 45.230 秒
- 总执行时间（优化）: 28.145 秒
- 总加速比: 1.61x
- 时间节省: 17.085 秒 (37.8%)

## 详细性能对比
| 插件 | 基线时间 (s) | 优化时间 (s) | 加速比 | 输出行数 | 状态 |
|------|-------------|-------------|--------|----------|------|
| hit_merged | 12.340 | 7.120 | 1.73x | 45,230 | ✅ 显著提升 |
| peaklets | 8.920 | 5.440 | 1.64x | 12,450 | ✅ 显著提升 |
...
```

#### B2：压力测试
**文件**: `tests/plugins/test_stress_tests.py`

测试边界情况和大数据集处理：
- `TestLargeDatasets`: 大规模数据处理（标记为 slow）
- `TestEdgeCases`: 边界情况（空输入、单通道、极端参数等）
- `TestMemoryPressure`: 内存压力测试（标记为 slow）
- `TestDependencyCycles`: 循环依赖检测
- `TestRobustness`: 健壮性测试

```bash
# 快速测试（边界情况）
pytest tests/plugins/test_stress_tests.py::TestEdgeCases -v

# 大数据集测试（慢速）
pytest tests/plugins/test_stress_tests.py::TestLargeDatasets -v
```

---

### 测试组 C：集成测试

#### C1：端到端测试
**文件**: `tests/integration/test_end_to_end.py`

完整流水线测试：
- `TestEndToEndPipeline`: 完整流水线功能测试
- `TestRealWorldScenarios`: 真实场景测试

```bash
# 运行完整流水线测试
pytest tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_complete_pipeline_basic -v

# 运行所有真实场景测试
pytest tests/integration/test_end_to_end.py::TestRealWorldScenarios -v
```

---

## 测试标记（Markers）

### slow
标记为耗时的测试（大数据集、内存压力等）

```bash
# 排除慢速测试
pytest tests/plugins/test_stress_tests.py -m "not slow"

# 仅运行慢速测试
pytest tests/plugins/test_stress_tests.py -m "slow"
```

---

## CI/CD 集成

### 在 GitHub Actions 中使用

```yaml
name: Performance Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov

      - name: Run fast tests
        run: ./scripts/run_optimization_tests.sh

      - name: Run slow tests (optional)
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        run: ./scripts/run_slow_tests.sh
```

---

## 故障排查

### 测试失败

1. **查看详细错误信息**
   ```bash
   pytest tests/plugins/test_performance_optimizations.py -v --tb=long
   ```

2. **运行单个测试**
   ```bash
   pytest tests/plugins/test_performance_optimizations.py::TestPeakletsNumbaAcceleration::test_cluster_merged_hits_basic -v
   ```

3. **查看覆盖率**
   ```bash
   pytest tests/ --cov=waveform_analysis --cov-report=html
   ```

### Numba 相关问题

如果 Numba 测试被跳过：
```bash
# 检查 Numba 是否安装
python -c "import numba; print(numba.__version__)"

# 安装 Numba
pip install numba
```

### 内存问题

如果内存压力测试失败：
```bash
# 监控内存使用
pytest tests/plugins/test_stress_tests.py::TestMemoryPressure -v --capture=no
```

---

## 添加新测试

### 1. 功能测试模板

```python
def test_new_optimization_feature(self):
    """测试新的优化功能"""
    # 准备测试数据
    data = generate_test_data()

    # 运行优化版本
    result = optimized_function(data)

    # 验证结果
    assert result is not None
    assert len(result) > 0
```

### 2. 性能对比测试模板

```python
import time

def test_optimization_speedup(self):
    """验证优化带来的加速"""
    data = generate_large_dataset()

    # 测量优化版本
    start = time.time()
    optimized_result = optimized_function(data)
    optimized_time = time.time() - start

    # 验证加速比
    assert optimized_time < baseline_time * 0.7  # 至少 30% 提升
```

---

## 性能基准参考

基于当前测试，预期性能指标：

| 数据规模 | records | hits | 预期时间 (优化后) |
|---------|---------|------|------------------|
| 小 | 100 | 30 | < 0.1s |
| 中 | 1,000 | 300 | < 1s |
| 大 | 10,000 | 3,000 | < 10s |
| 超大 | 100,000 | 30,000 | < 2min |

**加速比目标**:
- Numba 加速: 1.5-3x
- 并行执行: 1.3-2x（取决于 CPU 核心数）
- 总体: 1.6-4x

---

## 测试报告

完整的测试报告参见：`TEST_COMPLETION_REPORT.md`

统计摘要：
- **总测试数**: 51 个（不含 slow）
- **通过率**: 100%
- **代码覆盖率**:
  - hit_merge.py: 57%
  - hit_merged_features.py: 68%
  - peaklets.py: 38%

---

## 联系和支持

如有问题或建议，请：
1. 查看 `TEST_COMPLETION_REPORT.md` 了解详细信息
2. 运行 `pytest --help` 查看更多 pytest 选项
3. 查看各测试文件顶部的文档字符串

**测试套件版本**: 1.0.0
**最后更新**: 2026-06-15
