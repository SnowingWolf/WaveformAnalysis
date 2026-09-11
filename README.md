# WaveformAnalysis

WaveformAnalysis 是一个用于处理和分析 DAQ 波形数据的 Python 工具包。

## 安装

```bash
./install.sh
pip install -e ".[dev]"
```

## 常用命令

```bash
waveform-process --run-name <run_name> --verbose
waveform-docs generate plugins-agent -o docs/plugins/reference/agent/
waveform-cache --help
```

## 测试

```bash
./scripts/run_tests.sh
make test
pytest -v --cov=waveform_analysis --cov-report=html
```

## 文档

- 文档中心: [`docs/README.md`](docs/README.md)
- 用户指南: [`docs/user-guide/README.md`](docs/user-guide/README.md)
- 快速开始: [`docs/user-guide/QUICKSTART_GUIDE.md`](docs/user-guide/QUICKSTART_GUIDE.md)
- Agent 入口: `AGENTS.md`

## 规范 Python 入口

```python
from waveform_analysis.acquisition import DAQAdapter, DAQAnalyzer, DAQRun, get_adapter
from waveform_analysis.analysis import PeakChannelAccessor, S1S2PairAccessor
from waveform_analysis.visualization import corner_hist, plot_lineage_labview, plot_waveforms
```

历史 `waveform_analysis.utils.*` 导入继续作为无弃用警告的兼容入口；新代码应使用上述按职责划分的规范包。

命名约定：DAQ/CLI 数据集名称使用 `run_name`，Context/API 数据访问标识使用显式 `run_id`；CLI 正式参数为 `--run-name`，`--char` 仅保留为兼容别名。
