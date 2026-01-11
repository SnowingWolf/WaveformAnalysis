# 🛠️ 开发指南索引

**导航**: [文档中心](../README.md) > 开发指南

为贡献者、插件开发者和维护者提供的开发指南和规范。

---

## 📚 核心开发文档

### 1. 插件开发指南 ⭐
**文档**: [plugin_guide.md](../plugin_guide.md)

**内容**:
- 插件架构和生命周期
- 创建自定义插件
- 插件配置和选项
- 最佳实践和模式

**快速开始**:
```python
from waveform_analysis.core.plugins.core.base import Plugin, Option

class MyCustomPlugin(Plugin):
    \"\"\"自定义插件示例\"\"\"

    # 插件元数据
    provides = "my_result"
    depends_on = ["st_waveforms"]
    version = "1.0.0"

    # 配置选项
    options = {
        "threshold": Option(default=10.0, type=float, help="检测阈值"),
        "window": Option(default=100, type=int, help="时间窗口")
    }

    def compute(self, context, run_id, st_waveforms, **kwargs):
        \"\"\"
        核心计算逻辑

        Args:
            context: Context 实例
            run_id: 运行标识符
            st_waveforms: 依赖的输入数据
            **kwargs: 插件配置参数

        Returns:
            处理后的结果数据
        \"\"\"
        threshold = kwargs.get('threshold', self.options['threshold'].default)

        # 你的处理逻辑
        result = self.process_waveforms(st_waveforms, threshold)

        return result

# 注册插件
ctx.register_plugin(MyCustomPlugin())
```

**插件类型**:
- **数据转换插件**: 转换数据格式
- **特征提取插件**: 计算特征
- **分析插件**: 统计分析
- **可视化插件**: 生成图表
- **导出插件**: 保存结果

---

### 2. 代码风格规范
**文档**: [IMPORT_STYLE_GUIDE.md](../IMPORT_STYLE_GUIDE.md)

**内容**:
- Python 导入规范
- 代码格式化标准
- 命名规范
- 文档字符串规范

**导入规范**:
```python
# 标准库导入
import os
import sys
from pathlib import Path

# 第三方库导入
import numpy as np
import pandas as pd

# 本地导入（相对导入）
from .base import Plugin
from ..processing.processor import WaveformProcessor
from ...utils import io

# 本地导入（绝对导入，推荐）
from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.core.processing.processor import WaveformProcessor
```

**命名规范**:
- **类名**: `PascalCase` (例如: `WaveformProcessor`)
- **函数/方法**: `snake_case` (例如: `load_waveforms`)
- **常量**: `UPPER_SNAKE_CASE` (例如: `MAX_CHANNELS`)
- **私有成员**: `_leading_underscore` (例如: `_internal_method`)

**文档字符串**:
```python
def process_waveform(waveform: np.ndarray, threshold: float) -> np.ndarray:
    \"\"\"
    处理单个波形数据

    Args:
        waveform: 原始波形数据
        threshold: 检测阈值

    Returns:
        处理后的波形数据

    Raises:
        ValueError: 如果波形数据格式不正确

    Examples:
        >>> waveform = np.array([1, 2, 3, 4, 5])
        >>> result = process_waveform(waveform, threshold=2.5)
        >>> print(result)
    \"\"\"
    pass
```

---

## 🎯 开发工作流

### 1. 设置开发环境

```bash
# 克隆仓库
git clone https://github.com/your-repo/waveform-analysis.git
cd waveform-analysis

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e ".[dev]"

# 或使用安装脚本
./install.sh
```

### 2. 开发插件

```bash
# 创建插件文件
touch waveform_analysis/core/plugins/builtin/my_plugin.py

# 实现插件
# ... 编写代码 ...

# 注册插件
# 在 __init__.py 中导出
```

### 3. 测试

```bash
# 运行所有测试
./scripts/run_tests.sh

# 运行特定测试
pytest tests/test_my_plugin.py -v

# 运行带覆盖率的测试
pytest --cov=waveform_analysis --cov-report=html
```

### 4. 代码检查

```bash
# 代码格式化
black waveform_analysis/ --line-length 100

# 类型检查
mypy waveform_analysis/

# Lint 检查
flake8 waveform_analysis/
```

### 5. 文档

```bash
# 生成 API 文档
waveform-docs generate all --with-context --output docs/

# 查看文档
python -m http.server 8000 --directory docs/
# 访问 http://localhost:8000
```

---

## 📖 开发规范

### Git 工作流

#### 分支策略
```
master (main)          # 主分支，稳定版本
  ├── develop          # 开发分支
  ├── feature/xxx      # 功能分支
  ├── bugfix/xxx       # 修复分支
  └── docs/xxx         # 文档分支
```

#### 提交信息规范
```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型 (type)**:
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例**:
```
feat(plugins): 添加自定义滤波插件

实现基于 Butterworth 滤波器的信号处理插件。

- 支持低通、高通、带通滤波
- 可配置截止频率和滤波器阶数
- 添加单元测试和文档

Closes #123

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## 🧪 测试指南

### 测试类型

#### 单元测试
```python
import pytest
from waveform_analysis.core.plugins.builtin import MyPlugin

def test_my_plugin_basic():
    \"\"\"测试插件基本功能\"\"\"
    plugin = MyPlugin()
    assert plugin.provides == "my_result"
    assert "st_waveforms" in plugin.depends_on

def test_my_plugin_compute():
    \"\"\"测试插件计算\"\"\"
    plugin = MyPlugin()
    # ... 准备测试数据 ...
    result = plugin.compute(ctx, "run_001", st_waveforms)
    assert result is not None
    assert len(result) > 0
```

#### 集成测试
```python
def test_full_pipeline():
    \"\"\"测试完整数据处理流程\"\"\"
    ds = WaveformDataset(run_name="test_run")
    ds.load_raw_data()
    ds.extract_waveforms()
    ds.build_dataframe()

    df = ds.get_dataframe()
    assert df is not None
    assert len(df) > 0
```

#### 性能测试
```python
import time

def test_performance():
    \"\"\"测试性能要求\"\"\"
    start = time.time()
    # ... 执行操作 ...
    elapsed = time.time() - start

    # 断言性能要求
    assert elapsed < 10.0, f"操作耗时 {elapsed}s，超过 10s 限制"
```

---

## 📋 检查清单

### 新功能开发检查清单

开发新功能前：
- [ ] 查看相关架构文档
- [ ] 查看现有类似实现
- [ ] 设计 API 接口
- [ ] 编写设计文档（如需）

开发过程中：
- [ ] 遵循代码规范
- [ ] 添加类型注解
- [ ] 编写文档字符串
- [ ] 添加单元测试
- [ ] 运行代码检查

提交前：
- [ ] 所有测试通过
- [ ] 代码格式化
- [ ] 类型检查通过
- [ ] 更新相关文档
- [ ] 编写提交信息

---

## 🔗 相关资源

### 文档
- [API 参考](api-reference.md) - API 使用方式
- [架构设计](architecture.md) - 系统架构
- [功能特性](features.md) - 功能说明

### 工具
- Black - 代码格式化
- mypy - 静态类型检查
- pytest - 测试框架
- flake8 - 代码检查

### 社区
- GitHub Issues - 报告问题
- GitHub Discussions - 讨论和问答
- Pull Requests - 贡献代码

---

## 💡 常见问题

**Q: 如何调试插件？**
A: 使用 Python 调试器（pdb）或 IDE 断点，也可以添加日志输出。

**Q: 插件之间如何通信？**
A: 通过依赖关系（depends_on）传递数据，不要直接调用其他插件。

**Q: 如何处理大数据？**
A: 使用流式处理（StreamingPlugin）或生成器模式。

**Q: 如何优化性能？**
A: 使用 Numba JIT、向量化操作、并行处理等技术。

---

**开始开发** → [plugin_guide.md](../plugin_guide.md) 🛠️
