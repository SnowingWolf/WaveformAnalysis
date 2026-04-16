# MCP Adapter Notes

本页预留给 MCP 映射层，不是完整 MCP server。

## 推荐映射
- `resources`
  - `docs/agents/lifecycle.md`
  - `docs/agents/workflows.md`
  - `docs/agents/index.yaml`
- `prompts`
  - planner prompt
  - executor prompt
  - reviewer prompt
- `tools`
  - 现有脚本与检查命令

## 当前边界
- 只定义映射清单和资源来源。
- 不在本轮实现 transport、auth 或远程调用能力。
