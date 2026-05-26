# 迁移指南 (MIGRATION GUIDE)

**导航**: [文档中心](README.md) > 迁移指南

本文档提供 WaveformAnalysis 版本升级的详细指南，帮助你平滑迁移到新版本。

---

## 目录

- [最新变更 (2026-01)](#最新变更-2026-01)
- [存储系统迁移](#存储系统迁移)
- [数据类型迁移](#数据类型迁移)
- [API 变更](#api-变更)
- [配置变更](#配置变更)
- [兼容性矩阵](#兼容性矩阵)

---

## 最新变更 (2026-01)

### hit 字段重命名: event_index → record_id

**影响版本**: 2026-01+

#### 变更说明

`hit` 相关数据类型中的 `event_index` 字段重命名为 `record_id`，以更准确地反映其语义（指向原始 record 的 ID）。

#### 迁移步骤

**1. 更新字段访问**

```python
# 旧代码
hit_event_idx = hits['event_index']
df_event_idx = df['event_index']

# 新代码
hit_record_id = hits['record_id']
df_record_id = df['record_id']
```

**2. 更新过滤条件**

```python
# 旧代码
filtered = hits[hits['event_index'] > 100]

# 新代码
filtered = hits[hits['record_id'] > 100]
```

**3. 更新自定义插件**

如果你的插件依赖 `event_index` 字段：

```python
# 旧插件
class MyPlugin(Plugin):
    depends_on = ('hits',)

    def compute(self, hits):
        event_indices = hits['event_index']
        # ...

# 新插件
class MyPlugin(Plugin):
    depends_on = ('hits',)

    def compute(self, hits):
        record_ids = hits['record_id']
        # ...
```

#### 向后兼容

- 旧数据文件仍可读取，系统会自动映射字段名
- 建议重新生成数据以使用新字段名

#### 相关提交

- `e1a93c6`: 重命名 event_index 为 record_id

---

### basic_features 新增 max_abs_diff 字段

**影响版本**: 2026-01+

#### 变更说明

`basic_features` 和 `dataframe` 数据类型新增 `max_abs_diff` 字段，提供波形最大绝对差值信息。

#### 迁移步骤

**无需迁移**，这是向后兼容的新增功能。

**使用新字段**:

```python
# 获取数据
features = ctx.get_array(run_id='run_001', targets='basic_features')

# 访问新字段
max_diffs = features['max_abs_diff']

# 在 DataFrame 中使用
df = ctx.get_df(run_id='run_001', targets='basic_features')
print(df['max_abs_diff'].describe())
```

#### 相关提交

- `31bd27c`: 添加 max_abs_diff 到 basic_features 和 dataframe

---

### records 处理优化 (2TB+ 数据集支持)

**影响版本**: 2026-01+

#### 变更说明

重构 records 处理流程，引入 `RecordsBundleRef` 用于流式处理 2TB+ 数据集。这是内部实现变更，外部 API 保持兼容。

#### 迁移步骤

**无需迁移**，API 保持不变。

**性能提升**:
- 大数据集处理速度显著提升
- 内存占用更低
- 支持流式处理

#### 相关提交

- `ac9f6e3`: Phase 1 - 优化 V1725 处理
- `ee2634a`: Phase 2 - 添加批量合并
- `8834e49`: Phase 3 - 引入 RecordsBundleRef

---

## 存储系统迁移

详见 [存储迁移指南](updates/STORAGE_MIGRATION_GUIDE.md)

### MemmapStorage 统一分层存储

**影响版本**: 2026-01+

#### 变更说明

`MemmapStorage` 移除了 legacy 扁平存储模式，统一使用分层存储结构（按 run_id 组织）。

#### 迁移步骤

**1. 更新初始化代码**

```python
# 旧代码
storage = MemmapStorage(base_dir="./data")

# 新代码
storage = MemmapStorage(work_dir="./data")
```

**2. 所有操作需要 run_id**

```python
# 旧代码（扁平模式）
storage.save_memmap("my_key", data)
loaded = storage.load_memmap("my_key")

# 新代码（分层模式）
storage.save_memmap("my_key", data, run_id="run_001")
loaded = storage.load_memmap("my_key", run_id="run_001")
```

**3. 存储路径变更**

```
旧路径: ./data/my_key.bin
新路径: ./data/run_001/my_key.bin
```

#### 迁移现有数据

```python
import os
import shutil
from waveform_analysis import MemmapStorage

# 1. 创建新存储
new_storage = MemmapStorage(work_dir="./data_new")

# 2. 迁移数据
old_dir = "./data"
run_id = "run_001"

for filename in os.listdir(old_dir):
    if filename.endswith('.bin'):
        key = filename[:-4]  # 移除 .bin

        # 加载旧数据
        old_path = os.path.join(old_dir, filename)
        data = np.load(old_path, mmap_mode='r')

        # 保存到新存储
        new_storage.save_memmap(key, data, run_id=run_id)

print("迁移完成")
```

#### 向后兼容

- 旧代码在新版本中会报错，必须更新
- 建议使用迁移脚本批量转换数据

---

## 数据类型迁移

详见 [数据类型迁移清单](updates/DT_MIGRATION_TAILLIST.md)

### 采样间隔字段统一: dt

**影响版本**: 2025-2026

#### 变更说明

采样间隔相关字段统一使用 `dt` 命名，替代旧的 `dt_ns`、`sampling_interval_ns` 等变体。

#### 迁移步骤

**1. 配置键更新**

```python
# 旧配置
ctx.set_config({
    'dt_ns': 2,
    'events_dt_ns': 2,
    'records_dt_ns': 2
})

# 新配置
ctx.set_config({
    'dt': 2,
    'events_dt': 2,
    'records_dt': 2
})
```

**2. 数据字段访问**

```python
# 旧代码
dt_value = record['dt_ns']

# 新代码
dt_value = record['dt']
```

#### 兼容保留

以下位置仍保留旧术语，用于向后兼容：

- **preview 工具 API**: `sampling_interval_ns` 参数
- **配置兼容层**: 自动映射 `dt_ns` → `dt`
- **兼容测试**: 测试旧键覆盖

#### 建议

- 新代码使用 `dt`
- 旧代码可继续使用旧键（通过兼容层自动映射）
- 计划在未来版本移除兼容层

---

## API 变更

### Context 初始化参数

**影响版本**: 2025-2026

#### 变更说明

`Context` 初始化参数优化，推荐使用 `work_dir` 替代 `storage_dir`。

#### 迁移步骤

```python
# 旧代码
ctx = Context(storage_dir='./strax_data')

# 新代码（推荐）
ctx = Context(work_dir='./strax_data')

# 或使用自定义存储
from waveform_analysis import MemmapStorage
storage = MemmapStorage(work_dir='./strax_data')
ctx = Context(storage=storage)
```

#### 向后兼容

- `storage_dir` 参数仍然支持
- 建议新代码使用 `work_dir` 或 `storage`

---

### 插件 dtype 定义

**影响版本**: 2025-2026

#### 变更说明

插件 dtype 定义推荐使用三元组格式 `(name, type, help)`，提供更好的文档支持。

#### 迁移步骤

```python
# 旧格式（仍支持）
dtype = [
    ('time', np.int64),
    ('channel', np.int16),
    ('area', np.float32)
]

# 新格式（推荐）
dtype = [
    ('time', np.int64, '时间戳 (ns)'),
    ('channel', np.int16, '通道号'),
    ('area', np.float32, '积分面积')
]
```

#### 向后兼容

- 两种格式都支持
- 新格式提供更好的自动文档生成

---

## 配置变更

### 命名规范统一

**影响版本**: 2025-2026

#### 变更说明

配置键命名规范统一，推荐使用 snake_case。

#### 常见配置键映射

| 旧键 | 新键 | 说明 |
|------|------|------|
| `dt_ns` | `dt` | 采样间隔 |
| `events_dt_ns` | `events_dt` | 事件采样间隔 |
| `records_dt_ns` | `records_dt` | 记录采样间隔 |
| `sampleRate` | `sample_rate` | 采样率 |
| `baselineSamples` | `baseline_samples` | 基线样本数 |

#### 迁移步骤

```python
# 旧配置
ctx.set_config({
    'dt_ns': 2,
    'sampleRate': 1000,
    'baselineSamples': 100
})

# 新配置
ctx.set_config({
    'dt': 2,
    'sample_rate': 1000,
    'baseline_samples': 100
})
```

#### 向后兼容

- 配置兼容层自动映射旧键到新键
- 建议更新配置文件使用新键

---

## 兼容性矩阵

### Python 版本

| WaveformAnalysis 版本 | Python 版本 | 状态 |
|----------------------|-------------|------|
| 最新版 | 3.10+ | ✅ 支持 |
| 最新版 | 3.9 | ⚠️ 部分支持 |
| 最新版 | 3.8 及以下 | ❌ 不支持 |

### 依赖版本

| 依赖 | 最低版本 | 推荐版本 | 说明 |
|------|----------|----------|------|
| numpy | 1.20.0 | 1.24+ | 核心数组处理 |
| pandas | 1.3.0 | 2.0+ | DataFrame 支持 |
| pyarrow | 10.0.0 | 14.0+ | 高性能 CSV/Parquet |
| scipy | 1.7.0 | 1.11+ | 信号处理 |
| matplotlib | 3.4.0 | 3.7+ | 可视化（可选） |

### 数据格式兼容性

| 格式 | 读取 | 写入 | 说明 |
|------|------|------|------|
| Memmap (新) | ✅ | ✅ | 推荐格式 |
| Parquet | ✅ | ✅ | DataFrame 格式 |
| Pickle (旧) | ✅ | ⚠️ | 仅兼容读取 |
| CSV | ✅ | ✅ | 原始数据 |

---

## 迁移检查清单

### 升级到最新版本

- [ ] 检查 Python 版本 (≥3.10)
- [ ] 更新依赖包 (`pip install -U waveform-analysis`)
- [ ] 阅读 [变更日志](CHANGELOG.md)
- [ ] 备份现有数据和配置

### 代码更新

- [ ] 更新 `event_index` → `record_id`
- [ ] 更新 `MemmapStorage` 初始化
- [ ] 更新配置键 (`dt_ns` → `dt`)
- [ ] 更新插件 dtype 定义（可选）

### 数据迁移

- [ ] 迁移 MemmapStorage 数据（如使用）
- [ ] 重新生成缓存数据
- [ ] 验证数据完整性

### 测试验证

- [ ] 运行单元测试
- [ ] 验证数据处理流程
- [ ] 检查性能指标
- [ ] 验证输出结果

---

## 获取帮助

### 文档资源

- [变更日志](CHANGELOG.md) - 详细变更记录
- [更新记录](updates/README.md) - 专题更新文档
- [API 参考](api/README.md) - API 文档
- [AGENTS.md](../AGENTS.md) - 主入口与硬约束

### 常见问题

**Q: 升级后旧数据无法读取怎么办？**

A: 大多数情况下系统会自动兼容。如果遇到问题：
1. 检查是否使用了废弃的存储格式
2. 参考对应的迁移指南进行数据转换
3. 如果问题持续，请提交 issue

**Q: 配置键改名后旧配置文件还能用吗？**

A: 可以。配置兼容层会自动映射旧键到新键。但建议更新配置文件使用新键，以便未来兼容层移除后仍能正常工作。

**Q: 如何确认迁移是否成功？**

A: 运行以下检查：
```python
# 1. 检查数据读取
data = ctx.get_array(run_id='run_001', targets='records')
print(f"读取成功: {len(data)} 条记录")

# 2. 检查字段名
if 'record_id' in data.dtype.names:
    print("✅ 字段名已更新")

# 3. 检查配置
print(f"配置: {ctx.config}")
```

**Q: 迁移过程中遇到错误怎么办？**

A:
1. 查看错误信息，确认是哪个步骤失败
2. 参考本指南的对应章节
3. 检查 [变更日志](CHANGELOG.md) 中的相关说明
4. 如果无法解决，请提交 issue 并附上错误信息

---

## 贡献

发现迁移问题或有改进建议？请查看 [贡献指南](development/contributing/README.md)。
