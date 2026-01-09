# 项目结构说明

## 完整目录树

```
waveform-analysis/
│
├── waveform_analysis/              # 主包目录
│   ├── __init__.py                # 包初始化，导出主要 API
│   ├── cli.py                     # 命令行接口
│   │
│   ├── core/                      # 核心功能模块（模块化子目录结构）
│   │   ├── __init__.py            # 统一导出，保持向后兼容
│   │   ├── context.py             # 核心调度：Context 类，管理插件与缓存
│   │   ├── dataset.py             # 高层 API：WaveformDataset 链式封装
│   │   ├── cancellation.py        # 取消管理
│   │   ├── load_balancer.py       # 负载均衡
│   │   │
│   │   ├── storage/               # 存储层（5个文件）
│   │   │   ├── __init__.py
│   │   │   ├── memmap.py          # 基于 memmap 的零拷贝存储
│   │   │   ├── backends.py        # 可插拔存储后端（SQLite等）
│   │   │   ├── cache.py           # 缓存管理：Lineage 校验与签名
│   │   │   ├── compression.py     # 压缩管理：Blosc2, LZ4, Zstd
│   │   │   └── integrity.py       # 数据完整性检查
│   │   │
│   │   ├── execution/             # 执行层（3个文件）
│   │   │   ├── __init__.py
│   │   │   ├── manager.py         # ExecutorManager：统一管理线程/进程池
│   │   │   ├── config.py          # 执行器配置：IO密集型、CPU密集型等
│   │   │   └── timeout.py         # 超时管理：TimeoutManager
│   │   │
│   │   ├── plugins/               # 插件系统（核心和内置分离）
│   │   │   ├── __init__.py        # 统一导出
│   │   │   ├── core/              # 核心基础设施（6个文件）
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py        # 插件基类：Plugin, Option
│   │   │   │   ├── streaming.py   # 流式插件基类
│   │   │   │   ├── loader.py      # 插件动态加载器
│   │   │   │   ├── stats.py       # 插件性能统计
│   │   │   │   ├── hot_reload.py  # 插件热重载
│   │   │   │   └── adapters.py    # Strax 插件适配器
│   │   │   └── builtin/           # 内置插件（2个文件）
│   │   │       ├── __init__.py
│   │   │       ├── standard.py    # 标准插件：RawFiles, Waveforms, Features 等
│   │   │       └── streaming_examples.py  # 流式插件示例
│   │   │
│   │   ├── processing/            # 数据处理（4个文件）
│   │   │   ├── __init__.py
│   │   │   ├── loader.py          # 数据加载：WaveformLoader
│   │   │   ├── processor.py       # 信号处理：WaveformStruct（支持 Numba）
│   │   │   ├── analyzer.py        # 事件分析：聚类与配对（支持多进程）
│   │   │   └── chunk.py           # Chunk 对象与时间区间操作
│   │   │
│   │   ├── data/                  # 数据管理（2个文件）
│   │   │   ├── __init__.py
│   │   │   ├── query.py           # 时间范围查询：TimeRangeQueryEngine
│   │   │   └── export.py          # 批量处理和导出：BatchProcessor, DataExporter
│   │   │
│   │   └── foundation/            # 框架基础（5个文件）
│   │       ├── __init__.py
│   │       ├── exceptions.py      # 异常类和错误处理
│   │       ├── mixins.py          # 功能混合类：CacheMixin
│   │       ├── model.py           # 数据模型：LineageGraphModel
│   │       ├── utils.py           # 工具函数：exporter, Profiler
│   │       └── progress.py        # 进度追踪：ProgressTracker
│   │
│   ├── fitting/                   # 拟合模块
│   │   ├── __init__.py
│   │   └── models.py              # 拟合模型：Landau-Gauss, LandauGaussFitter
│   │
│   └── utils/                     # 工具函数
│       ├── __init__.py
│       ├── io.py                  # I/O 工具：CSV 解析、生成器
│       ├── loader.py              # 加载器适配：兼容性导出
│       ├── daq/                   # DAQ 工具：DAQRun, DAQAnalyzer
│       └── visualization/         # 可视化工具：波形绘图、血缘图
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
└── *.ipynb                        # Jupyter 笔记本
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

核心数据处理功能，采用**模块化子目录架构**，将原本扁平的 27 个文件重构为 6 个功能子目录。

#### 核心文件（保持扁平）

**`context.py`**
核心调度模块：
- `Context`: 管理插件注册、依赖解析、配置分发和数据缓存
- 支持多级缓存校验和血缘追踪

**`dataset.py`**
高层 API 模块：
- `WaveformDataset`: 提供链式调用接口，内部委托 `Context` 执行

#### `storage/` - 存储层（5个文件）

数据持久化、缓存管理和压缩：

- **`memmap.py`**: 基于 `numpy.memmap` 的零拷贝存储
- **`backends.py`**: 可插拔存储后端（MemmapBackend, SQLiteBackend）
- **`cache.py`**: 基于 Lineage 的缓存校验与签名管理
- **`compression.py`**: 压缩管理（Blosc2, LZ4, Zstd, Gzip）
- **`integrity.py`**: 数据完整性检查（校验和、验证）

#### `execution/` - 执行层（3个文件）

并行执行和超时管理：

- **`manager.py`**: `ExecutorManager` 全局单例，统一管理线程/进程池
- **`config.py`**: 预定义配置（IO密集型、CPU密集型、大数据、小数据）
- **`timeout.py`**: `TimeoutManager` 超时控制

便捷函数：`get_executor()`, `parallel_map()`, `parallel_apply()`

#### `plugins/` - 插件系统（核心和内置分离）

**`plugins/core/`** - 核心基础设施（6个文件）：
- **`base.py`**: 插件基类 `Plugin` 和配置 `Option`
- **`streaming.py`**: 流式插件基类 `StreamingPlugin`
- **`loader.py`**: 插件动态加载器 `PluginLoader`
- **`stats.py`**: 插件性能统计 `PluginStatsCollector`
- **`hot_reload.py`**: 插件热重载 `PluginHotReloader`
- **`adapters.py`**: Strax 插件适配器 `StraxPluginAdapter`

**`plugins/builtin/`** - 内置插件（2个文件）：
- **`standard.py`**: 标准数据处理插件
  - `RawFilesPlugin`, `WaveformsPlugin`, `StWaveformsPlugin`
  - `BasicFeaturesPlugin`, `DataFramePlugin`
  - `GroupedEventsPlugin`, `PairedEventsPlugin`
- **`streaming_examples.py`**: 流式处理插件示例

#### `processing/` - 数据处理（4个文件）

数据加载、信号处理和事件分析：

- **`loader.py`**: `WaveformLoader` 数据加载器
- **`processor.py`**: 信号处理（`WaveformStruct`, 峰值查找，支持 Numba JIT）
- **`analyzer.py`**: 事件分析（聚类与配对，支持多进程）
- **`chunk.py`**: `Chunk` 对象与时间区间操作工具

#### `data/` - 数据管理（2个文件）

时间范围查询和批量导出：

- **`query.py`**: `TimeRangeQueryEngine` 时间范围查询引擎
- **`export.py`**: 批量处理和导出
  - `BatchProcessor`: 多运行批量处理
  - `DataExporter`: 统一数据导出（Parquet, HDF5, CSV, JSON）

#### `foundation/` - 框架基础（5个文件）

异常处理、Mixin、模型和工具函数：

- **`exceptions.py`**: 异常类（`PluginError`, `ErrorSeverity`）
- **`mixins.py`**: 功能混合类（`CacheMixin`, `StepMixin`）
- **`model.py`**: 数据模型（`LineageGraphModel`）
- **`utils.py`**: 工具函数（`exporter`, `Profiler`）
- **`progress.py`**: 进度追踪（`ProgressTracker`）

#### 向后兼容

所有公共 API 通过 `core/__init__.py` 统一导出，保持完全向后兼容：

```python
# 仍然可用
from waveform_analysis.core import Plugin, MemmapStorage
from waveform_analysis.core import get_executor, WaveformStruct
```

推荐使用新路径：
```python
# 新路径更清晰
from waveform_analysis.core.plugins import Plugin
from waveform_analysis.core.storage import MemmapStorage
from waveform_analysis.core.execution import get_executor
from waveform_analysis.core.processing import WaveformStruct
```

### waveform_analysis/fitting/

拟合模型模块。

#### `models.py`

- `gauss()`: 高斯函数
- `landau_pdf_approx()`: Landau PDF 近似
- `landau_gauss_jax()`: JAX 实现的 Landau-Gauss 卷积
- `LandauGaussFitter`: Landau-Gauss 拟合器

### waveform_analysis/utils/

工具函数模块，包含 I/O、加载适配、DAQ 分析和可视化工具。

#### `io.py`
底层 I/O 工具，提供高效的 CSV 解析和流式生成器。

#### `loader.py`
加载器适配层，将 `core/loader.py` 的功能导出为兼容旧版本的 API。

#### `daq/`
DAQ 相关工具，包括 `DAQRun` 和 `DAQAnalyzer`。

#### `visualization/`
可视化工具，包括波形绘制和血缘追踪图生成。

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
