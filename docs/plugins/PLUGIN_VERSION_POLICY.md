# Plugin Version Upgrade Policy

**导航**: [文档中心](../README.md) > [插件系统](README.md) > Version Upgrade Policy

本文档定义插件 `version` 字段的升级策略，用于指导开发者在修改插件时决定是否需要升级版本号，以及升级到 MAJOR / MINOR / PATCH 的哪一级。

## 为什么需要 version

插件的 `version` 字段是缓存 lineage（血统）的关键组成部分：

- 当插件的 `version`、代码、配置或 `output_dtype` 发生变化时，缓存会自动失效。
- 正确升级 `version` 可确保下游消费者获得正确的数据，避免使用陈旧缓存。
- `version` 也是向下游传递"行为已变更"的明确信号。

## Semantic Versioning 适配规则

插件 `version` 遵循 **Semantic Versioning 2.0.0** 的精神，但语义针对**算法插件契约**进行了适配：

```
version = "MAJOR.MINOR.PATCH"
```

### MAJOR（重大变更）

**定义**：契约破坏性变更，影响下游插件或用户代码。

**典型场景**：

1. **`provides` 名称变更**：输出数据类型的标识符改变。
2. **`output_dtype` 字段破坏性变更**：
   - 删除字段
   - 字段重命名
   - 字段类型变更（如 `int32` → `float64`）
   - 字段语义变更（如 `time` 单位从 ns 改为 µs）
3. **`depends_on` 重大调整**：依赖链变化导致下游插件无法正常工作。
4. **配置语义破坏性变更**：
   - 删除 `options` 中的配置项
   - 配置项类型变更（如 `int` → `str`）
   - 配置项语义变更（如 `threshold` 从绝对值改为相对值）

**示例**：

```python
# 示例 1: 删除输出字段
# BEFORE: version = "1.2.3"
HIT_DTYPE = np.dtype([
    ("time", np.int64),
    ("channel", np.int16),
    ("amplitude", np.float32),
    ("area", np.float32),  # ← 将被删除
])

# AFTER: version = "2.0.0"  # MAJOR bump
HIT_DTYPE = np.dtype([
    ("time", np.int64),
    ("channel", np.int16),
    ("amplitude", np.float32),
    # "area" 字段已删除
])

# 示例 2: 字段语义变更
# BEFORE: version = "1.5.0"
# "time" 单位为 ns
output["time"] = hit_time_ns

# AFTER: version = "2.0.0"  # MAJOR bump
# "time" 单位改为 µs
output["time"] = hit_time_ns / 1000
```
