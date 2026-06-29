# S1S2PairAccessor 实现总结

## ✅ 已完成

### Phase 1: 数据访问层 ✓
- ✅ `__init__()` - 初始化，支持 source、selected_only、lazy_pairs、lazy_waveform 参数
- ✅ `_load_pairs()` - 加载 pair 数据
- ✅ `_build_indices()` - 构建索引（pair_id、s1_peak_id、s2_peak_id）
- ✅ `@property pairs` - 直接访问所有配对数据
- ✅ `get_pair(pair_id)` - 查询单个配对
- ✅ `get_pairs_for_s1(s1_peak_id)` - 查询 S1 的所有配对
- ✅ `get_pairs_for_s2(s2_peak_id)` - 查询 S2 的所有配对
- ✅ `build_mask()` - 构建过滤 mask（支持 drift_time_ns_range, log10_s2_s1_range, score_total_range, flags_any/all/none, selected, custom_filter）
- ✅ `filter_pairs()` - 快捷过滤方法

### Phase 2: 波形层 ✓
- ✅ `_load_waveform_layer()` - 延迟加载波形数据
- ✅ `_normalize_waveform_time()` - 时间单位统一为 ns
- ✅ `get_waveform(peak_id, copy)` - 获取单个 peak 的 sum waveform
- ✅ `get_pair_waveforms(pair_or_id, copy, missing)` - 获取配对的 S1 和 S2 波形
- ✅ `clear_waveform_cache()` - 清理波形缓存
- ✅ `release_waveform_layer()` - 释放整个波形层

### Phase 3: 可视化层 ✓
- ✅ `plot_pair(pair_or_id, pad_ns, show_info, ax)` - 绘制配对波形
  - 支持传入 pair_id 或 pair row
  - 支持传入 ax（不强制创建新 figure）
  - 显示完整信息（drift_time_us, log10_s2_s1, score, rank, selected）
  - S1 起点作为时间零点
  - 不强制 plt.show()

### Phase 4: 集成 ✓
- ✅ 更新 `waveform_analysis/utils/__init__.py` 导出 `S1S2PairAccessor`
- ✅ 创建示例脚本 `examples/demo_s1_s2_pair_accessor.py`
- ✅ 验证导入和方法完整性

## 核心特性

### 1. 数据返回格式
- **返回 numpy structured array**（不是 dict）
- 保留 dtype 信息，性能更好
- 便于与 numpy/pandas 集成

### 2. 分层加载
- **Pair 数据层**：默认加载（轻量，~KB 级）
- **波形层**：默认懒加载（重量，~MB 级）
- 不调用波形方法时，不会加载波形数据

### 3. 索引优化
- 预构建字典索引：`pair_id → idx`, `s1_peak_id → indices`, `s2_peak_id → indices`
- O(1) 查询复杂度
- 存储 row indices（不是 pair_id），便于直接切片

### 4. 时间单位统一
- 所有对外返回的时间统一为 **ns**
- `_normalize_waveform_time()` 处理 dt/dt_ps 字段
- drift_time 在标题中显示为 **μs**（更直观）

### 5. View vs Copy
- `get_waveform(peak_id, copy=False)` 默认返回 view（性能优先）
- copy=True 时返回独立副本
- 文档明确说明：view 不应原地修改

### 6. 错误处理
- 缺失数据时抛出清晰的异常（`WaveformNotFoundError`）
- `get_pair_waveforms(missing="raise"|"return_none")` 支持不同的缺失处理策略

## 使用示例

### 替代用户原有代码

**之前（手动函数）：**
```python
def get_peaklet_waveform_by_peak_id(peak_id):
    rows = peaklet_waveforms[peaklet_waveforms["peak_id"] == int(peak_id)]
    # ...

def plot_s1_s2_pair_on_timeline(pair_row, pad_ns=200):
    # ...

for pair in candidates[:5]:
    plot_s1_s2_pair_on_timeline(pair)
```

**现在（使用 accessor）：**
```python
from waveform_analysis.utils import S1S2PairAccessor

accessor = S1S2PairAccessor(context, run_id="run_001")

# 查询
pair = accessor.get_pair(pair_id=42)

# 过滤
filtered = accessor.filter_pairs(
    drift_time_ns_range=(10000, 50000),
    log10_s2_s1_range=(1.5, None),
)

# 绘制
for pair in filtered[:5]:
    fig, ax = accessor.plot_pair(pair, pad_ns=200)
    fig.savefig(f"output/pair_{pair['pair_id']}.png")
    plt.close(fig)
```

### 与 pandas 集成

```python
import pandas as pd

accessor = S1S2PairAccessor(context, run_id="run_001")
df = pd.DataFrame(accessor.pairs)
high_score = df[df["score_total"] > 0.8]
```

## 设计原则（第一版）

1. **职责明确**：只做数据访问，不做复杂分析
2. **接口稳定**：返回 numpy array，预留扩展空间
3. **性能优先**：波形层默认懒加载，查询使用索引
4. **时间安全**：统一单位，避免单位混淆
5. **后续扩展**：统计分析和批量工具留到后续版本

## 后续扩展计划（不在第一版）

以下功能可以放到后续版本或独立 analysis helper 中：

- **统计分析**：`get_ambiguity_stats()`, `get_score_distribution()`
- **批量绘图**：`batch_plot_pairs()`, `save_pair_plot()`
- **高级可视化**：`plot_drift_time_distribution()`, `plot_log10_s2_s1_distribution()`
- **多维分析**：`scan_cuts()`, `optimize_selection()`

## 文件结构

```
waveform_analysis/utils/
├── s1_s2_pair_accessor.py          # 主实现（~500 行）
└── __init__.py                      # 导出 S1S2PairAccessor

examples/
└── demo_s1_s2_pair_accessor.py     # 使用示例
```

## 测试建议

需要创建 `tests/test_s1_s2_pair_accessor.py` 测试：

1. **索引正确性**：pair_id 不连续时
2. **过滤逻辑**：flags bitwise 运算
3. **波形提取**：时间单位、copy 参数
4. **可视化**：支持 pair_id 和 pair row
5. **缓存管理**：清理后重新加载

## 性能指标

- **索引构建**：O(N) 一次性，N = pair 数量
- **查询**：O(1)（字典查找）
- **过滤**：O(N)（numpy 向量化）
- **波形提取**：O(1)（带缓存）

## 总结

✅ **第一版 S1S2PairAccessor 已完成**，包含：
- 完整的数据访问层（查询、过滤）
- 延迟加载的波形层（时间单位统一）
- 最小必要的可视化层（单配对绘图）
- 清晰的文档和示例

✅ **核心价值**：
- 替换用户的临时函数
- 统一接口，性能优化
- 时间安全，接口稳定
- 便于后续扩展
