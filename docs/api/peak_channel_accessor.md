# PeakChannelAccessor

`PeakChannelAccessor` 是单个 peak 的通道级只读查询和基础绘图接口。通道唯一键始终为 `(board, channel)`，不能只按 `channel` 解释。

## API

```python
from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor

accessor = PeakChannelAccessor(context, run_id, lazy_load=True)
channels = accessor.get_channels(peak_id=42)
hits = accessor.get_hits(peak_id=42)
merged_hits = accessor.get_merged_hits(merged_index=17)
channels_with_waveforms = accessor.get_channels(peak_id=42, include_waveforms=True)
sum_waveform = accessor.get_sum_waveform(peak_id=42)
fig, axes = accessor.plot(peak_id=42, view="overlay")
```

公开数据读取入口包括：

- `get_hits(peak_id)`：返回该 peak 的 threshold hits、所属 `merged_index` 与相邻时间间隔。
- `get_merged_hits(merged_index)`：返回该 merged hit 的 threshold hits 与相邻时间间隔。
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

每一行的逻辑分组键是 `(peaklet_id, board, channel)`。`peaklet_channels` 会展开该组全部 `merged_index` 及其跨 record 组件，在绝对时间网格上去重后再计算特征：

| 字段 | 口径 |
| --- | --- |
| `area` | 去重后通道波形的直接积分；默认保留负的基线扣除采样 |
| `height` | 去重后通道波形的最大采样值 |
| `n_hits` | 分组内 `n_hits` 的和 |
| `area_fraction` | `area / peaklet_features.area`；分母为 0 时为 0 |
| `merged_indices` | `peaklet_components` 中该逻辑通道的全部 `merged_index` |
| `waveform_area` | 返回的 `waveform` 的直接积分；仅在请求波形时存在 |

`width`、`rise_time`、`fall_time`、`center_time`、`record_id` 和 `merged_index` 来自该逻辑通道中 `height` 最大的代表组件。`sample_start` 是所有组件的最小起点，`sample_end` 是最大终点；只有全部组件均为单 record 时 `is_single_record` 才为真。

## 数据分层、波形和加载

Accessor 分为三个相互独立的延迟加载层：

| 数据层 | 依赖 | 触发入口 |
| --- | --- | --- |
| hit 查询层 | `peaklet_components`、`hit_merged_components`、`hit_threshold` | `get_hits()`、`get_merged_hits()` |
| 通道特征层 | `peaklet_components`、`peaklet_channels`、`hit_merged`、`hit_merged_features` | `get_channels()`；默认构造器会预加载，`lazy_load=True` 可推迟 |
| 波形层 | `records`、`hit_threshold`、`hit_merged_components`、`wave_pool` | `include_waveforms=True` 或绘图 |

因此，使用 `lazy_load=True` 的纯 hit 查询不会读取 `peaklet_channels`、`records` 或 wave pool。通道波形按需从 `records + wave_pool` 依据 hit 窗口和 `pad` 提取；同一逻辑通道的全部组件按绝对时间合并，并按 `(merged_indices, pad)` 缓存。顶层 `abs_time_ps` 只包含观测到的唯一采样且严格递增；同一 `(board, channel, abs_time_ps)` 的重复采样只有在 `float32` 位级相同时才会保留一次，不同值会抛出 `WaveformOverlapConflictError`。

返回值中的 `segments` 只用于检查原始 record 来源，片段之间允许重叠，不能直接拼接或积分。应使用顶层 `waveform`、`abs_time_ps` 和 `waveform_area`。当 `pad=0` 且波形来源和 `clip_negative_signal` 配置一致时，`waveform_area` 应与通道 `area` 在守恒容差内相等；`pad>0` 会包含额外窗口，不要求相等。`clip_negative_signal=False` 是默认物理口径；设为 `True` 时，裁剪发生在合并和积分之前。

求和波形来自 `peaklet_waveforms + peaklet_waveform_pool`，使用相同的按通道去重语义，并在通道去重后跨通道求和。它不包含 Accessor 的 `pad`，因此 `sum-comparison` 仍只在相同窗口、时间网格和滤波来源下适合逐点比较。

重复查询请复用同一个 Accessor。`lazy_load=True` 可推迟首次特征读取；`clear_waveform_cache(release_wave_pool=True)` 可释放已加载的波形层。
