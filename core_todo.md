# WaveformAnalysis 插件/架构可维护性改进方案（详细版）

> 目标：让插件更容易写、插件之间更少隐式耦合、升级不容易炸、核心更容易测试/替换。  
> 适用范围：`Context + Plugin + Lineage/Cache + DAQAdapter + Streaming/Batch + Storage` 这套体系。

---

## 0. 现状基线（从文档/变更可确定）

### 已有核心抽象
- **Context**：插件调度器，管理依赖、配置、缓存
- **Plugin**：处理单元（RawFiles → Waveforms → Features/Peaks）
- **Lineage**：血缘追踪保证缓存一致性
- **DAQAdapter/FormatSpec**：隔离不同 DAQ 格式输入

### 推荐使用方式（黄金链路）
- `ctx.register(*standard_plugins)` + `ctx.get_data(run_id, "basic_features")`
- 典型链路：`raw_files → waveforms → st_waveforms → basic_features`

### 最近演进趋势（维护风险会上升）
- 采样率/采样间隔由适配器推断并被插件自动使用
- 时间字段统一（timestamp 单位、time 字段引入、阈值命名统一）
- MemmapStorage 破坏性变更（work_dir/run_id 强约束）
- Streaming/并行策略变复杂（批量提交、回退机制、executor_config）

---

## 1. 可维护性关键风险点（问题 → 影响 → 原因）

### A. 插件契约不够硬
**影响**：字段/单位变化会“悄悄破坏”下游插件，甚至结果错但不报错。  
**原因**：输出 dtype/字段/单位、输入需求、配置项没有成为机器可读契约。

### B. 配置来源混乱（显式/默认/适配器推断/兼容别名）
**影响**：难复现、难调试；缓存可能假命中。  
**原因**：没有统一的配置归一化与解析路径。

### C. `standard_plugins` 变成巨石列表
**影响**：新增/替换插件影响面过大；CPU/Streaming/JAX 混杂难维护。  
**原因**：缺少“插件集合 + profile”的组合式组织。

### D. 弃用逻辑/兼容垫片散落
**影响**：技术债难清理；行为难测试/难文档。  
**原因**：旧字段/旧配置名映射缺少集中层。

### E. 存储 API 演进快，下游调用散落
**影响**：存储后端改一次，全仓库到处修；回归压力大。  
**原因**：插件依赖具体实现而非抽象接口。

### F. Streaming/并行策略渗透业务插件
**影响**：插件职责变重、逻辑分散、难以一致优化。  
**原因**：缺少统一的执行策略抽象（ExecutionPolicy/ExecutorBackend）。

---

## 2. 总体改进目标（硬约束）

1. **插件契约化**：输入/输出 schema + config schema + version 语义必须显式、可校验、可序列化。
2. **配置收敛**：所有 config 通过唯一的解析路径（ConfigResolver），推断结果必须显式化并纳入 lineage/cache key。
3. **标准插件集解耦**：`standard_plugins` 升级为可组合的 plugin sets + profiles。
4. **合同测试守门**：契约/兼容/缓存一致性/黄金链路必须有可重复的测试。
5. **兼容与弃用集中化**：compat 层统一维护别名与弃用窗口，避免散落。
6. **执行与存储抽象化**：插件只依赖接口（StorageBackend、ExecutionPolicy），不依赖具体实现。

---

## 3. 分 PR 落地计划（按收益/投入排序）

### PR1：插件契约化（Plugin Contract）——收益最大

#### 目标
让每个插件都有**机器可读契约**：
- 输入/输出 schema（字段、dtype、单位、必填/可选）
- 配置 schema（类型、默认值、单位、范围、说明、deprecated/alias）
- version 与缓存失效语义（变更必触发 lineage 变化）
- 能力声明（supports_streaming/parallel/time_field policy）

#### 具体改动
1. 新增 `PluginSpec` / `ConfigField` 数据结构（dataclass 或 TypedDict）
2. 插件提供 `spec()` 或 `SPEC` 静态属性
3. Context 在 `register()` 时校验 spec：
   - provides 唯一
   - depends_on 可解析且无环
   - output_schema 可序列化（用于 docs / lineage）
4. Context 将「最终解析配置快照 + 插件版本 + schema hash」写入 lineage/cache key

#### 验收标准
- 缺 spec 或 spec 不合法：`ctx.register()` 直接报清晰错误
- `ctx.preview_execution()` 能输出每个节点：依赖、版本、最终 config、输出 schema

---

与 PR1 目标的差距
┌─────────────────────┬────────────────────────────┬────────────────────────────────────┐
│        需求         │          当前状态          │                缺失                │
├─────────────────────┼────────────────────────────┼────────────────────────────────────┤
│ PluginSpec          │ ❌ 不存在                  │ 需要新增完整契约数据结构           │
├─────────────────────┼────────────────────────────┼────────────────────────────────────┤
│ ConfigField         │ ❌ 不存在                  │ 需要声明 units/deprecated/alias_of │
├─────────────────────┼────────────────────────────┼────────────────────────────────────┤
│ OutputSchema        │ ⚠️ 隐式（仅 output_dtype） │ 缺少字段/单位/必填声明             │
├─────────────────────┼────────────────────────────┼────────────────────────────────────┤
│ InputSchema         │ ⚠️ 隐式（仅 input_dtype）  │ 缺少依赖字段需求声明               │
├─────────────────────┼────────────────────────────┼────────────────────────────────────┤
│ Capabilities        │ ❌ 不存在                  │ 需要 streaming/parallel 能力声明   │
├─────────────────────┼────────────────────────────┼────────────────────────────────────┤
│ spec 校验           │ ❌ register() 不检查 spec  │ 需要强制校验                       │
├─────────────────────┼────────────────────────────┼────────────────────────────────────┤
│ schema hash         │ ❌ lineage 中没有          │ 需要检测 schema 变化               │
├─────────────────────┼────────────────────────────┼────────────────────────────────────┤
│ preview_execution() │ ⚠️ 基础版                  │ 需要输出版本/config/schema         │
└─────────────────────┴────────────────────────────┴────────────────────────────────────┘

### PR2：配置系统收敛（ConfigResolver + compat 层）

#### 目标
任何插件的配置生效规则可解释、可复现、可测试，并且不会导致缓存假命中。

#### 具体改动
1. ✅ 新增 `ConfigResolver.resolve(plugin, global_config, adapter_info) -> ResolvedConfig`
2. ⚠️ 统一优先级：已采用 `显式配置 > 适配器推断 > 插件默认`（全局默认未单独定义）
3. ✅/⚠️ 单位归一化：在 resolver adapter 推断中补齐 GHz/ns 等换算（仍可扩展）
4. ✅ 新增 `compat/`：
   - 配置别名映射（alias → canonical）
   - 字段别名映射（旧字段 → 新字段）
   - 弃用窗口与 warning 策略（DeprecatedWarning → 到期报错）
5. ✅ 将适配器推断结果“显式化”：纳入 `ResolvedConfig` 并写入 lineage

#### 验收标准
- ✅ 插件运行中只读 `ResolvedConfig`（`context.get_config` 走 resolver；保留 raw dict 回退）
- ✅ CLI verbose 模式能打印关键最终配置（采样率/时间字段/阈值等）

---

### PR3：标准插件集解耦（PluginSet + Profiles）

#### 目标
把 `standard_plugins` 从“大列表”升级成“组合式 pipeline”。

#### 建议结构
- `plugin_sets/`
  - `io.py`
  - `waveform.py`
  - `features.py`
  - `signal_processing.py`
- `profiles/`
  - `cpu_default()`
  - `streaming_default()`
  - `jax_accel()`（可选）

#### 验收标准
- 新增/替换一个环节插件不影响其它 profile
- CLI 可选 profile：`--profile cpu|streaming|...`
- Quickstart 仍可保持一行注册方式（内部只是更清晰）

---

### PR4：合同测试（Contract Tests）+ 回归门槛

#### 目标
把“契约、兼容、缓存一致性、黄金链路”变成测试能守住的硬规则。

#### 建议至少覆盖 4 类测试
1. **插件契约测试**
   - 所有 builtin 插件必须有 spec
   - spec 中 output_schema/config_spec 必须完整且可序列化
   - depends_on 无环、provides 唯一
2. **缓存一致性测试**
   - run_id + config + plugin version 不变 → 命中缓存
   - 任意关键 config 改动/推断改变 → 不命中缓存（触发重算）
3. **兼容/弃用测试**
   - alias 在窗口期：warning + 映射正确
   - 过期：直接报错
4. **黄金链路端到端**
   - 最小 fake DAQ 数据夹具跑通 `raw_files → ... → basic_features`

#### 验收标准
- CI 上任何契约破坏都能定位到具体插件/字段
- 黄金链路至少在 1 个 OS + 2 个 Python 版本跑通

---

### PR5：开发者体验与文档自动化（长期降低维护成本）

#### 目标
“新增插件=写好元数据+实现+测试”，文档与可视化自动生成。

#### 具体改动
1. `waveform-docs` 从 `PluginSpec` 自动生成：
   - 插件索引页（按 profile/类别）
   - 每个插件页（输入/输出 schema、配置项、默认值、单位、示例）
2. docs 构建时做覆盖校验：builtin 插件必须有文档页
3. 提供插件脚手架（可选）：
   - 生成 Plugin + 单测 + 文档模板

#### 验收标准
- 新增插件若未提供 spec 或文档缺失：CI 失败
- docs 内容与代码契约一致（单一来源）

---

## 4. 模板：契约定义与测试（可直接复制改造）

### 4.1 插件契约数据结构（建议）
```python
from dataclasses import dataclass
from typing import Any, Optional, Tuple, Dict

@dataclass(frozen=True)
class ConfigField:
    type: type
    default: Any
    doc: str = ""
    units: Optional[str] = None
    deprecated: Optional[str] = None  # e.g. "use break_threshold_ps"
    alias_of: Optional[str] = None    # e.g. old_key -> new_key

@dataclass(frozen=True)
class PluginSpec:
    name: str
    provides: str
    depends_on: Tuple[str, ...]
    version: str
    output_schema: Dict[str, Any]      # fields/dtype/units/required
    config_spec: Dict[str, ConfigField]
    capabilities: Dict[str, Any]       # streaming/parallel/time_field/etc
