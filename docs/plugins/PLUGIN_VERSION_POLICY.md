# 插件 Version 升级策略

**导航**: [文档中心](../README.md) > [插件系统](README.md) > Version 升级策略

## 概述

插件的 `version` 字段用于缓存 lineage 管理。当插件的行为、输出结构或配置语义发生变化时，必须升级 `version` 以触发下游缓存失效，确保数据一致性。

本文档定义插件 `version` 升级的语义化版本规则，明确何时升级以及升级到什么级别。

## 版本格式

插件 `version` 遵循语义化版本（Semantic Versioning）规范：

```
MAJOR.MINOR.PATCH
```

例如：`"1.2.3"`

- **MAJOR**（主版本号）：破坏性变更，不兼容旧数据或配置
- **MINOR**（次版本号）：向后兼容的功能变更或算法修改
- **PATCH**（修订号）：向后兼容的 bug 修复或性能优化

## 升级规则

### MAJOR 升级（X.0.0）

**触发场景**：破坏性变更，导致输出结构、契约或依赖关系不兼容。

**具体情况**：

1. **输出 dtype 字段删除或重命名**
   - 删除已有字段（下游代码可能依赖该字段）
   - 重命名字段（例如 `record_id` 改为 `rid`）
   - 字段类型不兼容变更（例如 `i4` 改为 `i8`，可能导致精度或溢出问题）

2. **`provides` 名称变更**
   - 修改插件的 `provides` 值会破坏依赖关系

3. **不兼容的配置项变更**
   - 删除配置项（没有默认值的情况）
   - 配置项语义变更（例如时间单位从 ns 改为 us）
   - 配置项取值范围变更导致现有配置失效

4. **依赖关系破坏性变更**
   - 修改 `depends_on` 列表，移除原有依赖
   - 修改依赖的解析逻辑，导致无法兼容旧配置

**示例**：

```python
# MAJOR 升级示例：字段重命名
# 从 version "1.5.2" -> "2.0.0"

# 旧版本
output_dtype = np.dtype([
    ("record_id", "i8"),
    ("position", "i8"),
])

# 新版本（字段重命名）
output_dtype = np.dtype([
    ("rid", "i8"),  # record_id 改为 rid
    ("position", "i8"),
])
```

### MINOR 升级（0.X.0）

**触发场景**：向后兼容的功能变更、算法逻辑修改或配置扩展。

**具体情况**：

1. **输出 dtype 新增字段（向后兼容）**
   - 在结构化数组中新增字段，不影响现有字段
   - 下游插件可以选择性使用新字段

2. **算法逻辑变更**
   - 内部实现路径变更，即使输出数值完全相同
   - 例如：从 tuple 构建改为预分配数组（hit_merged Phase 3）
   - 优化算法分支、数据结构或计算顺序

3. **依赖列表变更**
   - 新增依赖项（不删除原有依赖）
   - 调整依赖解析逻辑但保持兼容

4. **新增配置项（有默认值）**
   - 新增可选配置项，旧配置仍然有效
   - 配置项语义扩展但保持向后兼容

**示例**：

```python
# MINOR 升级示例 1：算法逻辑变更
# hit_merged Phase 3: 内部构建路径从 tuple 改为预分配数组
# 从 version "1.1.0" -> "1.2.0"

# 旧实现（tuple 构建）
def _emit_cluster(hits, indices):
    return (position, start, end, ...)

# 新实现（预分配数组）
def _build_merged_from_cluster_rows(cluster_count):
    output = np.empty(cluster_count, dtype=HIT_MERGED_DTYPE)
    # 原地填充
    return output

# MINOR 升级示例 2：新增字段
# 从 version "1.3.0" -> "1.4.0"

# 旧版本
output_dtype = np.dtype([
    ("position", "i8"),
    ("width", "f4"),
])

# 新版本（新增字段）
output_dtype = np.dtype([
    ("position", "i8"),
    ("width", "f4"),
    ("amplitude", "f4"),  # 新增字段
])

# MINOR 升级示例 3：新增配置项
# 从 version "1.2.0" -> "1.3.0"

options = [
    Option("merge_gap_ns", default=1000),
    Option("enable_feature_x", default=False),  # 新增配置项
]
```

### PATCH 升级（0.0.X）

**触发场景**：向后兼容的 bug 修复或性能优化，输出结果可能变化但不改变契约。

**具体情况**：

1. **Bug 修复（输出结果变化）**
   - 修复边界条件错误
   - 修复计算错误
   - 修复数据类型转换错误

2. **纯性能优化（输出完全不变）**
   - Numba `parallel=True` 优化（输出数值完全一致）
   - 内存分配优化
   - 缓存友好性优化

3. **文档修正**
   - 修正注释、docstring 或 `agent_doc`
   - 不影响代码行为

4. **类型注解修正**
   - 修正类型提示，不影响运行时行为

**示例**：

```python
# PATCH 升级示例 1：bug 修复
# 从 version "1.2.3" -> "1.2.4"

# 旧实现（bug：边界条件错误）
if end_time < chunk_end:  # 应该是 <=
    process(data)

# 新实现（修复边界条件）
if end_time <= chunk_end:
    process(data)

# PATCH 升级示例 2：性能优化（输出不变）
# 从 version "1.2.4" -> "1.2.5"

# 旧实现
@njit
def compute(data):
    return data.sum()

# 新实现（并行优化，输出完全一致）
@njit(parallel=True)
def compute(data):
    return data.sum()
```

## 缓存失效机制

插件 `version` 的变更会触发缓存 lineage 重新计算：

1. **直接失效**：修改插件的 `version` 会导致该插件的所有缓存失效
2. **级联失效**：依赖该插件的所有下游插件缓存也会失效
3. **重新计算**：下次访问时，整条依赖链会重新执行

因此，即使是 PATCH 升级也应谨慎，确认变更确实需要触发缓存失效。

**示例场景**：

```
hit_threshold (v1.0.0) -> hit_merged (v1.2.0) -> hit_merged_features (v1.1.0)
```

如果 `hit_merged` 升级到 `v1.3.0`：
- `hit_merged` 的所有缓存失效
- `hit_merged_features` 的所有缓存失效
- `hit_threshold` 的缓存不受影响（上游独立）

## 特殊情况处理

### 内部实现路径变更

即使输出结果完全相同，内部实现路径的变更也应触发 **MINOR 升级**。

**原因**：

- 缓存 lineage 基于插件代码的完整性
- 实现路径变更可能引入微小的数值差异（浮点运算顺序）
- 保守策略确保数据一致性

**案例参考**：

- `hit_merged` Phase 3 优化（v1.1.0 -> v1.2.0）：从 tuple 构建改为预分配数组
- 详见 `docs/updates/HIT_MERGED_PHASE3_OPTIMIZATION.md`

### 文档-only 变更

纯文档变更（修改 `agent_doc`、注释、docstring）**不需要**升级 `version`。

**判断标准**：

- 代码行为完全不变
- 输出结果完全不变
- 配置解析逻辑不变

### 依赖版本约束

插件不直接声明依赖插件的版本约束。依赖关系通过 `provides` 名称解析，版本管理由缓存 lineage 自动处理。

## Checklist

升级 `version` 前确认以下事项：

- [ ] **明确升级原因**：记录为什么需要升级（bug 修复、功能变更、性能优化）
- [ ] **确定升级级别**：根据本文档规则确定 MAJOR/MINOR/PATCH
- [ ] **更新变更日志**：在 `docs/updates/` 或项目 CHANGELOG 中记录变更
- [ ] **运行兼容性检查**：执行 `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- [ ] **更新插件文档**：执行 `waveform-docs generate plugins-agent --plugin <provides>`
- [ ] **评估影响范围**：执行 `python scripts/assess_change_impact.py --base HEAD`
- [ ] **运行相关测试**：确保变更不引入回归
- [ ] **评估性能影响**：对于性能关键插件，执行性能回归检查

## 相关资源

- [AGENTS.md](../../AGENTS.md) - 插件契约 checklist（第 208-215 行）
- [插件开发完整指南](guides/PLUGIN_AUTHORING_GUIDE.md) - 插件开发最佳实践
- [HIT_MERGED_PHASE3_OPTIMIZATION.md](../updates/HIT_MERGED_PHASE3_OPTIMIZATION.md) - MINOR 升级案例
- [schema_compat_check.py](../../scripts/schema_compat_check.py) - 兼容性检查工具
- [assess_change_impact.py](../../scripts/assess_change_impact.py) - 影响评估工具

## 总结

- **MAJOR**：破坏性变更（字段删除/重命名、配置不兼容）
- **MINOR**：向后兼容的功能变更或算法逻辑修改
- **PATCH**：bug 修复或性能优化（输出完全不变时谨慎使用）
- **内部实现路径变更**：即使输出相同，也应 MINOR 升级
- **文档-only 变更**：不需要升级 version

遵循本策略可确保缓存 lineage 的正确性和数据一致性。
