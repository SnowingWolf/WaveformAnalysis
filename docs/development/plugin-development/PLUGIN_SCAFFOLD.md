**导航**: [文档中心](../../README.md) > [development](../README.md) > [插件开发](README.md) > 插件脚手架与测试夹具

---

# 插件脚手架与测试夹具

面向插件开发者的快速验证路径：**一键生成插件 + 单测 + 文档页**，并提供最小化的
波形假数据与临时缓存目录夹具。

---

## ✅ 一键生成

```bash
python scripts/scaffold_plugin.py MyPlugin
```

默认会生成：

- `waveform_analysis/core/plugins/custom/my_plugin.py`
- `tests/plugins/test_my_plugin.py`
- `docs/plugins/custom/my_plugin.md`

常用参数：

```bash
# 指定 provides 名称
python scripts/scaffold_plugin.py MyPlugin --provides my_plugin

# 指定依赖（逗号分隔）
python scripts/scaffold_plugin.py MyPlugin --depends-on st_waveforms,filtered_waveforms

# 自定义输出目录
python scripts/scaffold_plugin.py MyPlugin \
  --plugins-dir waveform_analysis/core/plugins/custom \
  --tests-dir tests/plugins \
  --docs-dir docs/plugins/custom
```

> 如果文件已存在，可使用 `--force` 覆盖。

---

## 🧪 测试夹具

在测试中使用 `waveform_analysis.testing.fixtures`：

```python
from waveform_analysis.testing.fixtures import make_fake_st_waveforms, make_tiny_context
```

- `make_fake_st_waveforms(...)`：最小化的 st_waveforms 假数据
- `make_tiny_context(storage_dir, run_id, st_waveforms)`：带临时缓存目录的 Context

需要演示或测试当前 records 到 S1/S2 配对的依赖图时，可注册轻量 fake pipeline：

```python
from waveform_analysis.core.context import Context
from waveform_analysis.testing import register_fake_current_pipeline

ctx = Context(storage_dir="./fake-cache")
register_fake_current_pipeline(ctx)
plan = ctx.preview_execution("run_001", "s1_s2_pairs")
```

该 pipeline 使用共同的最小 structured dtype 和纯 Python `compute()`，覆盖
records-backed 的 `hit` 旁支、`hit_threshold -> hit_merged`、peaklet/peaks 关键节点，
以及 `peak_classification -> s1_s2_pair_candidates -> s1_s2_pairs`。它只用于
测试、lineage 和教学，不模拟物理算法或生产输出 dtype，也不会加入 production profile。

示例：

```python
def test_my_plugin(tmp_path):
    ctx = make_tiny_context(tmp_path / "storage", run_id="run_001")
    ctx.register(MyPlugin())
    data = ctx.get_data("run_001", "my_plugin")
```

---

## ✅ 单测范式

脚手架默认生成以下测试模板，建议保留并按插件需求微调：

1) **`test_contract()`**
- 校验 `output_dtype`
- 检查字段是否齐全（dtype/字段）

2) **`test_cache_invalidation()`**
- 版本变更（`version`）应导致 cache key 变化
- 配置变更（`set_config`）应导致 cache key 变化

---

## 🔗 相关文档

- [最简单的插件教程](../../plugins/tutorials/SIMPLE_PLUGIN_GUIDE.md)
- [插件开发完整指南](plugin_guide.md)
