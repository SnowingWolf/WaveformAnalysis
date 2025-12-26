# 项目结构说明

## 完整目录树

```
waveform-analysis/
│
├── waveform_analysis/              # 主包目录
│   ├── __init__.py                # 包初始化，导出主要 API
│   ├── cli.py                     # 命令行接口
│   │
│   ├── core/                      # 核心功能模块
│   │   ├── __init__.py
│   │   ├── loader.py              # 数据加载：RawFileLoader, get_raw_files, get_waveforms
│   │   ├── processor.py           # 数据处理：WaveformStruct, build_waveform_df, group_multi_channel_hits
│   │   └── dataset.py             # 数据集封装：WaveformDataset 主类
│   │
│   ├── fitting/                   # 拟合模块
│   │   ├── __init__.py
│   │   └── models.py              # 拟合模型：Landau-Gauss, LandauGaussFitter
│   │
│   └── utils/                     # 工具函数（预留）
│       └── __init__.py
│
├── tests/                         # 测试目录
│   ├── __init__.py
│   ├── test_basic.py              # 基本功能测试
│   └── test_loader.py             # 加载器测试
│
├── examples/                      # 示例脚本
│   ├── basic_analysis.py          # 基础分析示例
│   └── advanced_features.py       # 高级功能示例
│
├── docs/                          # 文档目录
│   ├── data_module.md             # 原有的模块文档
│   └── USAGE.md                   # 使用指南
│
├── scripts/                       # 辅助脚本（预留）
│
├── DAQ/                           # 数据目录（不包含在包中）
│   └── ...
│
├── outputs/                       # 输出目录（不包含在包中）
│   └── ...
│
├── pyproject.toml                 # 项目配置（现代方式）
├── setup.py                       # 安装配置（兼容性，可选）
├── MANIFEST.in                    # 打包清单
├── requirements.txt               # 依赖列表
├── requirements-dev.txt           # 开发依赖
├── README.md                      # 项目说明
├── LICENSE                        # MIT 许可证
├── CONTRIBUTING.md                # 贡献指南
├── .gitignore                     # Git 忽略文件
├── install.sh                     # 快速安装脚本
│
├── data.py                        # 原始文件（保留用于向后兼容）
├── dataset.py                     # 原始文件（保留用于向后兼容）
├── load.py                        # 原始文件（保留用于向后兼容）
├── fit.py                         # 原始文件（保留用于向后兼容）
└── *.ipynb                        # Jupyter 笔记本（保留）
```

## 模块说明

### waveform_analysis/

主包目录，包含所有的核心代码。

#### `__init__.py`

包的入口点，导出主要 API：
- `WaveformDataset`: 主数据集类
- `get_raw_files`, `get_waveforms`: 数据加载函数
- `WaveformStruct`, `build_waveform_df`, `group_multi_channel_hits`: 数据处理函数

#### `cli.py`

命令行接口，提供 `waveform-process` 命令。

### waveform_analysis/core/

核心数据处理功能。

#### `loader.py`

数据加载模块：
- `RawFileLoader`: 文件加载类
- `get_raw_files()`: 获取原始文件列表
- `get_waveforms()`: 加载波形数据
- `build_filetime_index()`: 建立文件时间索引

#### `processor.py`

数据处理模块：
- `WaveformStruct`: 波形结构化类
- `build_waveform_df()`: 构建波形 DataFrame
- `group_multi_channel_hits()`: 多通道事件分组
- 编码/解码辅助函数

#### `dataset.py`

数据集封装模块：
- `WaveformDataset`: 完整数据处理流程封装
  - 链式调用支持
  - 特征注册系统
  - 自定义配对策略
  - 时间戳索引缓存

### waveform_analysis/fitting/

拟合模型模块。

#### `models.py`

- `gauss()`: 高斯函数
- `landau_pdf_approx()`: Landau PDF 近似
- `landau_gauss_jax()`: JAX 实现的 Landau-Gauss 卷积
- `LandauGaussFitter`: Landau-Gauss 拟合器

### waveform_analysis/utils/

工具函数模块（预留用于扩展）。

## 配置文件

### pyproject.toml

现代 Python 项目配置文件，包含：
- 项目元数据
- 依赖声明
- 构建系统配置
- 开发工具配置（black, pytest, mypy）

### requirements.txt

运行时依赖列表。

### requirements-dev.txt

开发依赖列表（测试、格式化、类型检查等）。

### MANIFEST.in

定义打包时包含的文件。

## 安装方式

### 开发模式安装

```bash
pip install -e .
```

这会创建一个链接到源代码的安装，修改代码立即生效。

### 普通安装

```bash
pip install .
```

### 从 PyPI 安装（未来）

```bash
pip install waveform-analysis
```

## 使用方式

### 作为包使用

```python
from waveform_analysis import WaveformDataset

dataset = WaveformDataset(char="...")
dataset.load_raw_data().extract_waveforms()...
```

### 使用命令行工具

```bash
waveform-process --char dataset_name --verbose
```

### 运行示例

```bash
python examples/basic_analysis.py
```

### 运行测试

```bash
pytest tests/
```

## 向后兼容

项目根目录保留了原始的 Python 文件（`data.py`, `load.py` 等），以保持向后兼容性。现有的 Jupyter 笔记本可以继续使用这些文件。

要迁移到新的包结构，只需修改导入语句：

```python
# 旧方式
from data import WaveformDataset
from load import get_raw_files

# 新方式
from waveform_analysis import WaveformDataset
from waveform_analysis.core import get_raw_files
```

## 扩展指南

### 添加新特征

1. 在适当的模块中定义特征计算函数
2. 使用 `dataset.register_feature()` 注册
3. 或直接添加到 `processor.py` 中

### 添加新的拟合模型

1. 在 `fitting/models.py` 中添加新模型
2. 继承 `BaseFitter`（如果使用 pyDAW）
3. 在 `fitting/__init__.py` 中导出

### 添加工具函数

在 `utils/` 目录下创建新模块。

## 发布流程

1. 更新版本号（`pyproject.toml` 和 `__init__.py`）
2. 更新 CHANGELOG
3. 构建分发包：`python -m build`
4. 上传到 PyPI：`twine upload dist/*`

## 维护清单

- [ ] 定期更新依赖版本
- [ ] 添加更多测试
- [ ] 完善文档
- [ ] 添加 CI/CD
- [ ] 发布到 PyPI
