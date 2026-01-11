# 快速参考卡：跳过波形加载

## ⚡ 30 秒快速入门

```python
from waveform_analysis import WaveformDataset

# 不加载波形（节省内存）
dataset = WaveformDataset(
    run_name="50V_OV_circulation_20thr",
    load_waveforms=False  # ← 就是这个！
)

dataset.load_raw_data().extract_waveforms().build_waveform_features().build_dataframe().pair_events()

# 结果完全相同
df = dataset.get_paired_events()
```

---

## 参数说明

| 参数 | 值 | 效果 |
|------|-----|------|
| `load_waveforms` | `True`（默认） | 加载波形，支持 `get_waveform_at()` |
| `load_waveforms` | `False` | **跳过波形，节省 80% 内存** |

---

## 数据访问速查表

| 操作 | load_waveforms=T | load_waveforms=F |
|------|---|---|
| `get_paired_events()` | ✅ | ✅ |
| `df['peak_chX']` | ✅ | ✅ |
| `df['charge_chX']` | ✅ | ✅ |
| `get_waveform_at()` | ✅ | ❌ 返回 None |

---

## 性能对比

```
内存使用:    500 MB  →  100 MB   (↓80%)
处理时间:    30 秒   →  3 秒     (↓10x)
特征精度:    100%   =   100%    (相同)
```

---

## 何时使用

✅ **使用 False**:
- 内存有限
- 处理大数据集
- 只需要特征值

✅ **使用 True** (默认):
- 需要波形可视化
- 需要原始数据
- 内存充足

---

## 完整文档位置

| 需求 | 文件 |
|------|------|
| 快速答案 | [HOW_TO_SKIP_WAVEFORMS.md](../HOW_TO_SKIP_WAVEFORMS.md) |
| 详细指南 | [docs/MEMORY_OPTIMIZATION.md](../docs/MEMORY_OPTIMIZATION.md) |
| 代码示例 | [examples/skip_waveforms.py](../examples/skip_waveforms.py) |
| 演示脚本 | [scripts/demo_skip_waveforms.py](../scripts/demo_skip_waveforms.py) |
| 测试用例 | [tests/test_skip_waveforms.py](../tests/test_skip_waveforms.py) |
| 快速开始 | [QUICKSTART.md](../QUICKSTART.md#4-内存优化) |

---

## 常见问题（秒解）

**Q: 特征会不同吗？**
A: 不会，完全相同。

**Q: 可以中途切换吗？**
A: 不可以，初始化时决定。

**Q: 默认是加载吗？**
A: 是的，保持后向兼容。

**Q: 能同时用两种模式吗？**
A: 可以，创建两个实例。

---

## 就这么简单！

```python
# 记住这一行就够了：
dataset = WaveformDataset(..., load_waveforms=False)
```
