from datetime import datetime
import json
import os
from pathlib import Path
import warnings

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


def test_scan_v1725_bseg_naming_with_adapter(tmp_path: Path):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "test_run_v1725"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    # DAW_DEMO 风格命名：test_raw_b0_segX.bin
    (raw_dir / "test_raw_b0_seg0.bin").write_bytes(b"\x01\x02\x03")
    (raw_dir / "test_raw_b0_seg1.bin").write_bytes(b"\x04\x05")

    analyzer = DAQAnalyzer(daq_root, daq_adapter="v1725")
    analyzer.scan_all_runs()

    run = analyzer.get_run("test_run_v1725")
    assert run is not None
    assert run.file_count == 2
    assert run.total_bytes == 5
    assert run.channels == {0}


def test_display_overview_time_sort_no_infer_warning(tmp_path: Path, make_csv_fn):
    daq_root = tmp_path / "DAQ"

    # 非空 run（有可解析时间）
    run_dir1 = daq_root / "run_with_data" / "RAW"
    run_dir1.mkdir(parents=True)
    make_csv_fn(run_dir1, 1, 0, 1000, 2000)

    # 空 run（会产生 N/A）
    run_dir2 = daq_root / "run_empty" / "RAW"
    run_dir2.mkdir(parents=True)

    analyzer = DAQAnalyzer(daq_root)
    analyzer.scan_all_runs()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        analyzer.display_overview(sort_by="time")

    assert not any("Could not infer format" in str(w.message) for w in caught)


def test_run_acquisition_window_uses_first_file_time_and_last_file_end(tmp_path: Path, make_csv_fn):
    daq_root = tmp_path / "DAQ"
    raw_dir = daq_root / "test_run" / "RAW"
    raw_dir.mkdir(parents=True)

    make_csv_fn(raw_dir, 1, 0, 0, 2_000_000_000_000)
    make_csv_fn(raw_dir, 1, 1, 1_000_000_000_000, 5_000_000_000_000)
    first_file = raw_dir / "RUN_CH1_0.CSV"
    last_file = raw_dir / "RUN_CH1_1.CSV"

    first_ts = datetime(2024, 1, 1, 12, 0, 0).timestamp()
    last_mtime_ts = datetime(2024, 1, 1, 12, 0, 1).timestamp()
    os.utime(first_file, (first_ts, first_ts))
    os.utime(last_file, (last_mtime_ts, last_mtime_ts))

    analyzer = DAQAnalyzer(daq_root)
    analyzer.scan_all_runs()

    assert analyzer._get_run_acquisition_start("test_run") == "2024-01-01 12:00:00"
    assert analyzer._get_run_acquisition_end("test_run") == "2024-01-01 12:00:05"

    run = analyzer.get_run("test_run")
    assert run is not None
    start_time, end_time = run.get_run_acquisition_window()
    assert start_time == datetime.fromtimestamp(first_ts)
    assert end_time == datetime.fromtimestamp(first_ts + 5)
