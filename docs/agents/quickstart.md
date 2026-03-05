# Agent Quickstart

> 兼容速查页。主入口与硬约束请先看 `../../AGENTS.md`。

## 目标（5 分钟）
快速定位改动路径、验证命令和文档同步动作。

## 5 分钟流程
1. 读 `../../AGENTS.md` 获取硬约束和场景路由。
2. 读 `plugins.md` 确认插件链路与依赖。
3. 读 `configuration.md` 确认配置来源与兼容。
4. 执行定向测试，再执行回归测试。

## 常用命令
```bash
./scripts/run_tests.sh -v -k <keyword>
waveform-docs generate plugins-agent --plugin <provides>
waveform-docs check coverage --strict
```

## 文档同步检查
```bash
scripts/check_doc_sync.sh
python scripts/check_doc_anchors.py --check-sync --base HEAD
```
