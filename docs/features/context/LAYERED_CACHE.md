# 分层缓存：共享基础产物与私人分析

当多人对同一个 run 从相同的上游产物出发、使用不同的下游配置时，可以由生产者发布一个不可变的基础快照；每个人各自使用私人缓存继续计算。此功能在当前实现中要求生产者和消费者注册一致的上游插件，并使用匹配的上游配置。它不能把任意目录当作可共享的基础层。

| 场景 | 单目录缓存 | 分层缓存 |
| --- | --- | --- |
| 多人复用相同上游 | 每人维护自己的磁盘副本，或共同写同一个缓存目录 | 发布一次基础快照，每人指定同一 `base` 和各自的 `storage_dir` |
| 修改下游分析 | 相关结果写入该 Context 的缓存目录 | 基础产物固定，下游新结果写入私人目录 |
| 修改已冻结上游 | 新 lineage 可在普通缓存中计算 | 当前快照的上游身份必须匹配；需要重新计算并发布新快照 |
| 发布新版本 | 由使用者自行管理缓存目录 | 每个快照使用新的目标目录；已有使用者可继续固定旧版本 |
| 删除旧版本 | 由目录管理者决定 | 不自动删除；确认没有使用者依赖后由管理者处理 |

## 基本使用

生产者先在普通、可写 Context 中完成生产任务，确认需要共享的边界产物已写入磁盘，再发布到一个新的目标目录。调用方必须保证一起发布的 `records` 与 `wave_pool` 来自同一批次；复制期间的锁保护不能证明磁盘上既有的缓存属于同一批次。消费者用该目录作为 `base`，并将 `storage_dir` 指向自己的可写目录。`run_id` 必须显式传入；一个快照只对应一个 run。

```python
# producer 是已注册相关插件并完成配置的普通 Context。
run_id = "00196"
producer.get_data(run_id, "records")
producer.get_data(run_id, "wave_pool")
producer.publish(run_id, ["records", "wave_pool"], "/shared/wa/run00196-v1")

# 每位消费者注册同样的上游插件、使用匹配的上游配置。
consumer = Context(base="/shared/wa/run00196-v1", storage_dir="/work/alice/wa-cache")
# 按项目的正常方式注册插件并设置配置，然后请求下游产物。
consumer.get_data(run_id, "peaks")
```

这个片段说明真实工作流的边界，省略了项目特定的插件注册和配置，不可直接替代完整分析脚本。[可运行示例](../../../examples/layered_cache.py) 使用合成插件和少量整数，演示生产、发布、两个私人消费者及结果检查：

```bash
python examples/layered_cache.py --output-dir /tmp/wa-layered-demo
```

输出目录必须不存在。示例不读取真实 DAQ，也不代表对 `run00196` 全量事件的验证。

## 配置变化与发布新版本

下面的操作使用示例中的合成插件名称，假设 `base` 是示例的 v1 路径，`RUN` 和 `make_context` 来自 `examples/layered_cache.py`：

```python
# 只改未冻结的下游 scale：两个私人目录可独立得到 [4, 8] 和 [6, 12]。
alice = make_context("/work/alice", base=base, scale=2)
bob = make_context("/work/bob", base=base, scale=3)
print(alice.get_data(RUN, "synthetic_analysis")["value"])
print(bob.get_data(RUN, "synthetic_analysis")["value"])

# records_scale 属于已冻结的上游身份；访问下游时会拒绝，而不是复用私人缓存。
changed = make_context("/work/changed", base=base)
changed.set_config({"records_scale": 2})
try:
    changed.get_data(RUN, "synthetic_analysis")
except ValueError as exc:
    print(f"预期拒绝：{exc}")
else:
    raise AssertionError("冻结上游配置变化未被拒绝")

# 以 v1 为基础发布 v2；v1 路径不变，原使用者可继续使用。
alice.publish(RUN, "synthetic_analysis", "/shared/wa/synthetic-v2")
```

要实际修改冻结上游，应从可写生产者重新计算并发布新版本，不能在已有基础层中覆盖该身份。示例中的 `report.json` 还记录上游计算次数、私人文件大小、旧版本可读性和同文件系统上的文件复用；这些都是合成数据检查。

## 执行机制

- 带 `base` 的请求在私人内存或磁盘缓存命中前校验当前依赖图与涉及的冻结身份。已物化的冻结产物从基础层读取，未物化的冻结节点不能执行；未冻结下游使用私人目录。
- `get_data(run_id, target)` 在使用私人缓存或执行下游插件前检查冻结身份；无法通过身份验证时先修复配置或选择匹配快照，不会重算冻结节点。
- `clone()` 和 `create_context_factory()` 保留基础快照路径；仍应为不同使用者指定各自的私人目录。
- 发布文件设置为只读模式，基础数组以只读 memmap 返回。目录权限或只读挂载还需由管理者设置；插件及用户代码不受 Context 策略沙箱隔离。
- 校验包括元数据、lineage、dtype、run 配置（使用时）和载荷大小，**不计算载荷内容哈希**；这些检查不能证明文件字节内容未被修改。目录权限和外部完整性管理仍由部署方负责。

## 选择边界

`records` 与 `wave_pool` 是正式的 records-backed 波形产物；对 `run00196`，这两个目标可作为从原始数据进入下游处理的首个共享边界。发布它们后，仍可按需在私人目录计算未冻结的下游节点。若希望后续分析直接复用 `peaks` 和 `peaklet_channels`，应先计算并在新快照中包含这些目标；最终所需边界由实际请求的依赖 DAG 决定，可用 `resolve_dependencies(target, run_id=run_id)` 检查。

发布冻结所选目标及其传递依赖的身份；**冻结身份不等于所有祖先都已物化**。未包含磁盘产物的冻结祖先不能在消费者端重算。直接请求缺失的冻结祖先会失败；如需使用，生产者应先物化并发布相应产物。消费者仍需注册与快照匹配的插件及配置，不能只保留目标插件。

## 快照的版本与存储

首次从可写生产者发布时复制产物，快照本身会占用额外空间；共享快照能减少每位消费者重复保存相同上游产物，并不保证总体磁盘占用小于原始数据。后续从已有基础快照发布时，同一文件系统上的基础文件可通过硬链接复用；硬链接与原文件共享 inode，必须把已发布快照视为不可修改。跨文件系统时复制文件，不依赖硬链接节省空间。

- **新增产物**：先在生产者或私人层计算，再发布到新目录，将要共享的目标包含在新快照中。
- **修改上游**：在可写生产者使用新的插件版本或配置重算，发布新目录；切换消费者时同步插件和配置。
- **删除或退役版本**：先确认消费者不再使用旧路径，再由目录管理者处理。发布不会覆盖已有目标，也不会自动清理旧快照。旧消费者固定旧路径时可继续使用它。

通过操作系统目录权限或只读挂载保护共享快照，并给每个消费者单独的私人写目录。Context 的基础层策略是数据访问约定，不能隔离恶意插件、用户代码或直接文件操作；硬链接文件尤其不能通过任一路径原地修改。

## 当前限制与排查

- 目前支持发布已经存在于 MemmapStorage 磁盘上的非空、未压缩 ndarray；不支持 object dtype 或自定义插件后端。内存对象、空数组、其他格式和压缩产物不能直接作为发布载荷。
- 当前发布使用 Linux 的 `renameat2` 完成不覆盖已有目录的安装，依赖该平台及系统调用支持；当前不支持将发布功能视为跨平台接口。
- 请求读取私人缓存前，仍会验证涉及的冻结依赖及其 run、lineage、dtype；依赖使用 run 配置时还会验证 run 配置身份。插件、配置或身份不匹配应先修正，不能靠已有私人结果绕过冻结约束。
- 基础层数组以只读 memmap 返回；私人目录用于下游计算和缓存，基础快照不是通用的可写缓存目录。若请求触及未物化的冻结节点，先在生产者补齐并发布新版本。
- 遇到不匹配时，核对 `run_id`、插件注册和版本、受跟踪配置、输出 dtype、run 配置，以及用于创建该快照的代码环境。不要直接修改已发布文件以消除错误。

详见 [配置管理](CONFIGURATION.md) 和 [Plugin DAG、lineage 与缓存](../../architecture/PLUGIN_DAG_LINEAGE_CACHE.md)。
