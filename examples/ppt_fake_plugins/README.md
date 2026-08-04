# PPT Fake Plugins

这组插件只用于 PPT 中展示一条容易阅读的概念链：

```text
records -> hit -> hit_merged -> peaks -> s1_s2
```

它们统一返回空 structured array，不执行波形分析。该链是刻意简化的示意图，
**不是 WaveformAnalysis 的真实生产 DAG**，也不应注册到生产 profile。真实链包含
`hit_threshold`、peaklet、feature、classification 和 S1/S2 pairing 等更多节点。

## 使用

```python
from waveform_analysis.core.context import Context

from examples.ppt_fake_plugins import PPT_FAKE_PLUGINS

ctx = Context()
ctx.register(*PPT_FAKE_PLUGINS)

# 文本方式查看依赖解析顺序。
print(ctx.resolve_dependencies("s1_s2"))

# 或生成 lineage 图；可按环境改用 kind="plotly"。
ctx.plot_lineage("s1_s2", kind="mermaid")
```
