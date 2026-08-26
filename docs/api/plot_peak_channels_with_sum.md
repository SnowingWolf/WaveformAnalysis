# plot_peak_channels_with_sum 使用指南

`plot_peak_channels_with_sum` 是一个基于 `Context` 的便捷绘图函数：它自动读取指定
`run_id` 的 peak 相关数据，在顶部绘制框架已经生成的求和波形，在下方按通道绘制
组成波形。

## 快速开始

调用方只需要提供 `peak_id`、`context` 和 `run_id`，不需要手动读取或组装底层数组：

```python
from waveform_analysis.utils.visualization import plot_peak_channels_with_sum

fig, axes = plot_peak_channels_with_sum(
    peak_id=42,
    context=ctx,
    run_id="run_001",
)

if fig is not None:
    fig.savefig("peak-42-channels.png", dpi=150, bbox_inches="tight")
```

函数内部会读取 `peaklet_components`、`hit_merged`、`hit_merged_components`、
`hit_threshold`、`records`、`wave_pool`、`peaks`、`peaklet_waveforms` 和
`peaklet_waveform_pool`。因此不要把这些数组作为参数传给
`plot_peak_channels_with_sum`；那是内部实现使用的数据，不属于公开调用签名。

## 参数

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `peak_id` | `int` | 必填 | 要绘制的 peak ID。 |
| `context` | `Context` | 必填 | 已注册插件并能访问目标 run 数据的 Context。 |
| `run_id` | `str` | 必填 | 数据所属的 run；必须显式传入。 |
| `pad` | `int` | `30` | 在每个 hit 窗口两侧额外绘制的采样点数。 |
| `group_by` | `str` | `"board_channel"` | `"board_channel"` 按 `(board, channel)` 分组；`"channel"` 只按通道号分组。 |

例如，增加窗口并区分采集板：

```python
fig, axes = plot_peak_channels_with_sum(
    peak_id=919,
    context=ctx,
    run_id=run_id,
    pad=100,
    group_by="board_channel",
)
```

## 返回值和图形布局

返回 `(fig, axes)`：

- `fig` 是 Matplotlib `Figure`；
- `axes` 是一维 NumPy 数组，`axes[0]` 为求和波形，其余元素为通道子图；
- 找不到对应的 merged hit、可绘制波形或求和波形时，返回 `(None, None)`。

图形使用相对于该 peak 最早通道波形时间的纳秒坐标。通道子图会显示 hit 窗口背景和
`merged_index` 标签；当 `group_by="channel"` 时，不同 board 上同号通道会被放在同一组，
因此跨 board 分析通常应保留默认的 `"board_channel"`。

函数会调用 `plt.show()`。在脚本或 notebook 中保存后应显式关闭 figure，避免批量绘图时
累积内存：

```python
import matplotlib.pyplot as plt

fig, axes = plot_peak_channels_with_sum(
    peak_id=919,
    context=ctx,
    run_id=run_id,
)
if fig is not None:
    fig.savefig("peak-919.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
```

## 单次绘图与批量绘图

单次调用会读取并准备本次绘图所需的数据。需要检查多个 peak 时，使用
`create_peak_plotter` 复用已加载的数据：

```python
from waveform_analysis.utils.visualization import create_peak_plotter
import matplotlib.pyplot as plt

plot_peak = create_peak_plotter(context=ctx, run_id=run_id)
for peak_id in (919, 920, 921):
    fig, _ = plot_peak(peak_id=peak_id, pad=30, group_by="board_channel")
    if fig is not None:
        fig.savefig(f"peak-{peak_id}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
```

`create_peak_plotter` 会持有 `records`、`wave_pool` 和其他预加载数组的引用。批量任务
结束后释放 `plot_peak`，或让包含它的作用域结束，以便回收这些引用。

## 与 PeakChannelAccessor 的关系

`plot_peak_channels_with_sum` 仍适合已有脚本的单个 peak 绘图；新代码若还需要查询通道
特征、筛选通道或在多个视图之间切换，推荐使用统一的 `PeakChannelAccessor`：

```python
from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor

accessor = PeakChannelAccessor(ctx, run_id, lazy_load=True)

# 逐通道总览
fig, axes = accessor.plot(peak_id=919, view="stacked")

# 与 plot_peak_channels_with_sum 类似的求和波形对照
fig, axes = accessor.plot(peak_id=919, view="sum-comparison")
```

`PeakChannelAccessor` 的 `plot()` 不接受 `context` 和 `run_id` 作为每次绘图参数；它们在
构造器中绑定一次。详情见 [PeakChannelAccessor API](peak_channel_accessor.md)。

## 波形语义和常见差异

顶部求和曲线直接来自 `peaklet_waveforms + peaklet_waveform_pool`，不是把当前下方显示
的通道曲线重新相加。通道曲线则从 `records + wave_pool` 按 hit 窗口提取，并受 `pad`、
绝对时间网格、极性/基线处理以及波形来源配置影响。因此两者用于构建路径和质量检查的
对照，不应默认逐采样点完全相等。

如果需要严格比较，应同时确认：

1. 使用相同的波形来源（原始或滤波后的 pool）；
2. 使用相同的窗口，不把 `pad` 引入的额外采样混入比较；
3. 使用相同的绝对时间网格、采样间隔和信号极性/基线口径。

## 常见问题

### 返回 `(None, None)`

确认 `peak_id` 在目标 run 中存在，并且依赖产物已经生成：

```python
peaks = ctx.get_data(run_id, "peaks")
peaklet_components = ctx.get_data(run_id, "peaklet_components")
print(len(peaks), (peaklet_components["peak_id"] == 919).sum())
```

同时确认目标 run 已生成 `peaklet_waveforms` 和 `peaklet_waveform_pool`，并安装了
Matplotlib。

### 通道波形出现跨空档的斜线

跨 record 或不连续窗口应保留片段边界。若需要更细粒度的片段诊断，使用
`PeakChannelAccessor.get_channels(..., include_waveforms=True)` 查看每个通道返回的
`segments`，不要把不连续片段直接拼接成一条线。

### 内存占用过高

减小 `pad`，分批绘图并在保存后 `plt.close(fig)`。如果还需要特征查询和波形缓存控制，
使用 `PeakChannelAccessor`，在批次结束时调用：

```python
accessor.clear_waveform_cache(release_wave_pool=True)
```

## 依赖

- `matplotlib`：绘图必需；
- `numpy`：波形数组和时间轴处理；
- `waveform_analysis`：Context、插件产物和数据类型。
