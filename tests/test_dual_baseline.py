"""
测试双 Baseline 功能

验证 WaveformStruct 和 WaveformsPlugin 是否正确支持双 baseline 字段。
"""

import numpy as np


def test_record_dtype_has_both_baselines():
    """测试 ST_WAVEFORM_DTYPE 包含两个 baseline 字段"""
    import sys

    # 确保使用当前目录的模块
    if "." not in sys.path:
        sys.path.insert(0, ".")

    # 强制重新加载模块
    if "waveform_analysis.core.processing.dtypes" in sys.modules:
        del sys.modules["waveform_analysis.core.processing.dtypes"]

    from waveform_analysis.core.processing.dtypes import ST_WAVEFORM_DTYPE

    dtype = np.dtype(ST_WAVEFORM_DTYPE)
    field_names = list(dtype.names) if dtype.names else []

    print(f"Field names: {field_names}")

    assert "baseline" in field_names, "ST_WAVEFORM_DTYPE 应包含 baseline 字段"
    assert "baseline_upstream" in field_names, "ST_WAVEFORM_DTYPE 应包含 baseline_upstream 字段"

    # 验证字段类型
    assert dtype.fields["baseline"][0] == np.float64, "baseline 应为 float64"
    assert dtype.fields["baseline_upstream"][0] == np.float64, "baseline_upstream 应为 float64"

    print("✓ ST_WAVEFORM_DTYPE 包含两个 baseline 字段")


def test_create_record_dtype_has_both_baselines():
    """测试 create_record_dtype() 包含两个 baseline 字段"""
    from waveform_analysis.core.processing.dtypes import create_record_dtype

    dtype = create_record_dtype(1000)
    field_names = list(dtype.names)

    assert "baseline" in field_names
    assert "baseline_upstream" in field_names

    # 验证字段类型
    assert dtype.fields["baseline"][0] == np.float64
    assert dtype.fields["baseline_upstream"][0] == np.float64

    print("✓ create_record_dtype() 包含两个 baseline 字段")


def test_waveform_struct_without_upstream_baseline():
    """测试没有上游 baseline 的情况"""
    from waveform_analysis.core.plugins.builtin.cpu.waveforms import WaveformStruct

    # 创建测试数据（模拟 VX2730 CSV 格式）
    # 列: BOARD, CHANNEL, RECORD_LENGTH, TIMESTAMP, TRIGGER_ID, DC_OFFSET, BASELINE_START, BASELINE_END, 波形数据...
    n_events = 10
    wave_length = 800
    test_data = np.zeros((n_events, 807))  # 7 列元数据 + 800 列波形

    # 填充元数据
    test_data[:, 0] = 0  # BOARD
    test_data[:, 1] = 0  # CHANNEL
    test_data[:, 2] = wave_length  # RECORD_LENGTH
    test_data[:, 3] = np.arange(n_events) * 1000  # TIMESTAMP
    test_data[:, 4] = 0  # TRIGGER_ID
    test_data[:, 5] = 0  # DC_OFFSET
    test_data[:, 6] = 0  # BASELINE_START (索引)
    test_data[:, 7] = 50  # BASELINE_END (索引)

    # 填充波形数据（从第 7 列开始）
    test_data[:, 7:] = np.random.randn(n_events, wave_length) + 100

    waveforms = [test_data]

    # 不提供 upstream_baselines
    struct = WaveformStruct(waveforms)
    st_waveforms = struct.structure_waveforms()

    # 验证结果
    assert len(st_waveforms) == 1
    st_ch = st_waveforms[0]

    assert "baseline" in st_ch.dtype.names
    assert "baseline_upstream" in st_ch.dtype.names

    # baseline 应该是计算的值（接近 100）
    assert 99 < np.mean(st_ch["baseline"]) < 101

    # baseline_upstream 应该是 NaN
    assert np.all(np.isnan(st_ch["baseline_upstream"]))

    print("✓ 无上游 baseline 测试通过")


def test_waveform_struct_with_upstream_baseline():
    """测试有上游 baseline 的情况"""
    from waveform_analysis.core.plugins.builtin.cpu.waveforms import WaveformStruct

    # 创建测试数据
    n_events = 10
    wave_length = 800
    test_data = np.zeros((n_events, 807))

    # 填充元数据
    test_data[:, 0] = 0  # BOARD
    test_data[:, 1] = 0  # CHANNEL
    test_data[:, 2] = wave_length
    test_data[:, 3] = np.arange(n_events) * 1000
    test_data[:, 4] = 0
    test_data[:, 5] = 0
    test_data[:, 6] = 0
    test_data[:, 7] = 50

    # 填充波形数据
    test_data[:, 7:] = np.random.randn(n_events, wave_length) + 100

    waveforms = [test_data]

    # 提供上游 baseline（使用不同的值）
    upstream_baselines = [np.ones(n_events) * 95]

    # 创建 WaveformStruct
    struct = WaveformStruct(waveforms, upstream_baselines=upstream_baselines)
    st_waveforms = struct.structure_waveforms()

    # 验证结果
    st_ch = st_waveforms[0]

    # baseline 应该是计算的值（接近 100）
    assert 99 < np.mean(st_ch["baseline"]) < 101

    # baseline_upstream 应该是上游值（95）
    assert np.allclose(st_ch["baseline_upstream"], 95)

    print("✓ 有上游 baseline 测试通过")


def test_waveform_struct_upstream_baseline_length_mismatch():
    """测试上游 baseline 长度不匹配的情况"""
    from waveform_analysis.core.plugins.builtin.cpu.waveforms import WaveformStruct

    # 创建测试数据
    n_events = 10
    wave_length = 800
    test_data = np.zeros((n_events, 807))

    test_data[:, 0] = 0
    test_data[:, 1] = 0
    test_data[:, 2] = wave_length
    test_data[:, 3] = np.arange(n_events) * 1000
    test_data[:, 4] = 0
    test_data[:, 5] = 0
    test_data[:, 6] = 0
    test_data[:, 7] = 50
    test_data[:, 7:] = np.random.randn(n_events, wave_length) + 100

    waveforms = [test_data]

    # 提供长度不匹配的上游 baseline
    upstream_baselines = [np.ones(5) * 95]  # 只有 5 个，但应该有 10 个

    struct = WaveformStruct(waveforms, upstream_baselines=upstream_baselines)
    st_waveforms = struct.structure_waveforms()

    st_ch = st_waveforms[0]

    # baseline_upstream 应该是 NaN（因为长度不匹配）
    assert np.all(np.isnan(st_ch["baseline_upstream"]))

    print("✓ 上游 baseline 长度不匹配测试通过")


def test_waveform_struct_multiple_channels():
    """测试多通道情况"""
    from waveform_analysis.core.plugins.builtin.cpu.waveforms import WaveformStruct

    # 创建 3 个通道的测试数据
    n_events = 10
    wave_length = 800
    n_channels = 3

    waveforms = []
    upstream_baselines = []

    for ch in range(n_channels):
        test_data = np.zeros((n_events, 807))
        test_data[:, 0] = 0  # BOARD
        test_data[:, 1] = ch  # CHANNEL
        test_data[:, 2] = wave_length
        test_data[:, 3] = np.arange(n_events) * 1000
        test_data[:, 4] = 0
        test_data[:, 5] = 0
        test_data[:, 6] = 0
        test_data[:, 7] = 50
        test_data[:, 7:] = np.random.randn(n_events, wave_length) + 100

        waveforms.append(test_data)

        # 每个通道使用不同的上游 baseline
        upstream_baselines.append(np.ones(n_events) * (90 + ch * 5))

    struct = WaveformStruct(waveforms, upstream_baselines=upstream_baselines)
    st_waveforms = struct.structure_waveforms()

    # 验证每个通道
    for ch in range(n_channels):
        st_ch = st_waveforms[ch]

        # baseline 应该接近 100
        assert 99 < np.mean(st_ch["baseline"]) < 101

        # baseline_upstream 应该是对应通道的值
        expected_upstream = 90 + ch * 5
        assert np.allclose(st_ch["baseline_upstream"], expected_upstream)

    print("✓ 多通道测试通过")


if __name__ == "__main__":
    # 运行所有测试
    test_record_dtype_has_both_baselines()
    test_create_record_dtype_has_both_baselines()
    test_waveform_struct_without_upstream_baseline()
    test_waveform_struct_with_upstream_baseline()
    test_waveform_struct_upstream_baseline_length_mismatch()
    test_waveform_struct_multiple_channels()

    print("\n所有测试通过！✓")
