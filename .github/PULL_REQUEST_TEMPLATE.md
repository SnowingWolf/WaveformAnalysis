## 变更描述

<!-- 简要描述此 PR 的目的和主要变更 -->

## 变更类型

<!-- 勾选适用的选项 -->

- [ ] Bug 修复
- [ ] 新功能
- [ ] 重构
- [ ] 文档更新
- [ ] 测试
- [ ] 其他: ___

## 文档同步检查

<!-- 如果修改了核心模块代码，请确认是否需要更新对应文档 -->

### 涉及的核心模块

<!-- 勾选此 PR 涉及的模块 -->

- [ ] `core/context.py` - Context 核心调度器
- [ ] `core/plugins/` - 插件系统
- [ ] `core/config/` - 配置系统
- [ ] `core/storage/` - 存储层
- [ ] `core/processing/` - 数据处理
- [ ] `core/execution/` - 执行层
- [ ] `utils/` - 工具模块
- [ ] 其他: ___

### 文档更新确认

<!-- 如果修改了带有 # DOC: 注释的代码，请确认对应文档是否需要更新 -->

- [ ] 已检查代码中的 `# DOC:` 注释，确认关联文档是否需要更新
- [ ] 已更新相关文档（如适用）
- [ ] 此变更不影响用户文档

## 变更影响清单

<!-- 根据变更类型，确认以下影响项 -->

### 如果修改了插件系统

- [ ] 插件属性变更（provides/depends_on/options）
- [ ] 插件基类 API 变更
- [ ] 需要更新 `docs/features/plugin/SIMPLE_PLUGIN_GUIDE.md`
- [ ] 需要更新 `docs/development/plugin-development/PLUGIN_SPEC_GUIDE.md`

### 如果修改了配置系统

- [ ] 配置优先级变更
- [ ] 新增/移除配置项
- [ ] 兼容层变更（别名/弃用）
- [ ] 需要更新 `docs/features/context/CONFIGURATION.md`

### 如果修改了缓存/存储

- [ ] 缓存键生成逻辑变更
- [ ] 存储格式变更
- [ ] Lineage 计算变更
- [ ] 需要更新 `docs/features/context/DATA_ACCESS.md`

### 如果修改了 Context API

- [ ] 新增/移除公开方法
- [ ] 方法签名变更
- [ ] 需要更新 `docs/features/context/` 相关文档

## 测试确认

- [ ] 已运行 `make test` 并通过
- [ ] 已运行 `make check-docs` 检查文档锚点
- [ ] 已添加/更新相关测试（如适用）

## 其他说明

<!-- 任何其他需要说明的内容 -->
