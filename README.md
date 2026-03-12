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

- 文档中心: `docs/README.md`
- Agent 入口: `AGENTS.md`
