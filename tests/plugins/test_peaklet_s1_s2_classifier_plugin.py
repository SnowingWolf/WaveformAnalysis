"""Tests for PeakletS1S2ClassifierPlugin."""

from __future__ import annotations

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    LABEL_S1,
    LABEL_S2,
    LABEL_UNKNOWN,
    PEAKLET_DTYPE,
    PEAKLET_FEATURES_DTYPE,
    PeakletS1S2ClassifierPlugin,
)


def _make_peaklet_features(n: int = 3) -> np.ndarray:
    """创建测试用的 peaklet_features 数据"""
    features = np.zeros(n, dtype=PEAKLET_FEATURES_DTYPE)

    # Peaklet 0: S1 候选（窄脉冲，快速上升/下降，小面积）
    features[0]["peak_id"] = 0
    features[0]["time_start"] = 1000
    features[0]["time_end"] = 1050
    features[0]["time_peak"] = 1025
    features[0]["width"] = 50.0  # 50 ns
    features[0]["area"] = 100.0
    features[0]["height"] = 10.0
    features[0]["rise_time"] = 10.0  # 10 ns
    features[0]["fall_time"] = 15.0  # 15 ns

    # Peaklet 1: S2 候选（宽脉冲，慢速上升/下降，大面积）
    features[1]["peak_id"] = 1
    features[1]["time_start"] = 2000
    features[1]["time_end"] = 2500
    features[1]["time_peak"] = 2250
    features[1]["width"] = 500.0  # 500 ns
    features[1]["area"] = 5000.0
    features[1]["height"] = 50.0
    features[1]["rise_time"] = 100.0  # 100 ns
    features[1]["fall_time"] = 200.0  # 200 ns

    # Peaklet 2: 边界情况（不明显）
    features[2]["peak_id"] = 2
    features[2]["time_start"] = 3000
    features[2]["time_end"] = 3150
    features[2]["time_peak"] = 3075
    features[2]["width"] = 150.0  # 150 ns
    features[2]["area"] = 500.0
    features[2]["height"] = 15.0
    features[2]["rise_time"] = 50.0  # 50 ns
    features[2]["fall_time"] = 50.0  # 50 ns

    return features


def _make_peaklets(n: int = 3) -> np.ndarray:
    """创建测试用的 peaklets 数据"""
    peaklets = np.zeros(n, dtype=PEAKLET_DTYPE)

    peaklets[0]["time_start"] = 1000
    peaklets[0]["time_end"] = 1050
    peaklets[0]["center_time"] = 1025
    peaklets[0]["n_hits"] = 5
    peaklets[0]["n_channels"] = 3

    peaklets[1]["time_start"] = 2000
    peaklets[1]["time_end"] = 2500
    peaklets[1]["center_time"] = 2250
    peaklets[1]["n_hits"] = 20
    peaklets[1]["n_channels"] = 10

    peaklets[2]["time_start"] = 3000
    peaklets[2]["time_end"] = 3150
    peaklets[2]["center_time"] = 3075
    peaklets[2]["n_hits"] = 10
    peaklets[2]["n_channels"] = 5

    return peaklets


def test_peaklet_s1_s2_classifier_basic(tmp_path):
    """测试基本的 S1/S2 分类功能"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "peaklet_features")] = _make_peaklet_features()
    ctx._results[(run_id, "peaklets")] = _make_peaklets()

    # 配置分类范围
    ctx.set_config(
        {
            # S1: 窄脉冲，快速，小面积
            "s1_width_range": (0.0, 100.0),
            "s1_area_range": (0.0, 500.0),
            "s1_rise_time_range": (0.0, 30.0),
            "s1_fall_time_range": (0.0, 50.0),
            # S2: 宽脉冲，大面积
            "s2_width_range": (300.0, None),
            "s2_area_range": (1000.0, None),
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
    ctx._results[(run_id, "peaklet_features")] = np.zeros(0, dtype=PEAKLET_FEATURES_DTYPE)
    ctx._results[(run_id, "peaklets")] = np.zeros(0, dtype=PEAKLET_DTYPE)

    ctx.set_config(
        {
            "s1_width_range": (0.0, 100.0),
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
    features = np.zeros(1, dtype=PEAKLET_FEATURES_DTYPE)
    features[0]["peak_id"] = 0
    features[0]["width"] = 50.0
    features[0]["area"] = 100.0

    peaklets = np.zeros(1, dtype=PEAKLET_DTYPE)
    peaklets[0]["n_channels"] = 3

    ctx._results[(run_id, "peaklet_features")] = features
    ctx._results[(run_id, "peaklets")] = peaklets

    # 配置使得同时满足 S1 和 S2 条件
    ctx.set_config(
        {
            "s1_width_range": (0.0, 100.0),
            "s2_width_range": (0.0, 100.0),
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
    features = np.zeros(1, dtype=PEAKLET_FEATURES_DTYPE)
    features[0]["peak_id"] = 0
    features[0]["width"] = 50.0
    features[0]["area"] = 100.0

    peaklets = np.zeros(1, dtype=PEAKLET_DTYPE)
    peaklets[0]["n_channels"] = 3

    ctx._results[(run_id, "peaklet_features")] = features
    ctx._results[(run_id, "peaklets")] = peaklets

    # 配置使得同时满足 S1 和 S2 条件
    ctx.set_config(
        {
            "s1_width_range": (0.0, 100.0),
            "s2_width_range": (0.0, 100.0),
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
    features = np.zeros(1, dtype=PEAKLET_FEATURES_DTYPE)
    features[0]["peak_id"] = 0
    features[0]["width"] = 50.0
    features[0]["area"] = 100.0

    peaklets = np.zeros(1, dtype=PEAKLET_DTYPE)
    peaklets[0]["n_channels"] = 3

    ctx._results[(run_id, "peaklet_features")] = features
    ctx._results[(run_id, "peaklets")] = peaklets

    # 配置使得同时满足 S1 和 S2 条件
    ctx.set_config(
        {
            "s1_width_range": (0.0, 100.0),
            "s2_width_range": (0.0, 100.0),
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
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "peaklet_features")] = _make_peaklet_features()
    ctx._results[(run_id, "peaklets")] = _make_peaklets()

    ctx.set_config(
        {
            "strict": True,
            # 不配置任何范围
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
    ctx._results[(run_id, "peaklet_features")] = _make_peaklet_features()
    ctx._results[(run_id, "peaklets")] = _make_peaklets()

    # 仅使用 n_channels 进行过滤，不使用 width
    ctx.set_config(
        {
            "s1_n_channels_range": (1, 4),
            "s2_n_channels_range": (5, None),
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")

    assert len(labels) == 3
    # Peaklet 0: n_channels=3, 满足 S1
    assert labels[0]["label"] == LABEL_S1
    # Peaklet 1: n_channels=10, 满足 S2
    assert labels[1]["label"] == LABEL_S2
    # Peaklet 2: n_channels=5, 满足 S2
    assert labels[2]["label"] == LABEL_S2


def test_peaklet_s1_s2_classifier_output_fields(tmp_path):
    """测试输出字段完整性"""
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PeakletS1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "peaklet_features")] = _make_peaklet_features()
    ctx._results[(run_id, "peaklets")] = _make_peaklets()

    ctx.set_config(
        {
            "s1_width_range": (0.0, 100.0),
        },
        plugin_name="peaklet_s1_s2",
    )

    labels = ctx.get_data(run_id, "peaklet_s1_s2")

    # 检查所有字段都存在
    expected_fields = {
        "peak_id",
        "label",
        "width_ns",
        "area",
        "height",
        "rise_time_ns",
        "fall_time_ns",
        "n_hits",
        "n_channels",
        "time_start",
        "time_end",
        "time_peak",
    }
    assert set(labels.dtype.names) == expected_fields

    # 检查第一个 peaklet 的字段值
    assert labels[0]["peak_id"] == 0
    assert labels[0]["width_ns"] == 50.0
    assert labels[0]["area"] == 100.0
    assert labels[0]["height"] == 10.0
    assert labels[0]["rise_time_ns"] == 10.0
    assert labels[0]["fall_time_ns"] == 15.0
    assert labels[0]["n_hits"] == 5
    assert labels[0]["n_channels"] == 3
    assert labels[0]["time_start"] == 1000
    assert labels[0]["time_end"] == 1050
    assert labels[0]["time_peak"] == 1025
