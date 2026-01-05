"""
不加载波形数据的示例

展示如何只提取特征（峰值、电荷等）而不加载原始波形数据。
这对于内存有限或仅关心统计特征的场景很有用。
"""

from waveform_analysis import WaveformDataset


def example_without_waveforms():
    """示例：不加载波形，仅提取特征数据"""

    print("=" * 60)
    print("不加载波形数据示例")
    print("=" * 60)

    # 创建数据集，指定 load_waveforms=False
    dataset = WaveformDataset(
        run_name="50V_OV_circulation_20thr",
        n_channels=2,
        start_channel_slice=6,
        load_waveforms=False,  # 不加载原始波形！
    )

    print("\n1. 加载和处理数据（不加载波形）...")
    try:
        (
            dataset.load_raw_data()  # ✅ 加载文件列表
            .extract_waveforms()  # ✅ 流式提取特征并跳过缓存波形（load_waveforms=False）
            .structure_waveforms()  # ✅ 跳过（因为 load_waveforms=False）
            .build_waveform_features()  # ✅ 从文件读取并计算特征
            .build_dataframe()  # ✅ 构建 DataFrame
            .group_events()  # ✅ 事件分组
            .pair_events()  # ✅ 事件配对
            .save_results()
        )  # ✅ 保存结果

        print("\n✅ 处理完成！")
    except FileNotFoundError:
        print("❌ 数据文件未找到")
        return

    # 2. 获取处理结果
    print("\n2. 获取处理结果...")
    df_paired = dataset.get_paired_events()
    print(f"   配对事件数: {len(df_paired)}")

    if len(df_paired) == 0:
        print("   没有配对事件")
        return

    # 3. 查看数据
    print("\n3. 数据摘要:")
    print(f"   配对事件数: {len(df_paired)}")
    print(f"   包含的通道: {[f'CH{i}' for i in range(6, 8)]}")
    print(f"   包含的列: {list(df_paired.columns)[:10]}...")

    # 4. 查看峰值和电荷
    print("\n4. 峰值和电荷统计:")
    for ch in range(6, 8):
        peak_col = f"peak_ch{ch}"
        charge_col = f"charge_ch{ch}"
        if peak_col in df_paired.columns:
            peaks = df_paired[peak_col]
            charges = df_paired[charge_col]
            print(f"\n   CH{ch}:")
            print(f"     峰值: {peaks.mean():.2f} ± {peaks.std():.2f} (ADC)")
            print(f"     电荷: {charges.mean():.2f} ± {charges.std():.2f} (ADC)")

    # 5. 尝试获取波形（会失败）
    print("\n5. 尝试获取波形...")
    result = dataset.get_waveform_at(event_idx=0, channel=0)
    if result is None:
        print("   ✅ 正确：波形数据未加载，无法获取")
    else:
        print("   ✗ 意外：成功获取波形")


def example_with_and_without_comparison():
    """对比：加载vs不加载波形的性能差异"""

    import time

    print("\n" + "=" * 60)
    print("性能对比示例")
    print("=" * 60)

    # 加载波形
    print("\n1. 加载波形数据...")
    start = time.time()
    dataset_with_waves = WaveformDataset(
        run_name="50V_OV_circulation_20thr", n_channels=2, start_channel_slice=6, load_waveforms=True
    )

    try:
        (
            dataset_with_waves.load_raw_data(verbose=False)
            .extract_waveforms(verbose=False)
            .structure_waveforms(verbose=False)
            .build_waveform_features(verbose=False)
            .build_dataframe(verbose=False)
            .group_events(verbose=False)
            .pair_events(verbose=False)
        )
        time_with = time.time() - start
        size_with = len(dataset_with_waves.waveforms) if dataset_with_waves.waveforms else 0
        print(f"   ✅ 耗时: {time_with:.2f}s")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return

    # 不加载波形
    print("\n2. 不加载波形数据...")
    start = time.time()
    dataset_no_waves = WaveformDataset(
        run_name="50V_OV_circulation_20thr", n_channels=2, start_channel_slice=6, load_waveforms=False
    )

    try:
        (
            dataset_no_waves.load_raw_data(verbose=False)
            .extract_waveforms(verbose=False)
            .structure_waveforms(verbose=False)
            .build_waveform_features(verbose=False)
            .build_dataframe(verbose=False)
            .group_events(verbose=False)
            .pair_events(verbose=False)
        )
        time_without = time.time() - start
        print(f"   ✅ 耗时: {time_without:.2f}s")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return

    # 对比结果
    print("\n3. 对比结果:")
    speedup = time_with / time_without if time_without > 0 else 0
    print(f"   不加载波形快 {speedup:.1f}x")
    print(f"   节省时间: {time_with - time_without:.2f}s")

    # 验证结果一致性
    df_with = dataset_with_waves.get_paired_events()
    df_without = dataset_no_waves.get_paired_events()

    print(f"\n4. 数据一致性:")
    print(f"   加载波形版本事件数: {len(df_with)}")
    print(f"   不加载波形版本事件数: {len(df_without)}")

    if len(df_with) == len(df_without):
        print(f"   ✅ 事件数相同")
    else:
        print(f"   ⚠️  事件数不同")


def example_memory_usage():
    """估计内存使用情况"""

    import sys

    print("\n" + "=" * 60)
    print("内存使用估计")
    print("=" * 60)

    # 加载波形
    print("\n1. 加载波形...")
    dataset_with = WaveformDataset(run_name="50V_OV_circulation_20thr", n_channels=2, load_waveforms=True)

    try:
        dataset_with.load_raw_data(verbose=False).extract_waveforms(verbose=False)

        if dataset_with.waveforms:
            total_size = 0
            for ch, wf in enumerate(dataset_with.waveforms):
                size = wf.nbytes if hasattr(wf, "nbytes") else 0
                total_size += size
                print(f"   CH{ch + dataset_with.start_channel_slice}: {size / 1024 / 1024:.2f} MB")
            print(f"   总计: {total_size / 1024 / 1024:.2f} MB")
    except Exception as e:
        print(f"   ❌ {e}")

    # 不加载波形
    print("\n2. 不加载波形...")
    dataset_without = WaveformDataset(run_name="50V_OV_circulation_20thr", n_channels=2, load_waveforms=False)

    try:
        dataset_without.load_raw_data(verbose=False).extract_waveforms(verbose=False)
        print(f"   ✅ 节省了上述所有内存")
    except Exception as e:
        print(f"   ❌ {e}")


if __name__ == "__main__":
    # 运行示例
    example_without_waveforms()

    # 可选：运行性能对比
    # example_with_and_without_comparison()

    # 可选：查看内存使用
    # example_memory_usage()
