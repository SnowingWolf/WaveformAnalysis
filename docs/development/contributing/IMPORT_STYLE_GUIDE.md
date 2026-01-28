**导航**: [文档中心](../../README.md) > [development](../README.md) > [开发规范](README.md) > 导入风格指南

---

# 导入风格指南

本文档定义了 WaveformAnalysis 项目的导入规范，确保代码的一致性和可维护性。

---

## 基本原则

### 1. 优先使用绝对导入

**推荐：**
```python
from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.processing.chunk import Chunk
```

**不推荐：**
```python
from ...foundation.utils import exporter
from ...chunk_utils import Chunk
```

### 2. 同一包内可以使用相对导入

**推荐：**
```python
# 在 plugins/core/base.py 中
from .streaming import StreamingPlugin
from waveform_analysis.core.plugins.builtin.cpu import RawFilesPlugin
```

**不推荐：**
```python
from waveform_analysis.core.plugins.core.streaming import StreamingPlugin
```

### 3. 禁止使用超过两级的相对导入

**禁止：**
```python
from ...foundation.utils import exporter  # 三级相对导入
from ....utils import something           # 四级相对导入
```

**允许：**
```python
from .base import Plugin                  # 一级相对导入
from ..foundation.utils import exporter  # 二级相对导入
```

### 4. 类型注解兼容 Python 3.8

**推荐：**
```python
from typing import Union, Optional, Path

def process(path: Union[str, Path]) -> Optional[int]:
    pass
```

**禁止：**
```python
def process(path: str | Path) -> int | None:  # Python 3.10+ 语法
    pass
```

## 导入路径映射表

重构后的导入路径映射：

| 旧路径 | 新路径 |
|--------|--------|
| `waveform_analysis.core.chunk_utils` | `waveform_analysis.core.processing.chunk` |
| `waveform_analysis.core.utils` | `waveform_analysis.core.foundation.utils` |
| `waveform_analysis.core.exceptions` | `waveform_analysis.core.foundation.exceptions` |
| `waveform_analysis.core.mixins` | `waveform_analysis.core.foundation.mixins` |
| `waveform_analysis.core.processor` | `waveform_analysis.core.processing.event_grouping` |
| `waveform_analysis.core.analyzer` | `waveform_analysis.core.processing.analyzer` |
| `waveform_analysis.core.executor_manager` | `waveform_analysis.core.execution.manager` |
| `waveform_analysis.core.executor_config` | `waveform_analysis.core.execution.config` |
| `waveform_analysis.core.storage` | `waveform_analysis.core.storage.memmap` |
| `waveform_analysis.core.cache` | `waveform_analysis.core.storage.cache` |

## 导入顺序规范

按照 PEP 8，导入应按以下顺序：

1. **标准库导入**
   ```python
   import os
   import sys
   from typing import Dict, List
   ```

2. **第三方库导入**
   ```python
   import numpy as np
   import pandas as pd
   ```

3. **本地应用/库导入**
   ```python
   from waveform_analysis.core.foundation.utils import exporter
   from waveform_analysis.core.processing.chunk import Chunk
   ```

## 工具和检查

### 使用 ruff 自动修复

```bash
# 安装
pip install ruff

# 自动修复导入
ruff check --fix waveform_analysis/

# 只检查导入
ruff check --select I waveform_analysis/
```

### 使用检查脚本

```bash
# 检查导入规范
python scripts/check_imports.py

# 自动修复导入问题
python scripts/fix_imports.py --fix

# 只检查不修复
python scripts/fix_imports.py --check
```

### 使用 mypy 检测导入错误

```bash
mypy waveform_analysis/ --show-error-codes
```

## 常见问题

### Q: 什么时候使用相对导入？

**A:** 只在同一包内的文件之间使用相对导入。例如：
- `plugins/core/base.py` → `plugins/core/streaming.py`: 使用 `from .streaming import`
- `plugins/core/base.py` → `plugins/builtin/cpu/standard.py`: 使用 `from waveform_analysis.core.plugins.builtin.cpu import`

### Q: 什么时候使用绝对导入？

**A:** 跨包导入时使用绝对导入。例如：
- `plugins/core/base.py` → `foundation/utils.py`: 使用 `from waveform_analysis.core.foundation.utils import`
- `processing/chunk.py` → `foundation/utils.py`: 使用 `from waveform_analysis.core.foundation.utils import`

### Q: 如何确保导入路径正确？

**A:** 
1. 运行 `python scripts/check_imports.py` 检查
2. 运行 `mypy waveform_analysis/` 检测类型错误
3. 在 CI/CD 中集成检查

## 重构时的最佳实践

1. **使用 IDE 的重构功能**
   - VS Code/Cursor: 右键 → "Move File" 自动更新引用
   - PyCharm: Refactor → Move

2. **使用自动化脚本**
   ```bash
   python scripts/fix_imports.py --fix
   ```

3. **分阶段重构**
   - 先移动文件
   - 运行检查脚本
   - 修复导入路径
   - 运行测试验证

4. **保持向后兼容**
   - 在 `__init__.py` 中添加兼容性导入
   - 使用 `__getattr__` 实现延迟导入

## 示例

### ✅ 正确示例

```python
# 标准库
import os
from typing import Union, Optional, Dict, List

# 第三方库
import numpy as np
import pandas as pd

# 本地库（绝对导入）
from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.processing.chunk import Chunk, get_endtime

# 同一包内（相对导入）
from .base import Plugin
from waveform_analysis.core.plugins.builtin.cpu import RawFilesPlugin
```

### ❌ 错误示例

```python
# 三级相对导入
from ...foundation.utils import exporter

# Python 3.10+ 语法（不兼容 Python 3.8）
def process(path: str | Path) -> int | None:
    pass

# 错误的导入路径（已移动）
from waveform_analysis.core.chunk_utils import Chunk
```

## 相关工具配置

### ruff 配置

已在 `pyproject.toml` 中配置：
- 自动排序导入
- 检测导入错误
- 强制使用绝对导入（跨包）

### mypy 配置

已在 `pyproject.toml` 中配置：
- Python 3.8 兼容性检查
- 导入错误检测

## 更新日志

- 2024: 建立导入规范，统一使用绝对导入
- 2024: 添加 ruff 自动修复支持
- 2024: 添加导入检查脚本
