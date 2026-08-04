# 插件系统与模板 API

WaveformAnalysis 把每个分析步骤发布为一个唯一命名的数据产物。调用方请求产物，`Context` 根据
`run_id`、注册表和已解析配置构建依赖关系，执行缺失的插件，并由 Storage 按 lineage 保存结果。
插件负责一个产物的计算；Accessor 负责已经计算结果的组合查询；跨 run 的编排属于批量处理器。

## 系统边界与数据流

本节只说明请求和结果如何穿过系统边界；`provides`、`depends_on`、版本和输出字段等插件自身
契约放在下一节，避免把“系统中的一层”和“插件如何声明自己”混为一谈。

```mermaid
flowchart LR
    INPUT["DAQ 文件"] --> ADAPTER["DAQ adapter"]
    ADAPTER --> CONTEXT["Context: run_id、配置、注册表"]
    CONTEXT --> RUNTIME["Plugin runtime: 按 DAG 执行"]
    RUNTIME --> STORAGE["Storage: 保存和加载 lineage"]
    STORAGE --> RESULT["正式数据产物"]
    RESULT --> ACCESSOR["Accessor: 只读查询和组合"]
    BATCH["BatchProcessor: 多个独立 run"] --> CONTEXT
```

| 边界 | 在这一步发生什么 | 不负责什么 |
| --- | --- | --- |
| DAQ adapter | 把文件格式、目录布局、采样率和时间语义转换为统一输入 | 不决定分析算法、插件依赖或缓存键 |
| `Context` | 接收带 `run_id` 的请求，持有注册表，解析配置和依赖并协调执行 | 不实现具体信号算法，也不维护隐式当前 run |
| Plugin runtime | 按 Context 解析出的 DAG 调用插件，并传递已经声明的上游结果 | 不定义插件的输出字段，也不负责交互式组合查询 |
| Storage | 按 run 和 lineage 保存、加载和校验计算结果 | 不定义产物的物理含义，也不替插件决定依赖 |
| Accessor | 组合正式产物，按 ID、时间或通道组织只读查询 | 不发布新的缓存产物，也不重新实现处理算法 |
| `BatchProcessor` | 为多个独立 run 调度同一目标产物并收集结果 | 不把多个 run 合并成一个插件状态 |

一次请求可以概括为：调用方提供 `run_id` 和目标名称，Context 解析配置与 DAG，runtime 执行缺失的
节点，Storage 复用或保存结果，最后由调用方或 Accessor 读取正式产物。插件实例可以被多个 run
复用，因此插件内部的每一次数据访问都必须显式带上 `run_id`。

## Plugin 身份与输出契约

最小插件由四个互相配合的声明组成：`provides` 标识产物，`depends_on` 标识输入，`version` 标识
语义版本，`compute()` 产生实际结果。它们描述的是插件自身的可追踪身份，不是上一节的系统层次。

```python
import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin


class RecordScalePlugin(Plugin):
    # Context 用这个名称查找插件，也把它作为缓存和 lineage 的数据名。
    provides = "record_scale"
    # compute() 会读取 records，因此必须把它声明为上游依赖。
    depends_on = ["records"]
    # 算法、配置语义或输出契约变化时升级版本，旧缓存才不会被误复用。
    version = "1.0.0"
    # 结构化输出的字段和 dtype 是下游可以依赖的公开契约。
    output_dtype = np.dtype([("record_id", "i8"), ("value", "f4")])
    options = {
        # Option 负责默认值、类型和范围检查；实际值由 Context 解析。
        "scale": Option(default=1.0, type=float, min_value=0.0, help="输出缩放系数"),
    }

    def compute(self, context, run_id, **kwargs):
        # 上游数据必须通过显式 run_id 获取，不能依赖隐式当前 run。
        records = context.get_data(run_id, "records")
        # 不直接读取 context.config，统一走配置解析和校验流程。
        scale = context.get_config(self, "scale")
        # 即使 records 为空，也要返回同一 output_dtype 的空数组。
        result = np.empty(len(records), dtype=self.output_dtype)
        result["record_id"] = records["record_id"]
        result["value"] = records["area"] * scale
        return result
```

| 声明 | 运行时含义 | 必须保持的事实 |
| --- | --- | --- |
| `provides` | 结果的全局名称和请求入口 | 同一注册表中唯一，语义变化视为契约变化 |
| `depends_on` | 静态上游产物和 DAG 边 | 只列出 `compute()` 实际读取的产物 |
| `version` | 插件语义版本，参与 lineage | 算法、配置语义、依赖或输出契约变化时升级 |
| `output_dtype` | 结构化 NumPy 输出的字段、类型和顺序 | 实际返回值必须匹配，空输入也返回同一 dtype |
| `output_schema` | 非 ndarray 输出的正式结构 | 用于 list、dict、DataFrame 等非结构化结果 |
| `output_kind` | `static` 或 `stream` | 流式插件返回 chunk 迭代器 |
| `save_when` | `never`、`target` 或 `always` | 只改变持久化时机，不改变产物语义 |

插件只发布一个正式产物。需要把多个产物组合成用户查询结果时，由 Accessor 通过 ID 或索引关系
组织数据，而不是让一个插件同时发布一组互相隐含的结果。

## 注册与配置解析

注册只把插件加入 Context 的注册表，不会立即计算数据。`Context.register()` 接受插件实例、插件类、
插件模块以及嵌套的 list/tuple/set；传入插件类时会自动无参实例化，传入模块时会发现其中的 Plugin
子类。注册阶段会调用 `Plugin.validate()`，并检查 `provides`、依赖格式、`Option`、`save_when`、
`output_kind` 和输出 schema。

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

# Context 保存配置、插件注册表和 Storage；storage_dir 可按项目需要指定。
ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})

# profile 返回一组已经组织好的插件；register() 会逐个加入注册表。
ctx.register(*profiles.cpu_default())

# 自定义插件实例也可以单独注册。此处不会执行 compute()。
record_scale = RecordScalePlugin()
ctx.register(record_scale)

# 查看解析后的配置，再请求目标产物；get_data() 才会按需触发 DAG 执行。
ctx.show_resolved_config("record_scale", verbose=True)
scaled = ctx.get_data("run_001", "record_scale")
```

如果同一个 `provides` 已经注册，默认会拒绝覆盖；只有明确传入 `allow_override=True` 才会替换旧
实现。严格的 `require_spec=True` 还会要求插件提供有效的 `spec()` 或 `SPEC`，适合在插件集成和
发布前检查时使用。注册覆盖或插件版本变化会清理相关执行计划、lineage 和配置缓存。

配置项可以通过类属性 `options`、`@option` 或 `@takes_config` 声明。

### 配置优先级与来源

Context 对一个选项按下面的顺序寻找值，越靠前优先级越高：

1. 插件专属嵌套配置，例如 `{"record_scale": {"scale": 0.5}}`；
2. 点号配置，例如 `{"record_scale.scale": 0.5}`；
3. 共享配置，例如 `{"scale": 0.5}`；
4. 已注册 DAQ adapter 对可推断选项提供的值；
5. `Option.default` 插件默认值。

例如，下面三种显式写法分别对应插件专属、点号和共享配置；同一次运行只需要选择一种，避免让
同一个选项出现多个来源：

```python
ctx = Context(
    config={
        "daq_adapter": "vx2730",
        # 推荐：把插件配置放在 provides 名称下面，最容易定位来源。
        "record_scale": {"scale": 0.5},
        # 等价的点号写法是："record_scale.scale": 0.5
        # 共享写法是："scale": 0.5，但会影响所有同名 option。
    }
)
ctx.register(RecordScalePlugin())

plugin = ctx.get_plugin("record_scale")
scale_value = ctx.get_config_value(plugin, "scale")
print(scale_value.value, scale_value.source, scale_value.original_key)

# 运行中修改配置会清除解析缓存；下一次读取时重新校验并生成新配置身份。
ctx.set_config({"scale": 0.75}, plugin_name="record_scale")
resolved = ctx.get_resolved_config("record_scale")
print(resolved.to_dict())
```

| API | 用途 | 适合什么时候使用 |
| --- | --- | --- |
| `ctx.register(...)` | 加入插件实例、类、模块或插件集 | Context 初始化阶段 |
| `ctx.set_config(...)` | 修改全局或某个插件的原始配置 | 用户选择参数或运行前覆盖默认值 |
| `ctx.get_config(plugin, name)` | 读取已经校验后的单个值 | `compute()` 内部计算 |
| `ctx.get_config_value(plugin, name)` | 同时读取值、来源和原始键名 | 调试优先级、alias 或 adapter 推断 |
| `ctx.get_resolved_config(plugin)` | 获取插件完整的解析配置 | 生成配置快照、比较 lineage |
| `ctx.show_resolved_config(plugin, verbose=True)` | 打印按来源分组的配置 | 人工检查最终生效值 |

显式配置可以在创建 Context 时传入，也可以用 `ctx.set_config(config)` 更新；传入
`plugin_name="record_scale"` 时，更新只写入该插件的配置块。更新后 Context 会清除配置和相关性能
缓存，下次读取时重新解析。配置值经过 `Option` 的类型、choices、范围、单位和自定义校验；旧名称
alias 如果存在，会先规范化为当前选项名。

```python
from waveform_analysis.core.plugins.core.base import Option, option, takes_config


@option("threshold", default=12.0, type=float, min_value=0.0)
@takes_config({"mode": Option(default="standard", choices=["standard", "strict"])})
class ConfiguredPlugin(Plugin):
    provides = "configured_output"
    depends_on = []

    def compute(self, context, run_id, **kwargs):
        # get_config() 返回已经完成类型、范围和单位处理的值。
        threshold = context.get_config(self, "threshold")
        mode = context.get_config(self, "mode")
        return self._compute(threshold, mode)
```

插件内部使用 `context.get_config(self, name)` 只取值；需要判断值从哪里来时使用
`context.get_config_value(self, name)`，它返回值、来源、原始键名和规范键名。需要一次查看插件
全部配置时使用 `ctx.get_resolved_config("record_scale")`，可编程读取 `to_dict()`，或者使用
`ctx.show_resolved_config("record_scale", verbose=True)` 查看 explicit、adapter inferred 和默认值
分组。`track=False` 的选项不会进入用于 lineage 的配置快照，适合只影响日志或执行细节而不改变结果
语义的参数；会改变结果的选项应保持默认的 `track=True`。

## 依赖解析与 lineage

静态依赖来自类属性；动态依赖覆盖 `resolve_depends_on(context, run_id=None)`。动态解析器的返回值
就是本次运行的实际输入边，Context 会在构建执行计划、检查版本约束和计算 lineage 时使用同一结果。

```mermaid
flowchart TD
    REQUEST["ctx.get_data(run_id, target)"] --> PRODUCER["查找 target 的 Plugin"]
    PRODUCER --> STATIC{"静态依赖?"}
    STATIC -->|是| DEPS["读取 depends_on"]
    STATIC -->|否| RESOLVE["调用 resolve_depends_on: 配置 + run_id"]
    DEPS --> LINEAGE["合并上游 lineage"]
    RESOLVE --> LINEAGE
    LINEAGE --> ID["Plugin 版本、代码、配置、输出契约"]
    ID --> CACHE{"Storage 中身份匹配?"}
    CACHE -->|命中| LOAD["加载正式产物"]
    CACHE -->|缺失或失效| COMPUTE["拓扑顺序执行"]
    COMPUTE --> SAVE["保存新 lineage 和产物"]
    SAVE --> LOAD
```

动态插件应保持 `depends_on = []`，并让解析器返回所有 `compute()` 会读取的上游：

```python
class ChannelFeaturePlugin(Plugin):
    provides = "channel_features"
    depends_on = []
    version = "1.0.0"
    options = {"use_filtered": Option(default=False, type=bool)}

    def resolve_depends_on(self, context, run_id=None):
        source = "wave_pool_filtered" if context.get_config(self, "use_filtered") else "wave_pool"
        return ["records", source]

    def compute(self, context, run_id, **kwargs):
        records = context.get_data(run_id, "records")
        source = self.resolve_depends_on(context, run_id)[1]
        waves = context.get_data(run_id, source)
        return self._build_features(records, waves)
```

解析器不能读取临时文件、随机值或可变全局状态；同一配置和 run 必须返回同一依赖集合。静态依赖和
动态解析器同时存在时，注册校验会发出警告，因为两套来源无法准确表达实际 DAG。

| 现象 | 当前实现中的原因 | 排查方向 |
| --- | --- | --- |
| 注册时报 `provides` 冲突 | 两个插件声明了同一个产物名称 | 保留唯一生产者，或显式替换插件 |
| 动态结果反复重算 | 解析结果、版本、配置或输出契约改变 | 检查 `resolve_depends_on()`、`track` 和版本 |
| 依赖缺失或执行顺序错误 | `compute()` 读取了未声明产物 | 把所有读取加入静态或动态依赖返回值 |
| 缓存文件存在但未命中 | 文件的 lineage 与当前身份不一致 | 检查插件版本、代码、配置、dtype 和上游 lineage |

## Plugin 内部数据获取与生命周期

`compute(context, run_id, **kwargs)` 是普通插件唯一必须实现的计算入口。上游依赖由 Context 提前
解析，插件通过 `context.get_data(run_id, dependency)` 获取正式产物，通过 `context.get_config(self,
key)` 获取配置。插件不应保存跨 run 数据，也不应使用隐式“当前 run”。

返回值必须匹配 `output_dtype` 或 `output_schema`。空输入返回同一契约的空结果；`None`、临时字段或
不同 dtype 都会让下游和缓存身份失去确定性。

`on_error(context, exception)` 用于记录或释放计算失败时的诊断资源，不能吞掉异常或写入伪造成功结果。
`cleanup(context)` 在成功、失败和取消路径的 `finally` 阶段执行，适合关闭文件、临时缓冲区和设备会话。
清理失败只记录警告，不覆盖原始计算异常，因此清理函数必须幂等。

## Chunk Plugin：流式与批量计算

`Chunk` 封装一段数据及其半开时间范围 `[start, end)`。构造时会检查数据起点不早于 `start`，并检查
每条记录的结束时间不超过 `end`。这使相邻 chunk 可以拼接，也使边界越界在计算后立即暴露。

```mermaid
flowchart LR
    INPUT["静态 ndarray 或上游 chunk 流"] --> SPLIT["按 chunk_size 切分"]
    SPLIT --> HALO["可选 halo 与 break 分段"]
    HALO --> COMPUTE["compute_chunk(chunk)"]
    COMPUTE --> POST["包装结果并裁剪 main_start/main_end"]
    POST --> CHECK["校验 endtime <= chunk.end"]
    CHECK --> EXEC{"parallel?"}
    EXEC -->|线程/进程| ORDER["批量提交，按输入顺序回收"]
    EXEC -->|串行| ORDER
    ORDER --> OUTPUT["输出 chunk 流"]
```

### `StreamingPlugin`

继承 `StreamingPlugin` 的插件实现 `compute_chunk(chunk, context, run_id, **kwargs)`。基类会：

1. 从第一个已解析依赖获取输入流；已有迭代器直接传递，静态 ndarray 按 `chunk_size` 转为 chunk。
2. 根据 `break_threshold_ps` 切分不连续时间段，并用 `required_halo_ns` 扩展边界上下文。
3. 调用 `compute_chunk()`，把普通 ndarray 包装为输出 `Chunk`。
4. 按 `main_start`/`main_end` 裁剪 halo 产生的重复区域，再验证时间边界。
5. 在并行模式下分批提交任务并保持输出顺序；不可 pickle 的进程任务回退到线程执行器。

```python
from waveform_analysis.core.plugins.core.streaming import StreamingPlugin
from waveform_analysis.core.processing.chunk import Chunk


class ThresholdStreamPlugin(StreamingPlugin):
    provides = "threshold_hits"
    depends_on = ["st_waveforms"]
    chunk_size = 50_000
    parallel = True

    def compute_chunk(self, chunk: Chunk, context, run_id, **kwargs):
        hits = detect_threshold(chunk.data)
        return Chunk(
            data=hits,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
            time_field=chunk.time_field,
            dt_field=chunk.dt_field,
            length_field=chunk.length_field,
            endtime_field=chunk.endtime_field,
            dt=chunk.dt,
        )
```

有状态插件必须保持输入顺序；当 `is_stateful=True` 且 `parallel=True` 时，运行时会警告并退回串行，
在 break 分段切换时按 `reset_on_break` 重置状态。需要跨 chunk 上下文时，应使用 halo 或显式状态协议，
不能依赖任务提交顺序以外的全局变量。

### `BatchProcessingPlugin`

`BatchProcessingPlugin` 是面向有限大数据集的 `StreamingPlugin` 语义封装。它默认使用 `chunk_size=50000`、
线程执行器和并行处理，子类实现 `compute_chunk()`；基类的 `compute()` 仍然返回 chunk 流。

```python
import numpy as np

from waveform_analysis.core.plugins.core.batch_processing import BatchProcessingPlugin
from waveform_analysis.core.processing.chunk import Chunk


class AreaBatchPlugin(BatchProcessingPlugin):
    provides = "area_features"
    depends_on = ["st_waveforms"]
    output_dtype = np.dtype([("time", "i8"), ("area", "f4")])
    chunk_size = 10_000

    def compute_chunk(self, chunk: Chunk, context, run_id, **kwargs):
        result = np.empty(len(chunk.data), dtype=self.output_dtype)
        result["time"] = chunk.data["timestamp"]
        result["area"] = integrate_waveforms(chunk.data)
        return Chunk(
            data=result,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
            time_field="time",
        )
```

`compute_array()` 是向后兼容的完整数组接口：它要求恰好一个输入依赖，逐块调用 `compute_chunk()`，
再合并非空结果。多个输入依赖、非 NumPy 结构化输入或越过 chunk 边界的输出会直接失败，原因是该接口
无法为多个来源推断单一的切块和合并语义。

## 失败模式与测试要求

| 约束 | 失败原因 | 最小测试 |
| --- | --- | --- |
| 唯一 `provides` | 注册表出现两个生产者 | 注册冲突测试 |
| 显式 `run_id` | 不同 run 共用内存或缓存 | 两个 run 顺序访问并比较 lineage |
| 输出契约稳定 | 返回 dtype、字段或空结果不一致 | 正常输入和空输入测试 |
| 动态依赖确定 | 同一配置返回不同上游 | 覆盖每个分支并重复解析 |
| chunk 边界合法 | 记录结束时间超过 chunk.end | 构造越界 Chunk 并断言失败 |
| 状态顺序保持 | 并行执行改变状态演化 | `is_stateful` 自动串行测试 |
| 配置进入 lineage | 结果参数被标记为 `track=False` | 改变配置并比较缓存身份 |

提交插件前还应验证：无效 option、缺失输入、不支持 adapter、进程 executor 的不可 pickle 回退、
`on_error()`/`cleanup()` 生命周期，以及内置插件参考页中的配置、输出字段和依赖是否同步。

交互式插件 DAG 仍可从站点的独立 DAG 工具查看；本页只保留依赖解析和执行所需的事实，不重复描述独立
可视化工具的使用方式。
