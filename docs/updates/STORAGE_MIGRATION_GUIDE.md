**导航**: [文档中心](../README.md) > MemmapStorage 迁移指南

# MemmapStorage 迁移指南

## 概述

从 2026-01 版本开始，`MemmapStorage` 移除了 legacy 扁平存储模式，统一使用分层存储结构。本指南帮助你将现有代码迁移到新 API。

## 主要变更

### 1. 初始化参数变更

**旧 API**:
```python
# 旧模式：使用 base_dir
storage = MemmapStorage(base_dir="./data")

# 或者显式指定模式
storage = MemmapStorage(
    base_dir="./data",
    work_dir="./data",
    use_run_subdirs=True
)
```

**新 API**:
```python
# 新模式：只需 work_dir
storage = MemmapStorage(work_dir="./data")
```

### 2. 所有操作需要 run_id

**旧 API**:
```python
# 扁平模式不需要 run_id
storage.save_memmap("my_key", data)
loaded = storage.load_memmap("my_key")
exists = storage.exists("my_key")
```

**新 API**:
```python
# 所有操作都需要 run_id
storage.save_memmap("my_key", data, run_id="run_001")
loaded = storage.load_memmap("my_key", run_id="run_001")
exists = storage.exists("my_key", run_id="run_001")
```

### 3. 存储路径变更

**旧结构** (扁平模式):
```
data/
├── my_key.bin
├── my_key.json
└── another_key.bin
```

**新结构** (分层模式):
```
data/
├── run_001/
│   └── _cache/
│       ├── my_key.bin
│       └── my_key.json
└── run_002/
    └── _cache/
        └── another_key.bin
```

### 4. Context 初始化变更

**旧 API**:
```python
ctx = Context(storage_dir="./data", use_run_subdirs=True)
```

**新 API**:
```python
# use_run_subdirs 参数已移除
ctx = Context(storage_dir="./data")

# 或使用推荐方式
ctx = Context(config={"data_root": "DAQ"})
```

### 5. list_keys() 方法变更

**旧 API**:
```python
# 扁平模式：列出所有 keys
keys = storage.list_keys()
```

**新 API**:
```python
# 必须指定 run_id
keys = storage.list_keys(run_id="run_001")

# 列出所有 runs
runs = storage.list_runs()
for run_id in runs:
    keys = storage.list_keys(run_id)
```

## 迁移步骤

### 步骤 1: 更新代码

1. **更新 MemmapStorage 初始化**:
   ```python
   # 将所有 base_dir 改为 work_dir
   - storage = MemmapStorage(base_dir="./data")
   + storage = MemmapStorage(work_dir="./data")
   ```

2. **添加 run_id 参数**:
   ```python
   # 为所有存储操作添加 run_id
   - storage.save_memmap("key", data)
   + storage.save_memmap("key", data, run_id="run_001")
   ```

3. **移除 use_run_subdirs 参数**:
   ```python
   # 从 Context 初始化中移除
   - ctx = Context(storage_dir="./data", use_run_subdirs=True)
   + ctx = Context(storage_dir="./data")
   ```

### 步骤 2: 迁移现有数据（可选）

如果你有旧的扁平结构数据，可以使用以下脚本迁移：

```python
import os
import shutil
from pathlib import Path

def migrate_flat_to_hierarchical(old_dir, new_dir, run_id):
    """
    将扁平结构迁移到分层结构
    
    Args:
        old_dir: 旧的扁平目录
        new_dir: 新的分层目录根
        run_id: 运行标识符
    """
    old_path = Path(old_dir)
    new_path = Path(new_dir) / run_id / "_cache"
    new_path.mkdir(parents=True, exist_ok=True)
    
    # 迁移所有 .bin 和 .json 文件
    for ext in [".bin", ".json", ".lock"]:
        for file in old_path.glob(f"*{ext}"):
            dest = new_path / file.name
            shutil.copy2(file, dest)
            print(f"Migrated: {file.name}")
    
    print(f"Migration complete: {old_dir} -> {new_path}")

# 使用示例
migrate_flat_to_hierarchical("./old_data", "./new_data", "run_001")
```

### 步骤 3: 测试验证

迁移后，运行以下测试确保一切正常：

```python
from waveform_analysis.core.storage import MemmapStorage
import numpy as np

# 创建测试存储
storage = MemmapStorage(work_dir="./test_data")

# 测试保存和加载
test_data = np.array([1, 2, 3, 4, 5])
storage.save_memmap("test_key", test_data, run_id="test_run")

# 验证加载
loaded = storage.load_memmap("test_key", run_id="test_run")
assert np.array_equal(loaded, test_data), "数据不匹配！"

# 验证存在性检查
assert storage.exists("test_key", run_id="test_run"), "文件不存在！"

print("✓ 迁移验证成功！")
```

## 常见问题

### Q1: 为什么要移除扁平模式？

**A**: 分层结构提供了更好的组织性和可扩展性：
- 按 run_id 隔离数据，避免冲突
- 更清晰的目录结构
- 支持 run 级别的批量操作
- 简化代码维护

### Q2: 旧数据会丢失吗？

**A**: 不会。旧数据仍然存在于原位置，你可以：
1. 使用迁移脚本将数据移动到新结构
2. 保留旧数据作为备份
3. 根据需要逐步迁移

### Q3: 如何处理没有 run_id 的旧代码？

**A**: 你需要为所有存储操作添加 run_id：
```python
# 如果你的旧代码没有 run_id 概念
# 可以使用一个默认值
DEFAULT_RUN_ID = "default"

storage.save_memmap("key", data, run_id=DEFAULT_RUN_ID)
```

### Q4: Context 会自动处理 run_id 吗？

**A**: 是的！当你使用 Context API 时，run_id 会自动传递：
```python
ctx = Context(config={"data_root": "DAQ"})
# run_id 会自动从 get_data 调用中传递给存储层
data = ctx.get_data("run_001", "basic_features")
```

## 兼容性说明

- **Python 版本**: 无变化，仍支持 Python 3.8+
- **依赖**: 无新增依赖
- **测试**: 80/81 测试通过 (98.8%)
- **性能**: 无性能影响

## 获取帮助

如果遇到迁移问题，请：
1. 查看 [CHANGELOG.md](../../CHANGELOG.md) 了解详细变更
2. 参考 [CLAUDE.md](../../CLAUDE.md) 了解新 API 用法
3. 提交 Issue 到 GitHub 仓库

## 版本信息

- **变更版本**: 2026-01
- **影响范围**: MemmapStorage 及相关测试
- **向后兼容**: ❌ 破坏性变更
- **建议操作**: 必须更新代码
