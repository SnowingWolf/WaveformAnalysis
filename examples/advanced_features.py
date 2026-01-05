"""
高级功能示例 - 自定义特征和配对策略
"""

import numpy as np

from waveform_analysis import WaveformDataset


def example_custom_features():
    """示例：注册和使用自定义特征"""

    print("\n" + "=" * 60)
    print("自定义特征示例")
    print("=" * 60)

    dataset = WaveformDataset(run_name="50V_OV_circulation_20thr", n_channels=2, start_channel_slice=6)

    # 加载和处理数据
    try:
        (dataset.load_raw_data().extract_waveforms().structure_waveforms())
    except FileNotFoundError:
        print("数据文件未找到，退出")
        return

    # 定义自定义特征函数
    def compute_rise_time(waveforms, start=40, end=90):
        """计算上升时间（从10%到90%峰值）"""
        rise_times = []
        for wave_struct in waveforms:
            wave = wave_struct["wave"]
            peak = np.max(wave[start:end])
            baseline = wave_struct["baseline"]

            # 找到10%和90%的位置
            thresh_10 = baseline + 0.1 * (peak - baseline)
            thresh_90 = baseline + 0.9 * (peak - baseline)

            idx_10 = np.where(wave[start:end] > thresh_10)[0]
            idx_90 = np.where(wave[start:end] > thresh_90)[0]

            if len(idx_10) > 0 and len(idx_90) > 0:
                rise_time = idx_90[0] - idx_10[0]
            else:
                rise_time = -1

            rise_times.append(rise_time)

        return [np.array(rise_times)]

    # 注册特征
    print("\n注册自定义特征: rise_time")
    dataset.register_feature("rise_time", compute_rise_time, start=40, end=90)

    # 计算特征
    print("计算注册的特征...")
    dataset.compute_registered_features(verbose=True)

    # 继续处理流程
    (dataset.build_waveform_features().build_dataframe().group_events().pair_events())

    # 将特征添加到 DataFrame
    dataset.add_features_to_dataframe(["rise_time"])

    df_paired = dataset.get_paired_events()
    print(f"\n✅ 完成！配对事件数: {len(df_paired)}")

    if "rise_time_ch0" in df_paired.columns:
        print(f"   - CH0 平均上升时间: {df_paired['rise_time_ch0'].mean():.2f}")
        print(f"   - CH1 平均上升时间: {df_paired['rise_time_ch1'].mean():.2f}")


def example_custom_pairing():
    """示例：使用自定义配对策略"""

    print("\n" + "=" * 60)
    print("自定义配对策略示例")
    print("=" * 60)

    dataset = WaveformDataset(run_name="50V_OV_circulation_20thr", n_channels=2, start_channel_slice=6)

    # 处理到分组阶段
    try:
        (
            dataset.load_raw_data()
            .extract_waveforms()
            .structure_waveforms()
            .build_waveform_features()
            .build_dataframe()
            .group_events()
        )
    except FileNotFoundError:
        print("数据文件未找到，退出")
        return

    # 定义自定义配对策略
    def high_energy_pairing(df_events):
        """只配对高能量事件"""
        df_filtered = df_events[
            (df_events["n_hits"] == 2) & (df_events["channels"].apply(lambda x: np.array_equal(x, [0, 1])))
        ].copy()

        # 添加条件：总电荷大于某个阈值
        df_filtered["total_charge"] = df_filtered["charges"].apply(lambda x: sum(x))
        df_filtered = df_filtered[df_filtered["total_charge"] > 5000]

        return df_filtered

    # 使用自定义策略
    print("\n使用自定义配对策略: 高能量事件筛选")
    df_custom = dataset.pair_events_with(high_energy_pairing, verbose=True)

    print(f"\n✅ 自定义配对完成！")
    print(f"   - 标准配对: {len(dataset.get_paired_events())} 事件")
    print(f"   - 高能量配对: {len(df_custom)} 事件")


if __name__ == "__main__":
    example_custom_features()
    example_custom_pairing()
