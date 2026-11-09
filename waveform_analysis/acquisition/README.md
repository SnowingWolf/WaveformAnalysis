# 采集数据访问

采集模块按三个职责组织，公开类和函数仍可通过包入口导入。

| 目录 | 职责 | 主要实现 |
| --- | --- | --- |
| `runs/` | 发现运行、组织文件、汇总和展示运行信息 | `run.py`、`analyzer.py`、`discovery.py`、`adapters.py` |
| `formats/` | 解释设备格式、字段和单位，提供适配器及目录布局 | 公共契约，以及 `v1725/`、`vx2730/` 设备包 |
| `file_io/` | 通用 CSV 读取和批量调度 | `csv_pandas.py`、`csv_polars.py`、`csv_pyarrow.py`、`orchestration.py` |

```python
from waveform_analysis.acquisition.runs import DAQAnalyzer, DAQRun
from waveform_analysis.acquisition.formats import get_adapter
from waveform_analysis.acquisition.file_io import parse_and_stack_files, parse_files_generator
```

`runs` 使用格式层提供的目录规则；`file_io` 调度各 CSV 后端，在显式指定
格式读取器时委托 `formats` 解析。设备专属二进制解析继续放在设备包中。

`acquisition.daq`、`acquisition.readers`、`acquisition.io` 及相关 `utils`
路径保留为兼容入口，引用同一份实现。旧 `io` 模块直接指向新的调度模块，
旧代码对该模块全局读取函数或后端可用标志的替换仍作用于实际调用。
新代码使用上面的规范路径；兼容入口不保存第二份读取实现。
