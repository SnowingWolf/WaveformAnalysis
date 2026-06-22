# PeakClassificationPlugin 功能更新总结

`PeakClassificationPlugin` 当前直接依赖 `peaks`，并使用 `s1_selection` / `s2_selection` 表达分类条件。

## 核心变化

- 运行时插件名：`peak_classification`
- 插件类：`PeakClassificationPlugin`
- 输入：`peaks`
- 输出字段：`peak_id`、`label`
- 配置入口：`s1_selection`、`s2_selection`

旧的范围字典入口已删除，不再作为配置入口保留。

## 配置示例

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

## 分类逻辑

每个 `accept_any` 条件组内部使用 AND 逻辑：

```python
{
    "s2_selection": {
        "accept_any": [
            {
                "n_hits": (8, None),
                "rise_time_10_50": (100.0, None),
            },
        ],
    },
}
```

上例要求 peak 同时满足 `n_hits >= 8` 和 `rise_time_10_50 >= 100 ns` 才会成为 S2 候选。

多个条件组之间使用 OR 逻辑；可用 `reject_any` 添加排除条件。

## 兼容性说明

- 配置契约变化，插件版本升级到 `1.1.0`。
- 旧配置入口已删除，调用方应迁移到 selection 配置。
- 插件参考文档已同步到 `docs/plugins/reference/agent/peak_classification.md`。
