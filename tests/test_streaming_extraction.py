from pathlib import Path

from waveform_analysis import WaveformDataset


def test_streaming_feature_extraction(tmp_path: Path, make_simple_csv_fn):
    """当不缓存波形时（load_waveforms=False），应通过流式读取计算特征并构建 DataFrame。"""
    data_root = tmp_path / "DAQ"
    run_dir = data_root / "50V_OV_circulation_20thr"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    # create simple CSV files for two channels
    make_simple_csv_fn(raw_dir, 6, 0, 1000, n_samples=80)
    make_simple_csv_fn(raw_dir, 7, 0, 1005, n_samples=80)

    ds = WaveformDataset(
        run_name="50V_OV_circulation_20thr",
        n_channels=2,
        start_channel_slice=6,
        load_waveforms=False,
        data_root=str(data_root),
    )

    ds.load_raw_data()
    ds.extract_waveforms(chunksize=50)
    # After streaming extraction, peaks and charges should be present
    assert hasattr(ds, "peaks") and len(ds.peaks) == 2
    assert hasattr(ds, "charges") and len(ds.charges) == 2

    ds.build_dataframe()
    assert ds.df is not None
    assert len(ds.df) > 0
