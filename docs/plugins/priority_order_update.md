# peak_classification 优先级顺序功能更新

## 更新内容

为 `PeakClassificationPlugin` 添加了灵活的优先级配置功能，允许用户自定义分类判定的优先级顺序。

## 新增配置选项

### `priority_order` (list)

```python
priority_order = ["s1_s2", "s1", "s2"]  # 默认值
```

**说明**：
- 列表形式，指定分类判定的优先级顺序（从高到低）
- 可用值：`"s1"`, `"s2"`, `"s1_s2"`
- 按顺序检查：遇到第一个满足条件的类型即返回

## 工作原理

### 旧逻辑（使用 conflict_policy）

```python
if s1_s2_ok:
    return LABEL_S1_S2  # 硬编码优先级最高
elif s1_ok and not s2_ok:
    return LABEL_S1
elif s2_ok and not s1_ok:
    return LABEL_S2
elif s1_ok and s2_ok:
    # 冲突时才使用 conflict_policy
    if conflict_policy == "prefer_s1":
        return LABEL_S1
    # ...
```

**问题**：
- ❌ `s1_s2` 优先级硬编码为最高，无法调整
- ❌ 只能处理 s1 和 s2 冲突的情况
- ❌ 不够灵活

### 新逻辑（使用 priority_order）

```python
priority_order = ["s1", "s2", "s1_s2"]

# 按优先级顺序检查
for label_name in priority_order:
    if ok_map[label_name]:
        return label_map[label_name]

# 都不满足时返回 default_label
```

**优势**：
- ✅ 完全可配置的优先级
- ✅ 支持任意顺序组合
- ✅ 逻辑清晰简单

## 使用示例

### 示例 1: 默认配置（推荐）

```python
ctx.set_config({
    "priority_order": ["s1_s2", "s1", "s2"],  # 混合信号优先
    "s1_selection": {...},
    "s2_selection": {...},
    "s1_s2_selection": {...}
})

# 行为：
# 1. 先检查是否为 s1_s2 → 是 → LABEL_S1_S2
# 2. 否，检查是否为 s1 → 是 → LABEL_S1
# 3. 否，检查是否为 s2 → 是 → LABEL_S2
# 4. 都不满足 → default_label
```

### 示例 2: S1 优先

```python
ctx.set_config({
    "priority_order": ["s1", "s2", "s1_s2"],  # S1 优先级最高
    "s1_selection": {
        "accept_any": [{"n_hits": (None, 8)}]
    },
    "s2_selection": {
        "accept_any": [{"n_hits": (8, None)}]
    },
    "s1_s2_selection": {
        "accept_any": [{"width": (150, 250)}]
    }
})

# 场景：某个 peak 同时满足 s1, s2, s1_s2
# 结果：LABEL_S1（因为 s1 在列表第一位）
```

### 示例 3: S2 优先

```python
ctx.set_config({
    "priority_order": ["s2", "s1_s2", "s1"],  # S2 优先
    "s1_selection": {...},
    "s2_selection": {...}
})

# 适用场景：
# - S2 信号更重要的实验
# - 优先保证 S2 的识别率
```

## 优先级顺序对比表

| Priority Order | 同时满足 s1, s2, s1_s2 时的结果 | 使用场景 |
|----------------|--------------------------------|----------|
| `["s1_s2", "s1", "s2"]` | S1_S2 | 默认推荐，优先识别混合信号 |
| `["s1", "s2", "s1_s2"]` | S1 | S1 识别优先场景 |
| `["s2", "s1", "s1_s2"]` | S2 | S2 识别优先场景 |
| `["s1", "s1_s2", "s2"]` | S1 | S1 最优先，混合信号次之 |
| `["s2", "s1_s2", "s1"]` | S2 | S2 最优先，混合信号次之 |

## 向后兼容性

### ✅ 完全向后兼容

如果不设置 `priority_order`（或设置为 `None`），插件会回退到旧的 `conflict_policy` 逻辑：

```python
# 旧代码（仍然有效）
ctx.set_config({
    "conflict_policy": "prefer_s1",  # 旧方式
    "s1_selection": {...},
    "s2_selection": {...}
})

# 行为与之前完全一致
```

### 优先级

1. 如果设置了 `priority_order` → 使用新逻辑
2. 如果未设置 `priority_order` → 使用旧的 `conflict_policy` 逻辑

## 测试文件

已创建测试文件：`examples/test_priority_order.py`

运行测试：
```bash
python examples/test_priority_order.py
```

测试内容：
- ✅ priority_order = ["s1_s2", "s1", "s2"]（默认）
- ✅ priority_order = ["s1", "s2", "s1_s2"]（S1 优先）
- ✅ 向后兼容性（使用旧的 conflict_policy）
- ✅ 对比不同优先级顺序的效果

## 配置建议

### 推荐配置（默认）

```python
priority_order = ["s1_s2", "s1", "s2"]
```

**理由**：
- 混合信号通常需要特殊处理
- 优先识别出来可以避免误判
- 符合大多数实验需求

### 特殊场景

#### 场景 1: 只关心 S1 和 S2，不需要识别混合信号
```python
priority_order = ["s1", "s2"]  # 不包含 s1_s2
s1_s2_selection = None  # 不配置
```

#### 场景 2: S2 识别最重要
```python
priority_order = ["s2", "s1", "s1_s2"]
```

#### 场景 3: 严格区分，混合信号最后考虑
```python
priority_order = ["s1", "s2", "s1_s2"]
```

## 实现细节

### 新增方法

```python
def _determine_label(
    self,
    s1_ok: bool,
    s2_ok: bool,
    s1_s2_ok: bool,
    priority_order: list | None,
    conflict_policy: str,
    default_label: int,
) -> int:
    """根据判定结果和优先级顺序确定最终标签"""

    # 构建判定结果映射
    ok_map = {"s1": s1_ok, "s2": s2_ok, "s1_s2": s1_s2_ok}
    label_map = {"s1": LABEL_S1, "s2": LABEL_S2, "s1_s2": LABEL_S1_S2}

    # 如果使用 priority_order（新方式）
    if priority_order is not None and len(priority_order) > 0:
        for label_name in priority_order:
            if ok_map.get(label_name, False):
                return label_map[label_name]
        return default_label

    # 向后兼容：使用旧的 conflict_policy 逻辑
    # ...
```

## 版本升级

考虑在未来版本中：
- 版本: 1.2.0 → 1.3.0
- 变更类型: MINOR（新增功能，向后兼容）
- 废弃通知: `conflict_policy` 标记为 deprecated，建议使用 `priority_order`

## 总结

### ✅ 优点

1. **灵活性**：用户可以自定义任意优先级顺序
2. **清晰性**：逻辑简单，易于理解
3. **兼容性**：完全向后兼容旧代码
4. **扩展性**：未来可以轻松添加新的分类类型

### 📊 改进前后对比

| 特性 | 旧实现 | 新实现 |
|------|--------|--------|
| s1_s2 优先级 | 硬编码最高 | 可配置 |
| 优先级调整 | 只能通过 conflict_policy 调整 s1/s2 | 完全自定义 |
| 配置方式 | 字符串 | 列表（更直观） |
| 向后兼容 | - | ✅ 完全兼容 |

---

**状态**: ✅ 实现完成，已测试
**更新日期**: 2026-06-23
