# 缓存与 Lineage 系统

本项目采用基于 **Lineage Hashing** 和 **numpy.memmap** 的高性能缓存系统。

## 核心机制

### 1. Lineage Hashing (血缘追踪)

每个数据对象（如 `hits`）都有一个唯一的 Lineage。Lineage 是一个字典，包含了生成该数据所需的所有信息：
- **Plugin**: 插件的类名。
- **Version**: 插件的版本号。
- **Config**: 插件及其所有上游插件的配置参数。
- **DType**: 插件输出的标准化数据类型（使用 `dtype.descr` 列表，消除跨版本差异）。
- **Dependencies**: 上游数据的 Lineage。

系统将 Lineage 序列化并计算 SHA1 哈希值，作为缓存文件的唯一标识。

**优势**: 
- **自动失效**: 修改任何配置（如 `threshold`）、升级插件版本或更改 DType 定义，哈希值都会改变，系统会自动重新计算，避免使用过期数据。
- **确定性**: 相同的配置和代码永远指向相同的缓存文件。
- **血缘校验**: 加载缓存时，系统会读取元数据中的 `lineage` 并与当前逻辑生成的 `lineage` 进行深度对比。若不匹配，将触发 `UserWarning` 并强制重算。

### 2. Memmap 存储 (零拷贝访问)

对于结构化数组（如 `hits`），系统使用 `numpy.memmap` 进行存储：
- **原子性写入**: 数据先写入 `.tmp` 文件，成功后才重命名为 `.bin`，防止因程序崩溃导致缓存损坏。
- **按需加载**: 数据保存在磁盘上，只有在访问特定行时才加载到内存。
- **超大数据支持**: 可以处理远超内存容量的数据集。
- **极速启动**: 加载缓存几乎是瞬时的，因为只是建立了文件映射。

## 缓存目录结构

缓存默认保存在 `storage_dir`（默认为 `./strax_data`）下：

```text
strax_data/
├── run_001-hits-abc12345.bin      # 二进制数据 (memmap)
├── run_001-hits-abc12345.json     # 元数据 (dtype, lineage, count)
└── _side_effects/                 # 侧效应插件输出 (绘图, 导出等)
    └── run_001/
        └── my_plot_plugin/
            └── plot.png
```

## 使用示例

### 检查缓存状态

```python
from waveform_analysis.core.context import Context

ctx = Context(storage_dir="./strax_data")
# ... 注册插件 ...

# 检查数据是否已缓存
is_cached = ctx.is_cached("run_001", "hits")
print(f"Is hits cached? {is_cached}")

# 获取数据（如果已缓存则直接 memmap 加载，否则计算并保存）
hits = ctx.get_data("run_001", "hits")
```

### 强制重新计算

如果需要忽略缓存强制重新计算，可以手动删除对应的缓存文件，或者在 `get_data` 时传入特定参数（如果未来版本支持）。目前建议通过修改配置或删除文件来实现。

## 注意事项

- **DType 一致性**: 插件必须定义 `dtype` 属性，以便 `MemmapStorage` 正确解析二进制文件。
- **并发安全**: 目前版本未实现跨进程的文件锁，建议避免多个进程同时写入同一个 Run 的同一个数据。

加载行为

- 当 `persist_path` 指定且文件存在时，加载过程会：
  1. 反序列化缓存文件（pickle）。
  2. 若配置了 `watch_attrs` 并且缓存中存在 `WATCH_SIG_KEY`，计算当前签名并与缓存内签名比较。若不同则视为 cache miss 并继续执行步骤；若相同则恢复 `attrs` 并跳过步骤执行。
  3. 若没有配置 `watch_attrs` 或缓存中不包含签名，则直接恢复全部保存的 `attrs`（老行为）。

CI 与实践建议

- 在 CI 中运行测试时，避免将持久化缓存路径写入版本控制或 CI 工作区的长期位置。推荐使用 `tmp_path`/workspace 的临时目录并在 job 结束时清理。
- 为提高 CI 速度，可在 CI 中缓存依赖和测试生成的数据，但不要缓存会导致非确定性行为的文件。把持久化缓存作为测试产物上传仅用于调试（不要作为测试通过的依据）。

- 推荐覆盖点（测试用例）：
  - 持久化缓存创建与读取
  - 当 `watch_attrs` 标记的文件被修改时，持久化缓存应作废并被覆盖
  - 内存缓存的启用/禁用行为

- GitHub Actions CI 示例（简化）：

```yaml
name: Python tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install deps
        run: python -m pip install -r requirements.txt
      - name: Run tests
        run: pytest -q
      - name: Upload test artifacts (optional)
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: test-output
          path: .pytest_cache
```

实践小贴士

- 当使用网络文件系统或共享存储时，mtime 精度或延迟可能导致签名检测失败；在这类环境中，可以通过增加 `watch_attrs` 中更直接的内容（例如文件 hash）或把签名策略调整为只检测文件名列表来降低误判率。
- 如果你希望在多个进程/节点间共享持久化缓存，请确保文件写入具有原子性（例如写入临时文件后重命名），以避免竞争条件。

常见问题

- Q: 我可以把持久化缓存文件提交到仓库以加速 CI 吗？
  - A: 不建议这样做。持久化缓存可能依赖于本地路径、mtime 或环境差异，提交会导致不可预测的结果。CI 可在需要时生成并缓存依赖/构建产物，但应对缓存过时保持谨慎。

如需更详细示例或将签名策略改为文件内容哈希（而非 size/mtime），我可以继续实现并添加可配置选项。
# 缓存接口与 WATCH_SIG_KEY 说明

本项目在 `WaveformDataset` 提供了步骤级缓存（内存与可选磁盘持久化），用于缓存诸如 `st_waveforms`、`event_len` 等耗时计算结果。

关键点：

- 用户可通过 `ds.set_step_cache(step_name, enabled=True, attrs=[...], persist_path=..., watch_attrs=[...])` 启用缓存。
- 当配置 `watch_attrs` 时，数据集会基于这些属性计算一个轻量级签名（SHA1），并在持久化缓存时将其写入缓存文件中，用以检测外部文件的变更。
- 签名键已统一为模块常量 `WATCH_SIG_KEY`，可从包顶层导入：

```python
from waveform_analysis import WATCH_SIG_KEY
```

- `WATCH_SIG_KEY` 的值为 `"__watch_sig__"`，并写入持久化 cache 文件中的键名，用于标注保存的签名。

示例：

```python
ds.set_step_cache("load_raw_data", enabled=True, attrs=["raw_files"], persist_path="/tmp/load_cache.pkl", watch_attrs=["raw_files"])
ds.load_raw_data()
```

若缓存文件中包含 `WATCH_SIG_KEY`，在加载时会和当前计算的签名比较；若不一致则视为 cache miss，重新执行步骤并覆盖缓存文件。

注意事项与最佳实践：
- `watch_attrs` 应包含可能变化的文件路径或会影响步骤输出的重要属性（如 `raw_files`）。
- 签名聚合会尝试从字符串、列表或 dict 中提取路径和文件大小/mtime 信息，因此确保 `watch_attrs` 的值能以某种形式包含文件路径。
- 若环境对时间精度敏感（e.g. 网络文件系统），在某些极端情况下需要额外的缓存失效策略。
