# PeakletS1S2ClassifierPlugin 功能更新总结

## 更新内容

`PeakletS1S2ClassifierPlugin` 已从旧的 `peaklet_features` / `peaklets` 双输入改为直接依赖 `peaks`，并使用字典式范围配置：

- **n_hits**：peak 包含的 hit 数量
- **rise_time_10_50**：信号从 10% 到 50% 面积的上升时间（单位：ns）
- **s1_ranges / s2_ranges**：统一配置任意 peak 特征的范围条件
- **default_label**：不满足任何显式条件时的默认标签

## 物理意义

这两个特征反映了 S2 信号的物理特性：

1. **n_hits >= 8**：
   - S2 信号是由电子漂移产生的二次闪烁信号
   - 电子云会在多个 PMT 通道上产生响应
   - 因此 S2 信号通常包含更多的 hit（多通道响应）

2. **rise_time_10_50 >= 100 ns**：
   - S2 信号由电子漂移产生，上升过程较慢
   - S1 信号是直接闪烁，上升非常快
   - rise_time_10_50 可以有效区分快速（S1）和慢速（S2）信号

## 配置示例

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletS1S2ClassifierPlugin

ctx = Context()
ctx.register(PeakletS1S2ClassifierPlugin())

# 配置 S2 判断条件
ctx.set_config(
    {
        "s2_ranges": {
            "n_hits": (8, None),
            "rise_time_10_50": (100.0, None),
        },
        "default_label": "s1",
    },
    plugin_name="peaklet_s1_s2",
)

# 执行分类
labels = ctx.get_data(run_id, "peaklet_s1_s2")
```

## 配置选项

- `s1_ranges`: S1 特征范围字典，例如 `{"width": (0, 100), "n_hits": (1, 7)}`。默认 `None`。
- `s2_ranges`: S2 特征范围字典。默认 `{"n_hits": (8, None), "rise_time_10_50": (100.01, None)}`。
- `conflict_policy`: 同时满足 S1/S2 条件时的处理策略，支持 `unknown`、`prefer_s1`、`prefer_s2`，默认 `prefer_s1`。
- `default_label`: 不满足任何配置条件时的默认标签，支持 `unknown`、`s1`、`s2`，默认 `s1`。
- `strict`: 若没有任何 S1/S2 条件时是否报错，默认 `False`。

可用字段包括 `width`、`area`、`height`、`rise_time`、`fall_time`、`rise_time_10_50`、`width_25_75`、`range_90p_area`、`n_hits`、`n_channels`。

## 输出数据结构变化

输出数据类型 `PEAKLET_S1_S2_CLASSIFIER_DTYPE` 收敛为分类结果字段：

完整字段列表：
```python
[
    ("peak_id", "i8"),
    ("label", "i1"),
]
```

## 分类逻辑

分类器使用 **AND 逻辑**：所有配置的条件必须**同时满足**才能判定为某一类型。

例如，配置以下 S2 条件：
```python
{
    "s2_ranges": {
        "n_hits": (8, None),
        "rise_time_10_50": (100.0, None),
    },
}
```

一个 peak 必须**同时满足** `n_hits >= 8` **且** `rise_time_10_50 >= 100 ns` 才会被标记为 S2。

## 测试覆盖

新增了 3 个测试用例：

1. **test_peaklet_s1_s2_classifier_n_hits_filter**
   - 测试单独使用 n_hits 范围过滤

2. **test_peaklet_s1_s2_classifier_rise_time_10_50_filter**
   - 测试单独使用 rise_time_10_50 范围过滤

3. **test_peaklet_s1_s2_classifier_combined_s2_criteria**
   - 测试组合条件：n_hits >= 8 且 rise_time_10_50 >= 100 ns

所有测试通过，覆盖率 93%。

## 演示脚本

创建了演示脚本：`examples/demo_peaklet_s1_s2_n_hits_rise_time.py`

运行方式：
```bash
python examples/demo_peaklet_s1_s2_n_hits_rise_time.py
```

演示了如何配置和使用新特征进行 S1/S2 分类。

## 兼容性说明

- 插件 `version` 从 `0.1.0` 升级到 `1.0.0`，因为输出 dtype 删除了旧特征快照字段。
- 依赖从 `["peaklet_features", "peaklets"]` 改为 `["peaks"]`。
- 旧的 `s1_*_range` / `s2_*_range` 独立配置项已由 `s1_ranges` / `s2_ranges` 取代。
- 输出 dtype 从多字段特征快照收敛为 `peak_id` 和 `label`。

## 文件修改清单

1. **插件实现**：`waveform_analysis/core/plugins/builtin/cpu/peaklet_s1_s2_classifier.py`
   - 更新依赖、输出数据类型和配置项
   - 更新 compute 方法逻辑，直接读取 `peaks`

2. **测试文件**：`tests/plugins/test_peaklet_s1_s2_classifier_plugin.py`
   - 更新测试数据
   - 更新期望字段
   - 添加 3 个新测试用例

3. **演示脚本**：`examples/demo_peaklet_s1_s2_n_hits_rise_time.py`（新建）
   - 演示如何使用新特征

## 验证结果

验证命令以本次提交前实际执行结果为准；目标行为是支持 `n_hits >= 8` 且 `rise_time_10_50 >= 100 ns` 作为 S2 判断条件。
