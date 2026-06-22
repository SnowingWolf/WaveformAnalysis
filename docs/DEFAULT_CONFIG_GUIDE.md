# PeakClassificationPlugin 配置说明

`PeakClassificationPlugin` 通过 `peaks` 表中的特征把 peak 标记为 S1、S2、Unknown 或 S1_S2。

当前插件的分类条件统一使用 `s1_selection` 和 `s2_selection`。

每个 selection 可以包含：

- `accept_any`: 条件组列表，满足任一条件组即成为候选。
- `reject_any`: 条件组列表，满足任一条件组即排除。

条件组内部使用 AND 逻辑；多个条件组之间使用 OR 逻辑。

## 使用示例

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakClassificationPlugin

ctx = Context()
ctx.register(PeakClassificationPlugin())

ctx.set_config(
    {
        "s2_selection": {
            "accept_any": [
                {
                    "n_hits": (8, None),
                    "rise_time_10_50": (100.0, None),
                },
            ],
        },
        "default_label": "s1",
    },
    plugin_name="peak_classification",
)

labels = ctx.get_data(run_id, "peak_classification")
```

## 同时配置 S1 和 S2

```python
ctx.set_config(
    {
        "s1_selection": {
            "accept_any": [
                {
                    "width": (0.0, 100.0),
                    "n_hits": (1, 7),
                },
            ],
        },
        "s2_selection": {
            "accept_any": [
                {
                    "width": (300.0, None),
                    "n_hits": (8, None),
                    "rise_time_10_50": (100.0, None),
                },
            ],
        },
        "default_label": "unknown",
    },
    plugin_name="peak_classification",
)
```

## 配置选项

### s1_selection / s2_selection

**默认值：** `None`

分类 selection 字典。可用字段包括 `width`、`area`、`height`、`rise_time`、`fall_time`、`rise_time_10_50`、`width_25_75`、`range_90p_area`、`n_hits`、`n_channels`。

### default_label

**默认值：** `"unknown"`

当不满足任何配置条件时的默认标签。可选值为 `"unknown"`、`"s1"`、`"s2"`。

### conflict_policy

**默认值：** `"prefer_s1"`

当同时满足 S1 和 S2 条件时的处理策略。可选值为 `"unknown"`、`"prefer_s1"`、`"prefer_s2"`、`"mark_as_s1_s2"`。

### strict

**默认值：** `False`

为 `True` 时，至少需要配置一个 S1 或 S2 selection。

## 常见配置

只使用 S2 条件：

```python
{
    "s2_selection": {
        "accept_any": [
            {"n_hits": (8, None), "rise_time_10_50": (100.0, None)},
        ],
    },
    "default_label": "s1",
}
```

只使用 n_hits：

```python
{"s2_selection": {"accept_any": [{"n_hits": (8, None)}]}}
```

只使用 rise_time_10_50：

```python
{"s2_selection": {"accept_any": [{"rise_time_10_50": (100.0, None)}]}}
```

## 相关文档

- 插件参考：`docs/plugins/reference/agent/peak_classification.md`
- 演示脚本：`examples/demo_peaklet_s1_s2_n_hits_rise_time.py`
