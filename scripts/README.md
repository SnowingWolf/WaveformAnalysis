# 脚本工具说明

## 导入管理工具

### `check_imports.py` - 导入规范检查

检查代码库中的导入是否符合规范：

```bash
python scripts/check_imports.py
```

检查内容：
- 禁止使用超过两级的相对导入（`...`）
- 检查导入路径是否正确

### `fix_imports.py` - 自动修复导入

自动修复常见的导入路径问题：

```bash
# 检查并显示问题
python scripts/fix_imports.py

# 自动修复
python scripts/fix_imports.py --fix

# 只检查不修复
python scripts/fix_imports.py --check
```

修复内容：
- 相对导入 → 绝对导入

## 使用 ruff 自动修复

```bash
# 安装 ruff
pip install ruff

# 自动修复所有导入问题
ruff check --fix waveform_analysis/

# 只检查导入
ruff check --select I waveform_analysis/
```

## 插件脚手架

### `scaffold_plugin.py` - 生成插件 + 单测 + 文档

```bash
python scripts/scaffold_plugin.py MyPlugin
```

常用参数：

```bash
python scripts/scaffold_plugin.py MyPlugin --provides my_plugin --depends-on st_waveforms
```

## 缓存清理

### `clear_downstream_cache.py` - 清理下游缓存

根据插件依赖关系，清理指定数据的下游缓存（可选是否包含自身）。

```bash
python scripts/clear_downstream_cache.py run_001 st_waveforms --dry-run
python scripts/clear_downstream_cache.py run_001 st_waveforms --verbose
```

## Agent 质量闸门脚本

### `assess_change_impact.py` - 改动影响面扫描

```bash
python scripts/assess_change_impact.py --base HEAD
```

扫描插件契约变更（`provides/depends_on/output_dtype/version`）、下游受影响插件与 lineage 风险。

### `schema_compat_check.py` - 字段/dtype 兼容检查

```bash
python scripts/schema_compat_check.py --base HEAD --run-smoke
```

输出字段迁移清单，并固定执行链路冒烟：
`raw_files -> records / wave_pool -> hit_threshold -> hit_merged -> peaklets -> peaks`。
同时物化 `hit_merged_components`、`peaklet_components`、`peaklet_waveforms`、
`peaklet_waveform_pool` 和 `peaklet_features`。合成输入包含确定的脉冲，所有中间产物必须非空，
实际输出 dtype 必须匹配插件声明，并检查 records、hit_threshold、hit_merged、peaks 的关键
字段与类型。该检查覆盖波形到峰的处理链，不代表事件分组或 S1–S2 配对验证。

### `performance_regression_check.py` - 性能回归对比

```bash
python scripts/performance_regression_check.py --base HEAD
```

对热点插件记录“改前/改后”耗时与峰值内存对比。默认目标包含
`st_waveforms`、`hit`、`hit_threshold`、`hit_merged` 和 `peaks`。
合成 CSV 的通道时间戳对齐 VX2730 的 2 ns 采样网格，records 解析使用单 worker，
`hit` 对六采样点矩形脉冲使用直接信号检测（`use_derivative=False`）。
任一目标输出为空会直接失败，不将解析失败或筛选后无脉冲的输出记为性能样本。

两侧使用同一个当前 benchmark harness，在各自源码目录的独立 Python 子进程中执行，
校验实际导入来源。`--json-out <path>` 保存各次样本及源码 commit、工作树变更状态、解释器
和模块路径。默认重复 5 次并比较中位数；内存回归需同时超过百分比阈值和 1 MB 绝对增量。
这里的内存指标来自 `tracemalloc`，不等于进程峰值 RSS。

退出码：`0` 表示有效比较未检测到回归，`1` 表示检测到回归，`2` 表示参数、基准建立或测量
数据无效。旧版本 worktree 无法建立时直接失败，不使用当前版本替代基准。该小型合成输入
用于快速回归检查；真实负载的首次编译、热计算和缓存读取应另外固定输入与资源预算测量。

### `benchmark_system_workload.py` - 有界真实输入基线

```bash
python scripts/benchmark_system_workload.py \
  --raw-file /path/to/RUN/RAW/completed-v1725.bin \
  --output-dir /tmp/wa-baseline-new-experiment \
  --target hit_threshold --wave-source records --threads 1
```

仅接受显式指定、位于 `RUN/RAW/` 的 V1725 完成文件，输入不超过 64 MiB；输出目录必须不存在。
脚本把产物、JIT 缓存和报告放入独立目录，最多运行 60 秒，并在采样到 worker 进程树 RSS 超过
1 GiB 时终止。RSS 按 20 ms 采样，不能保证捕获瞬时峰值。原始输入只核对大小与 mtime，不计算哈希。

报告区分首次 JIT、热 JIT 下重新读取/计算/写入，以及新 Context 的缓存映射与触碰；输出按字段、
dtype、形状和顺序精确比较。未清除系统页缓存，不能将首次运行称为冷物理 I/O。不同 `wave_source`
可能有不同的 baseline、asymmetry 筛选和 record ID 语义，不能未经结果匹配直接比较提速比例。

### `release_artifact_sync.py` - 发布前统一校验

```bash
python scripts/release_artifact_sync.py --base HEAD
```

统一检查版本号、`CHANGELOG`、agent/auto 文档、doc anchors、schema smoke、`tests/`
全测试目录与性能回归结果。

## 工作流程

1. **开发时**：运行 `check_imports.py` 检查导入规范
2. **重构时**：运行 `fix_imports.py --fix` 自动修复
3. **CI/CD**：集成 `check_imports.py` 和 `ruff check` 到 CI 流程

## 相关文档

- [导入风格指南](../docs/IMPORT_STYLE_GUIDE.md)
