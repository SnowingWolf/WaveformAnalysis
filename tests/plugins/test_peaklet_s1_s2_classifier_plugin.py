"""Tests for PeakletS1S2ClassifierPlugin."""

from __future__ import annotations

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    LABEL_S1,
    LABEL_S2,
    LABEL_UNKNOWN,
    PEAKS_DTYPE,
    PeakletS1S2ClassifierPlugin,
)


def _make_peaks(n: int = 3) -> np.ndarray:
    """创建测试用的 peaks 数据"""
    peaks = np.zeros(n, dtype=PEAKS_DTYPE)

    # Peak 0: S1 候选（窄脉冲，快速上升/下降，小面积，少量 hits）
    peaks[0]["peak_id"] = 0
    peaks[0]["time_start"] = 1000
    peaks[0]["time_end"] = 1050
    peaks[0]["time_peak"] = 1025
    peaks[0]["center_time"] = 1025
    peaks[0]["width"] = 50.0  # 50 ns
    peaks[0]["area"] = 100.0
    peaks[0]["height"] = 10.0
    peaks[0]["rise_time"] = 10.0  # 10 ns
    peaks[0]["fall_time"] = 15.0  # 15 ns
    peaks[0]["rise_time_10_50"] = 5.0  # 5 ns (快速上升)
    peaks[0]["width_25_75"] = 20.0
    peaks[0]["range_90p_area"] = 40.0
    peaks[0]["n_hits"] = 5
    peaks[0]["n_channels"] = 3

    # Peak 1: S2 候选（宽脉冲，慢速上升/下降，大面积，大量 hits）
    peaks[1]["peak_id"] = 1
    peaks[1]["time_start"] = 2000
    peaks[1]["time_end"] = 2500
    peaks[1]["time_peak"] = 2250
    peaks[1]["center_time"] = 2250
    peaks[1]["width"] = 500.0  # 500 ns
    peaks[1]["area"] = 5000.0
    peaks[1]["height"] = 50.0
    peaks[1]["rise_time"] = 100.0  # 100 ns
    peaks[1]["fall_time"] = 200.0  # 200 ns
    peaks[1]["rise_time_10_50"] = 120.0  # 120 ns (慢速上升)
    peaks[1]["width_25_75"] = 300.0
    peaks[1]["range_90p_area"] = 450.0
    peaks[1]["n_hits"] = 20
    peaks[1]["n_channels"] = 10

    # Peak 2: 边界情况（不明显）
    peaks[2]["peak_id"] = 2
    peaks[2]["time_start"] = 3000
    peaks[2]["time_end"] = 3150
    peaks[2]["time_peak"] = 3075
    peaks[2]["center_time"] = 3075
    peaks[2]["width"] = 150.0  # 150 ns
    peaks[2]["area"] = 500.0
    peaks[2]["height"] = 15.0
    peaks[2]["rise_time"] = 50.0  # 50 ns
    peaks[2]["fall_time"] = 50.0  # 50 ns
    peaks[2]["rise_time_10_50"] = 30.0  # 30 ns
    peaks[2]["width_25_75"] = 80.0
    peaks[2]["range_90p_area"] = 120.0
    peaks[2]["n_hits"] = 10
    peaks[2]["n_channels"] = 5

    return peaks


def test_peaklet_s1_s2_classifier_basic(tmp_path):
    """测试基本的 S1/S2 分类功能"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "peaks")] = _make_peaks()

    # 配置分类范围（使用字典配置）
    ctx.set_config(
        {
            # S1: 窄脉冲，快速，小面积
            "s1_ranges": {
                "width": (0.0, 100.0),
                "area": (0.0, 500.0),
                "rise_time": (0.0, 30.0),
                "fall_time": (0.0, 50.0),
            },
            # S2: 宽脉冲，大面积
            "s2_ranges": {
                "width": (300.0, None),
                "area": (1000.0, None),
            },
            # 不满足条件时返回 Unknown
            "default_label": "unknown",
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")

    assert len(labels) == 3
    assert labels[0]["peak_id"] == 0
    assert labels[0]["label"] == LABEL_S1
    assert labels[1]["peak_id"] == 1
    assert labels[1]["label"] == LABEL_S2
    assert labels[2]["peak_id"] == 2
    assert labels[2]["label"] == LABEL_UNKNOWN


def test_peaklet_s1_s2_classifier_empty(tmp_path):
    """测试空输入"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "peaks")] = np.zeros(0, dtype=PEAKS_DTYPE)

    ctx.set_config(
        {
            "s1_ranges": {"width": (0.0, 100.0)},
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")
    assert len(labels) == 0


def test_peaklet_s1_s2_classifier_conflict_prefer_s1(tmp_path):
    """测试冲突策略：prefer_s1"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    peaks = np.zeros(1, dtype=PEAKS_DTYPE)
    peaks[0]["peak_id"] = 0
    peaks[0]["width"] = 50.0
    peaks[0]["area"] = 100.0
    peaks[0]["n_channels"] = 3

    ctx._results[(run_id, "peaks")] = peaks

    # 配置使得同时满足 S1 和 S2 条件
    ctx.set_config(
        {
            "s1_ranges": {"width": (0.0, 100.0)},
            "s2_ranges": {"width": (0.0, 100.0)},
            "conflict_policy": "prefer_s1",
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")
    assert len(labels) == 1
    assert labels[0]["label"] == LABEL_S1


def test_peaklet_s1_s2_classifier_conflict_prefer_s2(tmp_path):
    """测试冲突策略：prefer_s2"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    peaks = np.zeros(1, dtype=PEAKS_DTYPE)
    peaks[0]["peak_id"] = 0
    peaks[0]["width"] = 50.0
    peaks[0]["area"] = 100.0
    peaks[0]["n_channels"] = 3

    ctx._results[(run_id, "peaks")] = peaks

    # 配置使得同时满足 S1 和 S2 条件
    ctx.set_config(
        {
            "s1_ranges": {"width": (0.0, 100.0)},
            "s2_ranges": {"width": (0.0, 100.0)},
            "conflict_policy": "prefer_s2",
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")
    assert len(labels) == 1
    assert labels[0]["label"] == LABEL_S2


def test_peaklet_s1_s2_classifier_conflict_unknown(tmp_path):
    """测试冲突策略：unknown"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    peaks = np.zeros(1, dtype=PEAKS_DTYPE)
    peaks[0]["peak_id"] = 0
    peaks[0]["width"] = 50.0
    peaks[0]["area"] = 100.0
    peaks[0]["n_channels"] = 3

    ctx._results[(run_id, "peaks")] = peaks

    # 配置使得同时满足 S1 和 S2 条件
    ctx.set_config(
        {
            "s1_ranges": {"width": (0.0, 100.0)},
            "s2_ranges": {"width": (0.0, 100.0)},
            "conflict_policy": "unknown",
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")
    assert len(labels) == 1
    assert labels[0]["label"] == LABEL_UNKNOWN


def test_peaklet_s1_s2_classifier_strict_mode(tmp_path):
    """测试严格模式：未配置任何条件时报错"""
    ctx = Context(storage_dir=str(tmp_path))

    # 创建一个插件实例并手动覆盖默认配置
    plugin = PeakletS1S2ClassifierPlugin()
    plugin.options["s1_ranges"].default = None
    plugin.options["s2_ranges"].default = None

    ctx.register(plugin)

    run_id = "run_001"
    ctx._results[(run_id, "peaks")] = _make_peaks()

    ctx.set_config(
        {
            "strict": True,
        },
        plugin_name="peaklet_s1_s2",
    )

    with pytest.raises(RuntimeError, match="No S1/S2 criteria configured"):
        ctx.get_data(run_id, "peaklet_s1_s2")


def test_peaklet_s1_s2_classifier_n_channels_filter(tmp_path):
    """测试通道数过滤功能"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "peaks")] = _make_peaks()

    # 仅使用 n_channels 进行过滤，不使用 width
    ctx.set_config(
        {
            "s1_ranges": {"n_channels": (1, 4)},
            "s2_ranges": {"n_channels": (5, None)},
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")

    assert len(labels) == 3
    # Peak 0: n_channels=3, 满足 S1
    assert labels[0]["label"] == LABEL_S1
    # Peak 1: n_channels=10, 满足 S2
    assert labels[1]["label"] == LABEL_S2
    # Peak 2: n_channels=5, 满足 S2
    assert labels[2]["label"] == LABEL_S2


def test_peaklet_s1_s2_classifier_output_fields(tmp_path):
    """测试输出字段完整性"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "peaks")] = _make_peaks()

    ctx.set_config(
        {
            "s1_ranges": {"width": (0.0, 100.0)},
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")

    # 检查字段：仅 peak_id 和 label
    expected_fields = {
        "peak_id",
        "label",
    }
    assert set(labels.dtype.names) == expected_fields

    # 检查第一个 peak 的字段值
    assert labels[0]["peak_id"] == 0
    assert labels[0]["label"] == LABEL_S1


def test_peaklet_s1_s2_classifier_n_hits_filter(tmp_path):
    """测试 n_hits 范围过滤功能"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "peaks")] = _make_peaks()

    # 使用 n_hits 进行过滤
    # Peak 0: n_hits=5, Peak 1: n_hits=20, Peak 2: n_hits=10
    ctx.set_config(
        {
            "s1_ranges": {"n_hits": (1, 7)},  # 仅 Peak 0 满足
            "s2_ranges": {"n_hits": (8, None)},  # Peak 1 和 2 满足
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")

    assert len(labels) == 3
    assert labels[0]["label"] == LABEL_S1  # n_hits=5
    assert labels[1]["label"] == LABEL_S2  # n_hits=20
    assert labels[2]["label"] == LABEL_S2  # n_hits=10


def test_peaklet_s1_s2_classifier_rise_time_10_50_filter(tmp_path):
    """测试 rise_time_10_50 范围过滤功能"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "peaks")] = _make_peaks()

    # 使用 rise_time_10_50 进行过滤
    # Peak 0: 5.0 ns, Peak 1: 120.0 ns, Peak 2: 30.0 ns
    ctx.set_config(
        {
            "s1_ranges": {"rise_time_10_50": (0.0, 50.0)},  # Peak 0 和 2 满足
            "s2_ranges": {"rise_time_10_50": (100.0, None)},  # 仅 Peak 1 满足
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")

    assert len(labels) == 3
    assert labels[0]["label"] == LABEL_S1  # rise_time_10_50=5.0
    assert labels[1]["label"] == LABEL_S2  # rise_time_10_50=120.0
    assert labels[2]["label"] == LABEL_S1  # rise_time_10_50=30.0


def test_peaklet_s1_s2_classifier_combined_s2_criteria(tmp_path):
    """测试组合条件：n_hits >= 8 且 rise_time_10_50 >= 100"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "peaks")] = _make_peaks()

    # 组合条件：同时满足 n_hits >= 8 AND rise_time_10_50 >= 100
    ctx.set_config(
        {
            "s1_ranges": None,  # 不配置 S1
            "s2_ranges": {
                "n_hits": (8, None),
                "rise_time_10_50": (100.0, None),
            },
            "default_label": "unknown",  # 不满足 S2 时返回 Unknown
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")

    assert len(labels) == 3
    # Peak 0: n_hits=5, rise_time_10_50=5.0 -> Unknown (两个都不满足)
    assert labels[0]["label"] == LABEL_UNKNOWN
    # Peak 1: n_hits=20, rise_time_10_50=120.0 -> S2 (两个都满足)
    assert labels[1]["label"] == LABEL_S2
    # Peak 2: n_hits=10, rise_time_10_50=30.0 -> Unknown (只满足 n_hits)
    assert labels[2]["label"] == LABEL_UNKNOWN
