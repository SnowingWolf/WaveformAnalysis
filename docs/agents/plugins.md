# Agent Plugins Guide

## 插件契约
每个插件至少声明：
- `provides`
- `depends_on`
- `options`
- `version`
- `output_dtype` 或 output kind

## 变更检查单
1. `provides` 是否稳定且唯一
2. `depends_on` 与 `resolve_depends_on()` 是否一致
3. `options` 默认值、类型、help 是否完整
4. 输出字段是否与消费方兼容
5. 是否需要同步更新插件文档

## 改动等级与动作映射
| 等级 | 典型改动 | 必要动作 |
| --- | --- | --- |
| `L1` | 算法内部调整（契约不变） | 建议 bump patch；补定向 + 边界测试 |
| `L2` | 配置语义变化、字段变化 | 必须 bump 版本；补 dtype/字段兼容测试；更新 `plugins-agent` |
| `L3` | `provides` 或依赖链变化 | 必须 bump 版本；做下游回归；同步路由与流程文档 |

说明：`provides` 变化一律按高风险 `L3` 处理。

## 推荐入口
- 流程入口：`docs/agents/workflows.md`
- 机器参考：`docs/plugins/reference/agent/INDEX.md`
- 生成命令：`waveform-docs generate plugins-agent`
