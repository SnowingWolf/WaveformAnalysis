# CSV 表头处理说明

## 概述

在波形数据采集过程中，每个通道的 CSV 文件具有特殊的表头结构：
- **第一个文件**：包含元数据行和表头行，需要跳过这些行才能读取数据
- **后续文件**：不包含表头和元数据，直接包含数据行

本模块实现了智能的表头处理逻辑，能够自动识别并正确处理这种情况。

## 问题背景

在 DAQ 数据采集系统中，每个通道的数据可能被分割成多个 CSV 文件。通常：
- 第一个文件（索引为 0）包含完整的元数据和表头信息
- 后续文件（索引 > 0）只包含数据行，没有表头

如果对所有文件使用相同的 `skiprows` 参数，会导致：
- 第一个文件：正确跳过表头，读取数据
- 后续文件：错误地跳过数据行，导致数据丢失或错位

## 解决方案

### 实现逻辑

`parse_and_stack_files` 和 `parse_files_generator` 函数现在会根据文件在列表中的位置自动调整 `skiprows` 参数：

```python
# 第一个文件（索引 0）：使用指定的 skiprows 值（默认 2）
file_skiprows = skiprows if file_idx == 0 else 0

# 后续文件（索引 > 0）：不跳过任何行（skiprows=0）
```

### 函数签名

#### `parse_and_stack_files`

```python
def parse_and_stack_files(
    file_paths: List[str],
    skiprows: int = 2,  # 仅用于第一个文件
    delimiter: str = ";",
    chunksize: int | None = None,
    n_jobs: int = 1,
    use_process_pool: bool = False,
    show_progress: bool = False,
) -> np.ndarray:
    """
    解析 CSV 文件列表并返回堆叠的 numpy 数组。
    
    注意：只有列表中的第一个文件会跳过表头行（skiprows）。
    后续文件不会跳过任何行（skiprows=0），因为它们不包含表头。
    """
```

#### `parse_files_generator`

```python
def parse_files_generator(
    file_paths: List[str],
    skiprows: int = 2,  # 仅用于第一个文件
    delimiter: str = ";",
    chunksize: int = 1000,
    show_progress: bool = False,
) -> Iterator[np.ndarray]:
    """
    生成器函数，按块产生解析后的波形数据。
    
    注意：只有列表中的第一个文件会跳过表头行（skiprows）。
    后续文件不会跳过任何行（skiprows=0），因为它们不包含表头。
    """
```

## 使用示例

### 基本用法

```python
from waveform_analysis.utils.io import parse_and_stack_files
from pathlib import Path

# 准备文件列表（按索引排序）
files = [
    "DAQ/run1/RAW/RUN_CH0_0.CSV",  # 第一个文件，包含表头
    "DAQ/run1/RAW/RUN_CH0_1.CSV",  # 后续文件，无表头
    "DAQ/run1/RAW/RUN_CH0_2.CSV",  # 后续文件，无表头
]

# 解析文件（自动处理表头）
data = parse_and_stack_files(files, skiprows=2, delimiter=";")

# data 现在包含所有文件的数据行，正确对齐
print(f"总行数: {data.shape[0]}")
print(f"列数: {data.shape[1]}")
```

### 流式处理

```python
from waveform_analysis.utils.io import parse_files_generator

files = [
    "DAQ/run1/RAW/RUN_CH0_0.CSV",
    "DAQ/run1/RAW/RUN_CH0_1.CSV",
]

# 流式读取，自动处理表头
for chunk in parse_files_generator(files, skiprows=2, chunksize=1000):
    # 处理每个数据块
    process_chunk(chunk)
```

### 多通道处理

每个通道的文件列表是独立处理的，每个通道的第一个文件都会跳过表头：

```python
from waveform_analysis.core.loader import get_waveforms

# 每个通道的文件列表
raw_files = [
    ["CH0_0.CSV", "CH0_1.CSV"],  # 通道0：第一个文件有表头
    ["CH1_0.CSV", "CH1_1.CSV"],  # 通道1：第一个文件有表头
]

# 加载波形（每个通道独立处理表头）
waveforms = get_waveforms(raw_files)
```

## CSV 文件格式

### 第一个文件（带表头）

```
META;INFO
HEADER;X;TIMETAG;S0;S1;S2;...
v;1;1000;10;11;12;...
v;1;1500;15;16;17;...
v;1;2000;20;21;22;...
```

- 第1行：元数据（需要跳过）
- 第2行：表头（需要跳过）
- 第3行开始：数据行

### 后续文件（无表头）

```
v;1;2001;20;21;22;...
v;1;2500;25;26;27;...
v;1;3000;30;31;32;...
```

- 直接是数据行，不需要跳过任何行

## 技术细节

### 内部实现

1. **文件索引检测**：通过 `enumerate(file_paths)` 获取文件索引
2. **条件跳过**：根据索引决定 `skiprows` 值
3. **并行处理兼容**：在多进程/多线程模式下，每个任务接收正确的 `file_skiprows` 参数

### 性能考虑

- 第一个文件需要额外处理（跳过表头），但这是必要的
- 后续文件处理更快（无需跳过行）
- 并行处理时，每个文件独立处理，互不影响

### 错误处理

- 如果文件不存在或为空，会被自动跳过
- 如果解析失败，会记录日志并继续处理其他文件
- 支持多种 CSV 引擎（C、Python、PyArrow）的回退机制

## 测试

完整的测试用例位于 `tests/test_csv_header_handling.py`，包括：

- ✅ 混合表头文件的正确解析
- ✅ 单个文件（带表头）的处理
- ✅ 多个文件（无表头）的边界情况
- ✅ 流式处理的表头处理
- ✅ 并行处理的正确性
- ✅ 多通道独立处理

运行测试：

```bash
pytest tests/test_csv_header_handling.py -v
```

## 兼容性

### 向后兼容

- 如果所有文件都包含表头（旧格式），可以通过设置 `skiprows` 参数处理
- 如果所有文件都不包含表头，第一个文件会被错误跳过，但这种情况在实际使用中很少见

### 建议

- 确保文件列表按索引正确排序
- 使用默认的 `skiprows=2` 参数（适用于标准的 DAQ 输出格式）
- 如果使用自定义格式，请相应调整 `skiprows` 参数

## 相关文件

- `waveform_analysis/utils/io.py` - 核心实现
- `tests/test_csv_header_handling.py` - 测试用例
- `waveform_analysis/core/loader.py` - 文件加载器（使用上述函数）

## 更新历史

- **2024-12-XX**: 初始实现，支持智能表头处理

