**导航**: [文档中心](../README.md) > [架构设计](README.md) > 数据模块

---

# data.py 使用、扩展与性能提示

本文件说明 `data.py` 中的主要组件、使用流程与性能优化要点。

---

## 模块组件
- **WaveformStruct**：把原始波形数组结构化为包含 `baseline / timestamp / wave` 的记录，并给出每通道的配对长度。
- **build_waveform_df**：将多通道的 `timestamp / charge / peak / channel` 合并为单通道事件表 `df`。
- **group_multi_channel_hits**：按给定时间窗口（ns）聚类多通道命中，输出事件级 DataFrame。
- **WaveformDataset**：统一容器，封装加载、提取、特征计算、分组、配对、保存等完整流程，支持链式调用；内置可扩展特征注册与自定义配对策略。

## 典型用法
```python
from data import WaveformDataset

dataset = (
    WaveformDataset(run_name="50V_OV_circulation_20thr", n_channels=2, start_channel_slice=6)
        .load_raw_data()
        .extract_waveforms()
        .structure_waveforms()
        .build_waveform_features(peaks_range=(40, 90), charge_range=(60, 400))
        .build_dataframe()
        .group_events(time_window_ns=100)
        .pair_events()
        .save_results()
)

# 获取结果
df_raw = dataset.get_raw_events()
df_events = dataset.get_grouped_events()
df_paired = dataset.get_paired_events()
summary = dataset.summary()

# 获取单个配对事件的原始波形（基于缓存的 timestamp 查找，O(1)）
wave, baseline = dataset.get_waveform_at(event_idx=0, channel=0)
```

## 可扩展特征（Feature Registry）
`WaveformDataset` 提供特征注册机制，便于在不修改核心流程的情况下添加自定义特征：

```python
# 1) 注册一个自定义特征函数
def my_rise_time(self, st_waveforms, event_length, start=50, end=150):
    vals = []
    for ch in range(len(st_waveforms)):
        arr = []
        n = int(event_length[ch])
        for wave in st_waveforms[ch][:n]:
            seg = np.asarray(wave["wave"][start:end])
            # 示例：到达最大值的一半所需样本数（伪代码）
            m = np.max(seg); half = m * 0.5
            idx = np.argmax(seg >= half) if np.any(seg >= half) else np.nan
            arr.append(idx)
        vals.append(np.asarray(arr))
    return vals

dataset.register_feature("rise_time", my_rise_time, start=60, end=160)
dataset.compute_registered_features()
dataset.add_features_to_dataframe(names=["rise_time"])   # 在 df 中新增列
```

说明：
- 特征函数签名：`fn(self, st_waveforms, event_length, **params) -> List[np.ndarray]`；返回列表长度等于通道数。
- `add_features_to_dataframe()` 会按与 `build_waveform_df` 一致的顺序拼接，并添加列到 `df`。

## 自定义配对策略
可替换默认的“按通道 [0..n-1] 全部出现”的配对规则，使用自定义策略：

```python
def my_pairing(df_events: pd.DataFrame, n_channels: int) -> pd.DataFrame:
    # 例如：只要求命中数为 2 且通道为 {0,1} 或 {1,0}
    mask = (df_events["n_hits"] == 2) & (
        df_events["channels"].apply(lambda x: set(map(int, x)) == {0, 1})
    )
    return df_events[mask]

dataset.pair_events_with(strategy=my_pairing)
```

说明：
- 策略函数签名：`strategy(df_events, n_channels) -> pd.DataFrame`。
- 若策略未生成 `delta_t`，框架会自动补齐；并尝试派生 `charge_ch* / peak_ch*` 列。

## 性能优化要点
- **timestamp→index 缓存**：`structure_waveforms()` 会构建每个通道的时间戳索引，`get_waveform_at()` 查找波形为 O(1)，避免频繁 `np.where`。
- **事件数量与长度控制**：在下游绘图/统计时，可限制事件数（如 `df_paired.head(N)`）并裁剪波形长度，显著降低计算与绘图开销。
- **时间窗口合理选择**：`group_events(time_window_ns)` 窗口过大会导致簇过大，过小则配对不足；可按数据采样率微调。
- **避免重复 I/O**：`save_results()` 只在存在配对事件时写出 CSV/Parquet；若多次试验参数，可先禁用或减少输出。
- **充足的 dtype**：内部使用 `float64` 计算 peaks/charges，确保精度并减少溢出。

## 重要参数
- `peaks_range`：峰值窗口（样本索引区间）。
- `charge_range`：电荷积分窗口（样本索引区间）。
- `time_window_ns`：事件聚类时间窗，单位 ns。
- `start_channel_slice`：原始 8 通道文件中起始通道偏移（例如 6 表示只用 CH6/CH7）。

## 返回/导出
- `summary()`：返回处理阶段摘要（事件数量、配置等）。
- `save_results(output_dir="outputs")`：输出配对事件的 CSV 与 Parquet。

## 常见问题
- **没有配对事件**：检查 `time_window_ns` 是否过小，或 `n_channels` 与数据实际通道数是否一致。
- **波形查找失败**：若手工修改了 `df_paired`，请确保 `timestamps` 仍与结构化波形数组匹配；否则 `get_waveform_at()` 会返回 `None`。

## 小结
通过“特征注册机制”与“可插拔配对策略”，你可以在不变更核心处理流水线的前提下快速扩展指标与事件选取逻辑，从而适配不同实验与分析需求。
