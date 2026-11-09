# 插件执行链与缓存

**导航**: [文档中心](../README.md) > [系统架构与数据模型](README.md) > 插件执行链与缓存

一次 `Context.get_data(run_id, target)` 请求同时使用四类信息：Plugin 契约声明节点，静态和动态
依赖组成当前 DAG，lineage 在该 DAG 上递归建立结果身份，缓存用 `(run_id, provides, lineage)`
判断结果能否复用。

Context 负责统一协调插件注册、依赖解析、lineage 与缓存复用；具体产物仍由单一 Plugin 发布，
组合查询由 Accessor 完成。

公开的 Context 方法保留显式签名，配置、缓存、执行和时间操作分别委派给内部 domain；
这些入口与 domain 实现承担不同职责。内存和磁盘命中共用统计记录及输出转换出口。
Context 的缓存诊断入口为 `diagnose_cache(run_id=None, verbose=True)`，只检查并返回问题。
容量统计、条目列表和修复使用 `waveform-cache` CLI；扫描实现继续由缓存工具管理。

除非显式传入 `storage_dir`，Context 默认把缓存和处理产物写入当前目录下的 `./wa_data/`；
`data_root` 只用于定位原始 DAQ 数据，默认值为 `DAQ`。因此原始输入与可重建的缓存产物不会因为
默认配置而混在同一个目录中。

```mermaid
flowchart LR
    CONTRACT[Plugin 契约] --> DAG[本次 Plugin DAG]
    STATIC[静态 depends_on] --> DAG
    DYNAMIC[动态 resolve_depends_on] --> DAG
    DAG --> PLAN[执行顺序与缺失节点]
    DAG --> LINEAGE[递归 lineage]
    CONFIG[tracked 配置 / adapter] --> LINEAGE
    SCHEMA[version / dtype / schema] --> LINEAGE
    LINEAGE --> CACHE[缓存身份与复用]
    CACHE --> PLAN
```

DAG 与 lineage 是协同关系：DAG 提供结果的计算结构，lineage 把结构上每个节点使用的实现、配置和
上游身份固定下来。缓存既不能只看图，也不能脱离图单独计算身份。

## 1. Plugin 契约

### 1.1 一个 Plugin 发布一个正式产物

`provides` 是注册表中的唯一数据名。一个 Plugin 可以在内部创建多个数组、索引或临时对象，但只能
对外拥有一个稳定的结果语义。多个正式结果应由多个 Plugin 分别发布，即使它们共享同一次内部构建。

| 契约项 | 运行时用途 | 变化后的处理 |
| --- | --- | --- |
| `provides` | 注册表键、DAG 节点、缓存键的一部分 | 重命名属于公开契约迁移 |
| `depends_on` | 始终存在的上游边 | 新增或删除依赖需同步 lineage 与测试 |
| `resolve_depends_on()` | 本次请求真实存在的条件边 | 必须在执行前确定且可重复解析 |
| `options` | 配置声明、类型校验、来源与跟踪策略 | 语义变化需升级 version |
| `version` | 实现/行为身份 | 行为改变后主动失效旧结果 |
| `output_dtype` / `output_schema` | 字段、类型和结构约束 | 契约变化需执行 schema 检查 |

依赖可声明为 `("upstream", ">=1.0,<2.0")`。已注册 provider 的版本不满足约束时，consumer
注册会抛出 `ValueError`。请求还会按 `run_id` 检查目标可达的版本约束，覆盖晚注册、provider
替换和动态依赖，并在返回内存或磁盘缓存之前拒绝不兼容结果。成功验证按 run 和目标复用，注册、
配置变更或清理缓存时失效；无约束的有效缓存不要求缺失的上游插件重新注册。
显式约束要求可用的 `packaging`、合法版本及约束表达式，校验失败不会降为警告。
旧的 `resolve_depends_on(context)` 签名仍受支持；解析函数内部的 `TypeError` 直接传播。

已退役的 `df`、`df_events`、`df_paired` 及旧别名会在读取缓存前被拒绝。
缓存文件仍保留，但不能用旧缓存恢复已移除的产物契约；现行调用按
[旧表格链路迁移说明](../user-guide/DF_RETIREMENT.md) 显式选择目标并处理排序和标定。

### 1.2 Plugin 内数据获取

Plugin 通过 `context.get_data(run_id, name)` 读取正式上游，且 `name` 必须出现在静态或动态依赖中。
这条约束让依赖查询、lineage、缓存清理和实际运行看到同一张图。

```mermaid
flowchart TD
    COMPUTE[Plugin.compute] --> DECLARED{上游是否已声明?}
    DECLARED -->|是| GET[Context.get_data run_id name]
    GET --> PRODUCT[正式产物]
    DECLARED -->|否| ERROR[DAG 外隐式读取]
    PRIVATE[_results / bundle / 临时文件] --> ERROR
```

读取 `_results`、共享 builder 的私有键、另一个 Plugin 实例属性或临时文件，会绕过正式依赖关系。
即使当前运行能得到数组，预览和缓存也无法知道真实输入，属于契约错误。

## 2. 静态 DAG

### 2.1 节点与边

节点是 `provides`，边是产物依赖。Context 从目标向上递归解析，得到拓扑顺序；缺失目标、缺失上游
或依赖环在执行前失败。

```mermaid
flowchart LR
    RAW[raw_files] --> RECORDS[records]
    RAW --> POOL[wave_pool]
    RECORDS --> FILTER[wave_pool_filtered]
    POOL --> FILTER
    RECORDS --> HITS[hits]
    FILTER --> HITS
    HITS --> MERGED[hit_merged]
    MERGED --> PEAKLETS[peaklets]
    PEAKLETS --> PEAKS[peaks]
```

图只示意依赖方向，不替代当前 Plugin 注册表。运行时图以
`Context.resolve_dependencies(target, run_id=...)` 的结果为准。

### 2.2 DAG 不变量

1. 每个 `provides` 在一个 Context 注册表中唯一。
2. 目标及所有上游必须已注册或由合法输入边界提供。
3. 图必须无环，拓扑顺序中上游先于下游。
4. `compute` 实际读取的全部正式数据必须出现在本次图中。
5. 单次 Plugin 执行只处理请求中的一个 `run_id`。

## 3. 动态依赖

### 3.1 解析时机

`resolve_depends_on(context, run_id=None)` 用于 adapter、配置或 run 条件决定上游的情况。动态边在
lineage 与缓存查询之前解析，因此选择结果同时影响执行计划和结果身份。

```mermaid
sequenceDiagram
    participant C as Context
    participant P as Target Plugin
    participant R as Config resolver
    participant G as DAG / lineage builder

    C->>R: 解析当前 Plugin 配置与 adapter
    R-->>C: 稳定的 resolved config
    C->>P: resolve_depends_on(context, run_id)
    P-->>C: 本次正式上游名称
    C->>G: 合并静态边与动态边
    G-->>C: 当前 DAG + 递归 lineage
```

动态依赖只能基于已解析配置、adapter 信息和请求上下文作选择，不能先调用未声明的 `get_data()`
探测哪条上游“有数据”。后者会先在 DAG 外触发计算，使预览、缓存键和真实执行分叉。

### 3.2 分支例子

以波形输入选择为例：records-backed 算法依赖结构化索引与对应 pool，另一种输入模式可能依赖已经
物化的波形产物。目标 Plugin 名称可以不变，但不同配置下的依赖集合和 lineage 必须不同。

```mermaid
flowchart TD
    OPTION{wave_source}
    OPTION -->|records| RECORDS[records]
    OPTION -->|records| POOL[wave_pool / wave_pool_filtered]
    OPTION -->|materialized| WAVES[st_waveforms]
    RECORDS --> TARGET[target Plugin]
    POOL --> TARGET
    WAVES --> TARGET
```

同一 resolved config 和 run 条件应得到确定的依赖集合。若解析依赖依赖随机状态、调用顺序或上次
执行留下的内存对象，则无法形成稳定缓存身份。

## 4. 从 DAG 到执行计划

### 4.1 Cache-aware plan

Context 先解析目标的依赖顺序，再计算各节点当前缓存键。执行计划保留逻辑 DAG，但只运行未命中或
身份变化的节点。

| 节点状态 | 执行动作 |
| --- | --- |
| 内存结果存在且 lineage 一致 | 直接复用 |
| 磁盘结果存在、元数据和 lineage 一致 | 加载并复用 |
| 上游命中、当前节点缺失 | 只执行当前节点 |
| 上游 lineage 改变 | 从变化节点向下游重算 |
| 动态依赖选择另一分支 | 计算新分支对应的缺失节点 |

`resolve_dependencies(target, run_id=run_id)` 可查询拓扑顺序；它不报告缓存命中或重算范围。
`get_data()` 可直接读取有效目标缓存：无显式版本约束的缓存读取仍可缺少上游 provider。
执行计划未命中时由依赖解析统一验证版本，计划命中时仍验证已注册 provider 的约束。

`Plugin.timeout` 是执行属性，不是 `set_config()` 配置项，其值不进入 lineage 或缓存身份。
Context 当前只支持 `timeout=None`；非 `None` 值在该插件的 `compute()` 入口触发
`NotImplementedError`，有效缓存命中仍可正常读取。此时上游依赖可能已经执行，不能将该检查
视为整张 DAG 执行前的校验。平台与独立函数限制见[超时支持边界](ARCHITECTURE.md#超时支持边界)。

## 5. Lineage

Context 按需从 `waveform_analysis.visualization` 加载 lineage renderer，避免普通数据处理
提前导入 Matplotlib 或 Plotly；`waveform_analysis.utils.visualization` 保持为同一模块对象的兼容入口。

### Lineage 与缓存身份

#### 5.1 结果身份的组成

用户通过 `ctx.get_lineage(data_name)` 查询 lineage；公共签名只接收数据名称。
循环检测与递归状态由私有 `_get_base_lineage()` 管理，不由调用方传递。

默认 lineage 是可序列化配方，包含 Plugin 类、version、描述、受跟踪配置和递归上游 lineage；
存在时还会加入规范化 dtype、`output_schema`、已验证 spec hash 和顶层 adapter 信息。Context 递归缓存
不含 adapter 信息的基础 lineage，并只在顶层补充一次，所以首次查询、缓存后查询及不同遍历顺序具有
相同身份。adapter 元数据提取不使用全局缓存；同名注册表替换不会通知既有 Context，
因此必须在替换格式规范后新建 Context，避免复用旧配置或 lineage。

V1725 分卷顺序按整数索引排列（如 `seg0, seg2, seg10`），此读取解释变更由 `raw_files` 的
`0.0.3` 版本沿上游 lineage 传播至 `st_waveforms`；无需为未变更的结构化算法单独升级版本。
`records` 与 `wave_pool` 的共享原始输入路径版本均为 `0.17.0`，旧 bundle 缓存随对应 lineage 失效。

Plugin 可用 `get_lineage(context, *, dependency_resolver=None)` 补充自身构建语义，并应使用
传入的 resolver 构造上游；旧的单参数 hook 仍兼容。

```mermaid
flowchart TD
    CLASS[Plugin class] --> NODE[节点 lineage]
    VERSION[version] --> NODE
    TRACKED[tracked resolved config] --> NODE
    OUTPUT[dtype / schema / spec] --> NODE
    ADAPTER[adapter interpretation] --> NODE
    UP1[upstream lineage A] --> NODE
    UP2[upstream lineage B] --> NODE
    NODE --> DIGEST[lineage digest]
    RUN[run_id] --> KEY[cache key]
    NAME[provides] --> KEY
    DIGEST --> KEY
```

lineage 不包含数组内容，也不表示缓存一定存在。它回答“这份结果应该由什么产生”；Storage 再根据
该身份检查是否存在可读取结果。

历史版本若仅因 `adapter_info` 附着层级不同生成了另一个 key，磁盘读取器可以只读复用，但必须有
lineage 元数据作为证明：递归移除 `adapter_info` 后其余 JSON 完全一致，且已声明的 adapter 信息没有
冲突。规范 key 始终优先，新计算也只写规范 key；任何 version、配置、dtype/schema/spec 或依赖差异
仍会触发重算。

### 5.2 传播规则

```mermaid
flowchart LR
    A[A version/config 改变] --> LA[A 新 lineage]
    LA --> B[B 的上游身份改变]
    B --> LB[B 新 lineage]
    LB --> C[C 的上游身份改变]
    C --> LC[C 新 lineage]
```

上游变化沿 DAG 传播。下游代码完全未改，只要输入身份改变，它仍应得到新 lineage。反过来，纯资源
配置若声明 `track=False`，不应仅因 worker 数或批大小变化而使全链失效。

## 6. 缓存复用与失效

### 6.1 命中顺序

```mermaid
flowchart TD
    REQUEST[run_id + target] --> CURRENT[计算当前 lineage key]
    CURRENT --> MEM{内存键一致?}
    MEM -->|是| RETURN[返回]
    MEM -->|否| DROP[丢弃不一致内存项]
    DROP --> DISK{磁盘键与元数据一致?}
    DISK -->|是| LOAD[加载并返回]
    DISK -->|否| PLAN[执行缺失 DAG 节点]
    PLAN --> SAVE[保存数据 + lineage 元数据]
    SAVE --> RETURN
```

当前缓存键包含 `run_id`、产物名称和 lineage 摘要。同名产物在不同 run 中不会共享键；同一 run
中配置、version、输出契约或上游身份变化也会产生不同键。

分层缓存另有发布快照和私人缓存的读取策略，并在复用之前验证冻结的上游身份；
详见[分层缓存](../features/context/LAYERED_CACHE.md)。上图描述普通单目录模式。

### 6.1.1 大型波形池的持久化

`peaklet_waveform_pool` 一类的大型连续数组仍须完整写入磁盘，才能在新 Context 中命中缓存；这段
I/O 不能视为 waveform 的重复计算。memmap 存储直接写入连续 ndarray 的 buffer，避免先用
`tobytes()` 创建同等大小的 Python 临时副本。性能诊断应分别记录 Plugin compute 与 cache-save
时间，避免把存储带宽、压缩或 checksum 成本误判为算法回归。

### 6.1.2 写入锁与替换边界

Memmap 的 `save_stream` / `save_memmap`、Context 的 generator 缓存写入和 `delete`
使用同一 key 的文件锁。锁文件在解锁后保留，避免已打开旧 inode 的等待者与新进入者锁住不同
文件；临时二进制文件在释放锁之前清理。读取不存在的 run/key 不创建目录。

二进制和 metadata 分别通过 `os.replace` 替换，避免先删除旧文件产生的缺失窗口；这不构成两个
文件的联合事务。独立 `save_metadata`、`finalize_save` 与 DataFrame 写入不自动取得该锁，
调用者不能据此假定所有存储格式都支持并发覆盖。`delete` 当前删除二进制与 metadata，保留
锁文件，也不负责回收残留的压缩或 DataFrame 数据文件。

结果只保存在显式 `(run_id, data_name)` 的内存存储中，不再自动挂到 `ctx.<data_name>`。
读取统一使用 `ctx.get_data(run_id, data_name)`；普通对象属性不作为结果或依赖注入。
`clear_cache_for(..., clear_disk=False)` 只移除选定 run 的内存结果和关联 lineage，保留另一 run 的结果
以及用户自己设置的普通属性。调用方或 Accessor 自己持有的引用不受
影响，释放 Python 引用也不保证分配器立即归还 RSS。这是显式清理，不是自动内存预算或淘汰策略。

### 6.2 失效矩阵

配置更新统一通过 `ctx.set_config(...)`，自动失效解析配置、运行配置、lineage、缓存键与执行计划。
内部维护入口不再作为公开 API；无需在配置修改后手动清理规划缓存。
指定 run 的产物清理继续使用 `clear_cache_for(run_id, data_name)`，迁移细节见
[配置管理](../features/context/CONFIGURATION.md#context-api-迁移)。

| 变化 | 正常行为 | 失败时的表现 |
| --- | --- | --- |
| Plugin 行为变化并升级 `version` | 当前节点及下游新键 | 未升级时静默复用旧算法结果 |
| tracked 配置变化 | 当前节点及下游新键 | 错标 `track=False` 时旧结果命中 |
| 动态依赖切换 | lineage 包含另一上游分支 | 动态边遗漏时预览与执行不一致 |
| dtype/schema/spec 变化 | 新输出身份并执行兼容检查 | 契约未进入 lineage 时旧文件被误读 |
| 上游缓存损坏 | 读取失败、诊断或重算 | 只看文件存在会把损坏条目当命中 |
| `track=False` 资源参数变化 | 结果身份保持不变 | 若结果并非等价，会形成错误复用 |

外部文件内容如果不在 Plugin 配方、受跟踪配置或上游 lineage 中，框架不能自动感知变化。解决方式是
修正输入契约或显式清理缓存，而不是假设文件时间戳总会进入身份。

## 7. 故障原因与诊断

### 检查与诊断

| 现象 | 可能原因 | 验证入口 |
| --- | --- | --- |
| 本应命中却重算 | resolved config、adapter、version、schema 或上游身份变化 | `get_config`、`get_lineage`、执行日志 |
| 本应重算却命中 | 行为未升级 version，或语义配置未跟踪 | Plugin options、version 与缓存元数据 |
| 动态路径错误 | `resolve_depends_on` 读到另一配置来源或依赖不确定状态 | `resolve_dependencies(..., run_id=...)` |
| 依赖查询与实际运行不同 | `compute` 在 DAG 外读取数据，或运行期临时切换来源 | 静态/动态依赖与所有 `get_data` 调用 |
| 磁盘条目损坏或孤立 | 写入中断、checksum 失败、旧元数据遗留 | `waveform-cache diagnose --run <run_id> --dry-run` |
| 清理后仍看到结果 | 清理范围、run 或产物名不一致，或内存项仍在 | `clear_cache_for(run_id, ..., downstream=True)` |

## 8. 维护检查

1. `provides` 唯一且只表达一个正式产物。
2. 静态和动态依赖覆盖 `compute` 的全部正式输入。
3. 动态分支在执行前稳定，并同时进入 DAG 与 lineage。
4. 影响结果的配置受跟踪，纯资源配置才使用 `track=False`。
5. 行为、字段、dtype、默认配置或依赖语义改变时升级 `version`。
6. 冷缓存、部分缓存和热缓存得到相同结果，并产生可解释的执行计划。
7. schema、lineage、动态分支和下游失效均有定向测试。

## 9. 相关专题

- [数据产物与波形访问](DATA_PRODUCTS.md)
- [分析查询与批量运行](ACCESSOR_ANALYSIS.md)
