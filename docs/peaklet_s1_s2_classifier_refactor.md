# PeakClassificationPlugin 重构总结

`PeakClassificationPlugin` 已收敛为基于 `peaks` 的 S1/S2 分类插件。

## 当前配置方式

分类条件统一通过 selection 配置：

```python
ctx.set_config(
    {
        "s1_selection": {
            "accept_any": [
                {
                    "width": (0.0, 100.0),
                    "area": (0.0, 500.0),
                },
            ],
            "reject_any": [
                {"width": (400.0, None)},
            ],
        },
        "s2_selection": {
            "accept_any": [
                {
                    "width": (300.0, None),
                    "area": (1000.0, None),
                    "n_hits": (8, None),
                    "rise_time_10_50": (100.0, None),
                },
            ],
        },
        "s1_s2_selection": {
            "accept_any": [
                {
                    "width": (100.0, 200.0),
                    "area": (400.0, 600.0),
                },
            ],
        },
        "default_label": "unknown",
    },
    plugin_name="peak_classification",
)
```

## Selection 语义

- `accept_any`: 满足任一条件组即成为候选。
- `reject_any`: 满足任一条件组即排除。
- 条件组内部是 AND 逻辑。
- 多个条件组之间是 OR 逻辑。
- `s1_s2_selection` 命中时优先输出 `S1_S2`。

## 版本变化

| 版本 | 配置方式 | 依赖 |
|------|---------|------|
| v1.0.0 | 范围字典配置 | `["peaks"]` |
| v1.1.0 | selection 配置 | `["peaks"]` |
| v1.2.0 | 新增显式 S1_S2 selection | `["peaks"]` |

## 迁移指南

调用方需要把每个范围字典改成 selection 条件组。

旧式范围字典的一个条件组：

```python
{
    "width": (300.0, None),
    "n_hits": (8, None),
}
```

迁移为：

```python
{
    "accept_any": [
        {
            "width": (300.0, None),
            "n_hits": (8, None),
        },
    ],
}
```

## 数据流

```text
peaks
  -> PeakClassificationPlugin.compute()
  -> _extract_features()
  -> _check_selection()
  -> peak_classification
```

## 验证入口

```bash
/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest tests/plugins/test_peak_classification_plugin.py
```
