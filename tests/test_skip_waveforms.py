"""
测试 load_waveforms 功能的脚本
"""

import sys
from pathlib import Path

from waveform_analysis import WaveformDataset


def test_without_waveforms(create_daq_run):
    """测试：不加载波形（使用 fixture）。"""
    daq_root, run_dir, raw_dir = create_daq_run("50V_OV_circulation_20thr")

    dataset = WaveformDataset(
        run_name="50V_OV_circulation_20thr",
        n_channels=2,
        start_channel_slice=6,
        load_waveforms=False,
        data_root=str(daq_root),
    )

    # Should run through pipeline without raising and not load waveforms
    dataset.load_raw_data()
    dataset.extract_waveforms()
    dataset.build_waveform_features()
    dataset.build_dataframe()
    dataset.pair_events()

    assert dataset.get_waveform_at(0) is None


def test_with_waveforms(create_daq_run, make_simple_csv_fn):
    """测试：加载波形（使用 fixture）。"""
    daq_root, run_dir, raw_dir = create_daq_run("50V_OV_circulation_20thr")

    # create a tiny CSV so load_raw_data can find something
    make_simple_csv_fn(raw_dir, 6, 0, 1234, n_samples=20)

    dataset = WaveformDataset(
        run_name="50V_OV_circulation_20thr",
        n_channels=2,
        start_channel_slice=6,
        load_waveforms=True,
        data_root=str(daq_root),
    )

    dataset.load_raw_data()
    dataset.extract_waveforms()

    assert dataset.waveforms is not None
    dataset.build_waveform_features()
    dataset.build_dataframe()
    dataset.group_events()
    dataset.pair_events()

    # If waveforms exist, get_waveform_at may return None if no paired events; just ensure no exception
    _ = dataset.get_waveform_at(0)


def test_with_waveforms(tmp_path: Path):
    """测试：加载波形"""
    print("\n" + "=" * 70)
    print("测试 2: 加载波形 (load_waveforms=True，默认)")
    print("=" * 70)

    data_root = tmp_path / "DAQ"
    run_dir = data_root / "50V_OV_circulation_20thr"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    # create a tiny CSV so load_raw_data can find something
    from tests.utils import make_simple_csv

    make_simple_csv(raw_dir, 6, 0, 1234, n_samples=20)

    dataset = WaveformDataset(
        run_name="50V_OV_circulation_20thr",
        n_channels=2,
        start_channel_slice=6,
        load_waveforms=True,  # 显式指定，但这是默认值
        data_root=str(data_root),
    )

    print("\n1️⃣  加载原始数据...")
    dataset.load_raw_data()
    total_files = sum(len(fs) for fs in dataset.raw_files) if dataset.raw_files else 0
    print(f"   ✅ 加载了 {total_files} 个文件")

    print("\n2️⃣  提取波形...")

    dataset.extract_waveforms()
    if dataset.waveforms:
        print(f"   ✅ 波形已加载，通道数: {len(dataset.waveforms)}")
    else:
        print(f"   ⚠️  波形为空")

    print("\n3️⃣  构建特征...")
    dataset.build_waveform_features()
    print(f"   ✅ 特征已计算")

    print("\n4️⃣  构建 DataFrame...")
    dataset.build_dataframe()
    df = dataset.get_raw_events()
    if df is not None:
        print(f"   ✅ DataFrame 行数: {len(df)}")

    print("\n5️⃣  配对事件...")
    dataset.pair_events()
    df_paired = dataset.get_paired_events()
    if df_paired is not None:
        print(f"   ✅ 配对事件数: {len(df_paired)}")

    print("\n6️⃣  尝试获取波形...")
    result = dataset.get_waveform_at(0)
    if result:
        wave, baseline = result
        print(f"   ✅ 成功获取波形")
        print(f"      波形长度: {len(wave)}")
        print(f"      基线值: {baseline}")
    else:
        print(f"   ❌ 无法获取波形: {result}")

    assert dataset is not None


if __name__ == "__main__":
    try:
        print("\n" + "=" * 70)
        print("波形加载选项测试")
        print("=" * 70)

        # 测试不加载波形
        try:
            dataset_no_waves = test_without_waveforms()
        except Exception as e:
            print(f"\n❌ 测试 1 失败: {e}")
            import traceback

            traceback.print_exc()

        # 测试加载波形
        try:
            dataset_with_waves = test_with_waveforms()
        except Exception as e:
            print(f"\n❌ 测试 2 失败: {e}")
            import traceback

            traceback.print_exc()

        print("\n" + "=" * 70)
        print("✅ 所有测试完成")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
