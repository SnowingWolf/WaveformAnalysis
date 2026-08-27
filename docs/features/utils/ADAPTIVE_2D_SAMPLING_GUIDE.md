# 自适应二维分层抽样

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [工具函数](README.md) > 自适应二维分层抽样

`adaptive_stratified_sample_2d` 先把两项连续特征划分为二维网格，再根据每个网格的占用量决定保留多少行。稀疏网格会尽量完整保留，稠密网格的样本数逐渐饱和到上限，因此适合从高密度不均匀的数据中选取覆盖二维形态的代表性子集。

该工具只处理调用方提供的 `DataFrame` 和两项坐标，不依赖 `Context`、插件产物、S1/S2 标签或特定物理特征。

## 导入

推荐从稳定的工具入口导入：

```python
from waveform_analysis.utils import adaptive_stratified_sample_2d
```

也可以直接从 `waveform_analysis.utils.sampling` 导入。该函数不会从 `waveform_analysis` 包根导出。

## 基本用法

```python
import numpy as np
import pandas as pd

from waveform_analysis.utils import adaptive_stratified_sample_2d

events = pd.DataFrame(
    {
        "area": [1.0, 2.0, 10.0, 100.0, 500.0],
        "height": [2.0, 2.5, 8.0, 40.0, 120.0],
        "peak_id": [10, 11, 12, 13, 14],
    }
)
events["log_area"] = np.log10(events["area"])
events["log_height"] = np.log10(events["height"])

sampled, bin_info = adaptive_stratified_sample_2d(
    events,
    x="log_area",
    y="log_height",
    bins=(40, 40),
    n_full=4,
    n_max=12,
    random_state=42,
    return_bin_info=True,
)
```

返回的 `sampled` 是新的 `DataFrame`，保留输入的全部列和原始 index；输入表不会被修改。返回行按二维网格的处理顺序组织，不承诺保持全局原始行顺序。

## 分箱形式

`bins` 支持四种形式：

```python
bins=25                         # x、y 都使用 25 个等宽网格
bins=(40, 20)                   # x 使用 40 个，y 使用 20 个
bins=(x_edges, y_edges)         # 两轴都使用显式边界
bins=(40, y_edges)              # 整数与显式边界混合
```

整数分箱默认使用对应坐标中有限值的最小值和最大值。需要固定分析范围时可传入：

```python
range=((0.0, 6.0), (-1.0, 4.0))
```

`range` 只作用于整数分箱；显式边界保持调用方给定的值。显式边界必须是一维、有限且严格递增的数值序列。

网格区间通常为左闭右开，整个坐标轴的最大边界会计入最后一个网格。`NaN`、无穷值以及网格范围外的行不会进入返回样本。

## 自适应数量

每个网格的抽样数量由 `adaptive_sample_count` 计算：

- 网格占用量不超过 `n_full` 时全部保留；
- 更密集的网格按单调饱和曲线增加保留量；
- 任一网格最多保留 `n_max` 行；
- 抽样数量不会超过网格实际占用量。

默认 `n_full=4`、`n_max=12`。这个 API 不接受全局 `target_n`，最终行数是所有非空网格抽样数量的总和。

## 代表点与随机性

默认 `representative=True`。只要网格配额大于零，函数会先保留归一化距离上最靠近网格中心的行，再用 `numpy.random.Generator` 无放回抽取剩余行。

整数 `random_state` 可以复现随机部分；`random_state=None` 不保证不同调用得到相同结果。代表点本身不依赖随机种子。

强制代表点适合可视化覆盖，但会使网格内部不再是严格等概率抽样。需要用于总体统计推断时，可以设置：

```python
representative=False
```

此时网格内的保留行全部通过无放回随机抽样确定。二维分层仍会主动改变不同密度区域的比例；需要恢复总体统计权重时，应根据每格的 `occupancy / n_sampled` 设计分析权重。

## 网格诊断

设置 `return_bin_info=True` 后，第二个返回值对每个原始非空网格记录：

| 字段 | 含义 |
|---|---|
| `x_bin`, `y_bin` | 网格编号 |
| `x_left`, `x_right` | x 方向边界 |
| `y_left`, `y_right` | y 方向边界 |
| `occupancy` | 抽样前有效行数 |
| `n_sampled` | 实际抽样行数 |
| `sampling_fraction` | `n_sampled / occupancy` |
| `representative_index` | 代表点的原始 DataFrame index；未使用代表点时为 `None` |

这些字段可用于核对二维覆盖、记录抽样配置，以及解释抽样后分布与原始分布的差异。

## 空输入与边界行为

- 显式边界允许空输入，并返回保持列结构的空样本。
- 整数分箱在没有任何有限坐标且没有 `range` 时无法推断边界，会抛出 `ValueError`。
- `n_full` 和 `n_max` 必须是非负整数，且 `n_max >= n_full`。
- 当 `n_full=n_max=0` 时，所有非空网格的配额均为零，不会因为启用代表点而额外选中行。
