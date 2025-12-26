import json
from pathlib import Path

import pytest

from waveform_analysis.utils.daq import DAQAnalyzer


@pytest.fixture(autouse=True)
def _ensure_tmp_path(tmp_path):
    # ensure tmp_path is available for tests that expect filesystem
    return tmp_path


def test_scan_single_run(tmp_path: Path, make_csv_fn):
    # 准备模拟 DAQ 目录
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "test_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    # 创建两个通道的 CSV 文件
    make_csv_fn(raw_dir, 1, 0, 1000, 2000)
    make_csv_fn(raw_dir, 2, 0, 1500, 2500)

    # 运行扫描
    analyzer = DAQAnalyzer(daq_root)
    analyzer.scan_all_runs()

    assert analyzer.df_runs is not None
    assert "test_run" in analyzer.runs

    run = analyzer.get_run("test_run")
    assert run is not None

    stats = run.compute_acquisition_times()
    assert 1 in stats and 2 in stats

    # 生成 JSON 文件并校验结构
    out = tmp_path / "out.json"
    analyzer._build_dataframe()  # ensure df
    analyzer.save_to_json(out, include_file_details=True)

    data = json.loads(out.read_text(encoding="utf-8"))
    assert "runs" in data
    assert len(data["runs"]) == 1
    assert data["runs"][0]["run_name"] == "test_run"
