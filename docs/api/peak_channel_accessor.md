# PeakChannelAccessor

`PeakChannelAccessor` 是单个 peak 的通道级只读查询和基础绘图接口。通道唯一键始终为 `(board, channel)`，不能只按 `channel` 解释。

## API

```python
from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor

accessor = PeakChannelAccessor(context, run_id, lazy_load=True)
channels = accessor.get_channels(peak_id=42)
channels_with_waveforms = accessor.get_channels(peak_id=42, include_waveforms=True)
sum_waveform = accessor.get_sum_waveform(peak_id=42)
fig, axes = accessor.plot(peak_id=42, view="overlay")
```

公开数据读取入口只有：

- `get_channels(peak_id, include_waveforms=False, pad=30)`：返回逻辑通道特征；仅在 `include_waveforms=True` 时读取通道波形。
- `get_sum_waveform(peak_id)`：返回框架已生成的 peak 求和波形；找不到时返回 `None`。

辅助方法 `clear_waveform_cache(release_wave_pool=False)` 用于释放已提取的波形窗口或波形层。

公开绘图入口只有 `plot(peak_id, view=...)`：

- `view="stacked"`：逐通道总览，可配置特征、hit 窗口和求和波形。
- `view="overlay"`：在同一坐标轴叠加通道；用 `channel_filter` 筛选。
- `view="sum-comparison"`：对照框架求和波形与各通道叠加。

所有绘图形式都返回 `(figure, axes)`；`overlay` 的单个坐标轴会包装为一元素 NumPy 数组。批量保存请在调用方显式循环 `plot()`、保存并关闭 figure。

```python
# 逐通道查看，并标注常用特征
fig, axes = accessor.plot(
    peak_id=919,
    view="stacked",
    show_features=["area", "height", "width"],
)

# 只叠加 board 0 的通道
fig, axes = accessor.plot(
    peak_id=919,
    view="overlay",
    channel_filter=lambda channel: channel["board"] == 0,
)

# 对照框架求和波形与各通道叠加
fig, axes = accessor.plot(peak_id=919, view="sum-comparison")
```

## 字段来源和计算口径

`peaklet_channels` 是通道聚合真源，缺少该产物、它不是结构化数组或缺少规范字段时，会抛出 `PeakChannelDataUnavailableError`。不会退回到 `hit_merged_features` 返回部分字段。

每一行的逻辑分组键是 `(peaklet_id, board, channel)`。只使用 `hit_merged_features.valid != 0` 的组件：

| 字段 | 口径 |
| --- | --- |
| `area` | 分组内 `area` 的和 |
| `height` | 分组内 `height` 的最大值 |
| `n_hits` | 分组内 `n_hits` 的和 |
| `area_fraction` | `area / peaklet_features.area`；分母为 0 时为 0 |
| `merged_indices` | `peaklet_components` 中该逻辑通道的全部 `merged_index` |

`width`、`rise_time`、`fall_time`、`center_time`、`record_id` 和 `merged_index` 来自该逻辑通道中 `height` 最大的代表组件。`sample_start` 是所有组件的最小起点，`sample_end` 是最大终点；只有全部组件均为单 record 时 `is_single_record` 才为真。

## 波形和加载

特征层读取 `peaklet_components`、`peaklet_channels`、`hit_merged` 与 `hit_merged_features`。通道波形按需从 `records + wave_pool` 依据 hit 窗口和 `pad` 提取；同一逻辑通道的全部组件按绝对时间合并，并按 `(merged_indices, pad)` 缓存。

求和波形来自 `peaklet_waveforms + peaklet_waveform_pool`，不会从当前通道曲线重新求和。因此求和与通道波形可能使用不同窗口、时间网格或滤波来源，`sum-comparison` 仅用于构建路径对照，不是逐点相等性检验。

重复查询请复用同一个 Accessor。`lazy_load=True` 可推迟首次特征读取；`clear_waveform_cache(release_wave_pool=True)` 可释放已加载的波形层。
