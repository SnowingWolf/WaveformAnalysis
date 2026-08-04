"""S1-S2 配对插件测试

测试 S1S2PairCandidatesPlugin 的候选生成功能。
测试 S1S2PairSelectionPlugin 的选择功能。

Author: Claude Code
Version: 0.1.0
"""

import numpy as np
import pytest

from waveform_analysis.core.plugins.builtin.cpu.peak_classification import (
    LABEL_S1,
    LABEL_S1_S2,
    LABEL_S2,
    LABEL_UNKNOWN,
    PEAK_CLASSIFICATION_DTYPE,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklets import PEAKS_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates import (
    FLAG_CLOSE_COMPETITOR,
    FLAG_MULTI_S1_CANDIDATE,
    FLAG_MULTI_S2_CANDIDATE,
    FLAG_ORPHAN_S1,
    FLAG_ORPHAN_S2,
    FLAG_VALID_TIME,
    S1_S2_PAIR_CANDIDATES_DTYPE,
    S1S2PairCandidatesPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_selection import (
    S1S2PairSelectionPlugin,
)

# ============================================================================
# 辅助函数: 创建测试数据
# ============================================================================


def create_test_peak(
    peak_id: int, time_ns: float, area: float, width_ns: float = 100.0, n_channels: int = 5
):
    """创建测试 peak"""
    time_ps = int(time_ns * 1000)  # ns -> ps
    width_ps = int(width_ns * 1000)  # ns -> ps for timestamp bounds

    peak = np.zeros(1, dtype=PEAKS_DTYPE)[0]
    peak["peak_id"] = peak_id
    peak["center_time"] = time_ps
    peak["time_start"] = time_ps - width_ps // 2
    peak["time_peak"] = time_ps
    peak["time_end"] = time_ps + width_ps // 2
    peak["area"] = area
    peak["height"] = area / 10.0
    peak["width"] = width_ns
    peak["n_channels"] = n_channels

    return peak


def create_test_label(peak_id: int, label: int):
    """创建测试 S1/S2 标签"""
    row = np.zeros(1, dtype=PEAK_CLASSIFICATION_DTYPE)[0]
    row["peak_id"] = peak_id
    row["label"] = label
    return row


class MockContext:
    """Mock Context 用于测试"""

    def __init__(self):
        self._data = {}
        self._config = {}

    def get_data(self, run_id: str, data_name: str):
        return self._data.get((run_id, data_name))

    def set_data(self, run_id: str, data_name: str, data):
        self._data[(run_id, data_name)] = data

    def get_config(self, plugin, option_name: str):
        key = (plugin.__class__.__name__, option_name)
        if key in self._config:
            return self._config[key]
        # 返回默认值
        return plugin.options[option_name].default

    def set_config(self, config: dict, plugin_name: str = None):
        for key, value in config.items():
            self._config[(plugin_name or "S1S2PairCandidatesPlugin", key)] = value


# ============================================================================
# 测试用例
# ============================================================================


def test_basic_pairing_one_to_one():
    """测试基本配对: 1 S1 - 1 S2"""
    # 创建测试数据
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=100, width_ns=120.0),  # S1
            create_test_peak(peak_id=2, time_ns=20000, area=5000, width_ns=640.0),  # S2
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S2),
        ]
    )

    # 初始化插件和 context
    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)

    # 执行
    candidates = plugin.compute(ctx, "test_run")

    # 验证
    assert len(candidates) == 1, "应该有 1 个候选对"

    cand = candidates[0]
    assert cand["s1_peak_id"] == 1
    assert cand["s2_peak_id"] == 2
    assert cand["drift_time_ns"] == pytest.approx(19000.0, rel=1e-3)  # 20000 - 1000
    assert cand["s1_area"] == pytest.approx(100.0)
    assert cand["s2_area"] == pytest.approx(5000.0)
    assert cand["s1_width"] == pytest.approx(120.0)
    assert cand["s2_width"] == pytest.approx(640.0)
    assert cand["log10_s2_s1"] == pytest.approx(np.log10(5000 / 100), rel=1e-3)
    assert cand["n_s1_candidates_for_s2"] == 1
    assert cand["n_s2_candidates_for_s1"] == 1
    assert cand["flags"] & FLAG_VALID_TIME
    assert not (cand["flags"] & FLAG_MULTI_S1_CANDIDATE)
    assert not cand["selected"]  # 第一层不设置 selected


def test_multiple_s1_for_one_s2():
    """测试 1 S2 对应多个 S1 候选"""
    # 创建测试数据: 3 个 S1, 1 个 S2
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=100),  # S1_A
            create_test_peak(peak_id=2, time_ns=2000, area=150),  # S1_B
            create_test_peak(peak_id=3, time_ns=3000, area=200),  # S1_C
            create_test_peak(peak_id=10, time_ns=20000, area=5000),  # S2_X
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S1),
            create_test_label(peak_id=3, label=LABEL_S1),
            create_test_label(peak_id=10, label=LABEL_S2),
        ]
    )

    # 初始化
    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)

    # 执行
    candidates = plugin.compute(ctx, "test_run")

    # 验证
    assert len(candidates) == 3, "应该有 3 个候选对"

    # 所有候选应该属于同一个 S2
    assert all(c["s2_peak_id"] == 10 for c in candidates)

    # S1 应该是 1, 2, 3
    s1_ids = sorted([c["s1_peak_id"] for c in candidates])
    assert s1_ids == [1, 2, 3]

    # 验证 drift_time
    drift_times = sorted([c["drift_time_ns"] for c in candidates])
    assert drift_times[0] == pytest.approx(17000.0, rel=1e-3)  # 20000 - 3000
    assert drift_times[1] == pytest.approx(18000.0, rel=1e-3)  # 20000 - 2000
    assert drift_times[2] == pytest.approx(19000.0, rel=1e-3)  # 20000 - 1000

    # 验证 ambiguity 标志
    for cand in candidates:
        assert cand["n_s1_candidates_for_s2"] == 3
        assert cand["n_s2_candidates_for_s1"] == 1
        assert cand["flags"] & FLAG_MULTI_S1_CANDIDATE
        assert not (cand["flags"] & FLAG_MULTI_S2_CANDIDATE)


def test_time_window_filtering():
    """测试时间窗口筛选"""
    # 创建测试数据: S2 在 20000 ns, max_drift_time = 10000 ns
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=5000, area=100),  # 在窗口外 (drift=15000)
            create_test_peak(peak_id=2, time_ns=12000, area=150),  # 在窗口内 (drift=8000)
            create_test_peak(peak_id=3, time_ns=19000, area=200),  # 在窗口内 (drift=1000)
            create_test_peak(peak_id=10, time_ns=20000, area=5000),  # S2
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S1),
            create_test_label(peak_id=3, label=LABEL_S1),
            create_test_label(peak_id=10, label=LABEL_S2),
        ]
    )

    # 初始化
    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)
    ctx.set_config({"max_drift_time": 10000.0})  # 10 μs

    # 执行
    candidates = plugin.compute(ctx, "test_run")

    # 验证
    assert len(candidates) == 2, "应该有 2 个候选对 (S1_2 和 S1_3)"

    s1_ids = sorted([c["s1_peak_id"] for c in candidates])
    assert s1_ids == [2, 3], "S1_1 应该被时间窗口过滤掉"


def test_multiple_s2_for_one_s1_sets_multi_s2_flag():
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=100),
            create_test_peak(peak_id=10, time_ns=20000, area=5000),
            create_test_peak(peak_id=11, time_ns=25000, area=6000),
        ]
    )
    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=10, label=LABEL_S2),
            create_test_label(peak_id=11, label=LABEL_S2),
        ]
    )

    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)

    candidates = plugin.compute(ctx, "test_run")

    assert len(candidates) == 2
    for cand in candidates:
        assert cand["n_s2_candidates_for_s1"] == 2
        assert cand["flags"] & FLAG_MULTI_S2_CANDIDATE


def test_candidate_ambiguity_counts_large_vectorized_window():
    s1_count = 12
    s2_count = 5
    peaks = np.array(
        [
            *[
                create_test_peak(peak_id=i + 1, time_ns=1000 + i * 100, area=100 + i)
                for i in range(s1_count)
            ],
            *[
                create_test_peak(peak_id=100 + i, time_ns=20000 + i * 100, area=5000 + i)
                for i in range(s2_count)
            ],
        ]
    )
    labels = np.array(
        [
            *[create_test_label(peak_id=i + 1, label=LABEL_S1) for i in range(s1_count)],
            *[create_test_label(peak_id=100 + i, label=LABEL_S2) for i in range(s2_count)],
        ]
    )

    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)

    candidates = plugin.compute(ctx, "test_run")

    assert len(candidates) == s1_count * s2_count
    np.testing.assert_array_equal(candidates["pair_id"], np.arange(len(candidates)))
    assert np.all(candidates["n_s1_candidates_for_s2"] == s1_count)
    assert np.all(candidates["n_s2_candidates_for_s1"] == s2_count)
    assert np.all(candidates["flags"] & FLAG_MULTI_S1_CANDIDATE)
    assert np.all(candidates["flags"] & FLAG_MULTI_S2_CANDIDATE)


def test_pair_candidates_ignore_unknown_and_s1_s2_labels():
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=100),
            create_test_peak(peak_id=2, time_ns=2000, area=100),
            create_test_peak(peak_id=3, time_ns=3000, area=100),
            create_test_peak(peak_id=10, time_ns=20000, area=5000),
        ]
    )
    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_UNKNOWN),
            create_test_label(peak_id=3, label=LABEL_S1_S2),
            create_test_label(peak_id=10, label=LABEL_S2),
        ]
    )

    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)

    candidates = plugin.compute(ctx, "test_run")

    assert len(candidates) == 1
    assert int(candidates[0]["s1_peak_id"]) == 1


def test_causality_s2_before_s1():
    """测试时间因果性: S2 在 S1 之前应该被过滤"""
    # S2 在 S1 之前
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=20000, area=100),  # S1
            create_test_peak(peak_id=2, time_ns=10000, area=5000),  # S2 (在 S1 之前!)
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S2),
        ]
    )

    # 初始化
    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)

    # 执行
    candidates = plugin.compute(ctx, "test_run")

    # 验证
    assert len(candidates) == 0, "S2 在 S1 之前,应该没有候选对"


def test_empty_input():
    """测试空输入"""
    peaks = np.array([], dtype=PEAKS_DTYPE)
    labels = np.array([], dtype=PEAK_CLASSIFICATION_DTYPE)

    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)

    # 执行
    candidates = plugin.compute(ctx, "test_run")

    # 验证
    assert len(candidates) == 0
    assert candidates.dtype == S1_S2_PAIR_CANDIDATES_DTYPE


def test_orphan_s1():
    """测试孤立 S1"""
    # 1 个 S1, 没有 S2
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=100, width_ns=85.0),  # S1
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
        ]
    )

    # 不允许孤立 S1
    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)
    ctx.set_config({"allow_orphan_s1": False})

    candidates = plugin.compute(ctx, "test_run")
    assert len(candidates) == 0, "不允许孤立 S1 时应该没有输出"

    # 允许孤立 S1
    ctx.set_config({"allow_orphan_s1": True})
    candidates = plugin.compute(ctx, "test_run")

    assert len(candidates) == 1, "应该有 1 个孤立 S1 记录"
    assert candidates[0]["s1_peak_id"] == 1
    assert candidates[0]["s2_peak_id"] == -1  # 标记缺失
    assert candidates[0]["s1_width"] == pytest.approx(85.0)
    assert candidates[0]["flags"] & FLAG_ORPHAN_S1


def test_orphan_s2():
    """测试孤立 S2"""
    # 1 个 S2, 没有 S1
    peaks = np.array(
        [
            create_test_peak(peak_id=10, time_ns=20000, area=5000, width_ns=720.0),  # S2
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=10, label=LABEL_S2),
        ]
    )

    # 允许孤立 S2
    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)
    ctx.set_config({"allow_orphan_s2": True})

    candidates = plugin.compute(ctx, "test_run")

    assert len(candidates) == 1, "应该有 1 个孤立 S2 记录"
    assert candidates[0]["s1_peak_id"] == -1  # 标记缺失
    assert candidates[0]["s2_peak_id"] == 10
    assert candidates[0]["s2_width"] == pytest.approx(720.0)
    assert candidates[0]["flags"] & FLAG_ORPHAN_S2


def test_min_area_threshold():
    """测试最小面积阈值"""
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=50),  # S1 (面积小)
            create_test_peak(peak_id=2, time_ns=2000, area=150),  # S1 (面积大)
            create_test_peak(peak_id=10, time_ns=20000, area=5000),  # S2
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S1),
            create_test_label(peak_id=10, label=LABEL_S2),
        ]
    )

    # 设置 min_s1_area = 100
    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)
    ctx.set_config({"min_s1_area": 100.0})

    candidates = plugin.compute(ctx, "test_run")

    # 验证: 只有 S1_2 满足阈值
    assert len(candidates) == 1
    assert candidates[0]["s1_peak_id"] == 2
    assert candidates[0]["s1_area"] >= 100.0


def test_log10_s2_s1_calculation():
    """测试 log10(S2/S1) 计算"""
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=100),  # S1
            create_test_peak(peak_id=2, time_ns=20000, area=10000),  # S2
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S2),
        ]
    )

    plugin = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)

    candidates = plugin.compute(ctx, "test_run")

    expected_log10 = np.log10(10000 / 100)  # log10(100) = 2.0
    assert candidates[0]["log10_s2_s1"] == pytest.approx(expected_log10, rel=1e-3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============================================================================
# 选择插件测试
# ============================================================================


def test_selection_largest_mode():
    """测试 largest 模式: 选择面积最大的 S1"""
    # 创建候选: S2 有 3 个 S1 候选,面积分别为 100, 200, 150
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=100),
            create_test_peak(peak_id=2, time_ns=2000, area=200),  # 最大
            create_test_peak(peak_id=3, time_ns=3000, area=150),
            create_test_peak(peak_id=10, time_ns=20000, area=5000),
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S1),
            create_test_label(peak_id=3, label=LABEL_S1),
            create_test_label(peak_id=10, label=LABEL_S2),
        ]
    )

    # 生成候选
    plugin_cand = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)

    candidates = plugin_cand.compute(ctx, "test_run")
    assert len(candidates) == 3

    # 选择
    plugin_sel = S1S2PairSelectionPlugin()
    ctx.set_data("test_run", "s1_s2_pair_candidates", candidates)
    ctx.set_config({"selection_mode": "largest"}, plugin_name="S1S2PairSelectionPlugin")

    pairs = plugin_sel.compute(ctx, "test_run")

    # 验证: 应该选择 S1_2 (area=200)
    selected = pairs[pairs["selected"]]
    assert len(selected) == 1, "应该只有 1 个被选中"
    assert selected[0]["s1_peak_id"] == 2, "应该选择面积最大的 S1_2"
    assert selected[0]["s1_area"] == pytest.approx(200.0)


def test_selection_scores_computed():
    """测试 score 是否正确计算"""
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=100),
            create_test_peak(peak_id=2, time_ns=2000, area=200),
            create_test_peak(peak_id=10, time_ns=20000, area=5000),
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S1),
            create_test_label(peak_id=10, label=LABEL_S2),
        ]
    )

    # 生成候选
    plugin_cand = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)
    candidates = plugin_cand.compute(ctx, "test_run")

    # 选择
    plugin_sel = S1S2PairSelectionPlugin()
    ctx.set_data("test_run", "s1_s2_pair_candidates", candidates)
    pairs = plugin_sel.compute(ctx, "test_run")

    # 验证 score
    for pair in pairs:
        assert pair["score_total"] > 0, "score_total 应该被计算"
        assert pair["score_s1_quality"] > 0, "score_s1_quality 应该被计算"


def test_selection_delta_score():
    """测试 delta_score_to_next_best 计算"""
    # S1 面积相近 (竞争激烈)
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=200),
            create_test_peak(peak_id=2, time_ns=2000, area=195),  # 接近
            create_test_peak(peak_id=10, time_ns=20000, area=5000),
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S1),
            create_test_label(peak_id=10, label=LABEL_S2),
        ]
    )

    # 生成候选和选择
    plugin_cand = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)
    candidates = plugin_cand.compute(ctx, "test_run")

    plugin_sel = S1S2PairSelectionPlugin()
    ctx.set_data("test_run", "s1_s2_pair_candidates", candidates)
    pairs = plugin_sel.compute(ctx, "test_run")

    # 验证
    selected = pairs[pairs["selected"]][0]
    assert selected["delta_score_to_next_best"] < 0.1, "分数差应该很小 (竞争激烈)"
    assert selected["flags"] & FLAG_CLOSE_COMPETITOR, "应该标记 CLOSE_COMPETITOR"


def test_selection_rank_for_s2():
    """测试 rank_for_s2 计算"""
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=100),
            create_test_peak(peak_id=2, time_ns=2000, area=200),
            create_test_peak(peak_id=3, time_ns=3000, area=150),
            create_test_peak(peak_id=10, time_ns=20000, area=5000),
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S1),
            create_test_label(peak_id=3, label=LABEL_S1),
            create_test_label(peak_id=10, label=LABEL_S2),
        ]
    )

    # 生成和选择
    plugin_cand = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)
    candidates = plugin_cand.compute(ctx, "test_run")

    plugin_sel = S1S2PairSelectionPlugin()
    ctx.set_data("test_run", "s1_s2_pair_candidates", candidates)
    pairs = plugin_sel.compute(ctx, "test_run")

    # 验证排名
    # S1_2 (area=200) 应该排第 1
    # S1_3 (area=150) 应该排第 2
    # S1_1 (area=100) 应该排第 3
    ranks = {}
    for pair in pairs:
        ranks[pair["s1_peak_id"]] = pair["rank_for_s2"]

    assert ranks[2] == 1, "S1_2 (最大) 应该排第 1"
    assert ranks[3] == 2, "S1_3 (中等) 应该排第 2"
    assert ranks[1] == 3, "S1_1 (最小) 应该排第 3"


def test_selection_all_mode():
    """测试 all 模式: 保留所有候选"""
    peaks = np.array(
        [
            create_test_peak(peak_id=1, time_ns=1000, area=100),
            create_test_peak(peak_id=2, time_ns=2000, area=200),
            create_test_peak(peak_id=10, time_ns=20000, area=5000),
        ]
    )

    labels = np.array(
        [
            create_test_label(peak_id=1, label=LABEL_S1),
            create_test_label(peak_id=2, label=LABEL_S1),
            create_test_label(peak_id=10, label=LABEL_S2),
        ]
    )

    # 生成候选
    plugin_cand = S1S2PairCandidatesPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "peaks", peaks)
    ctx.set_data("test_run", "peak_classification", labels)
    candidates = plugin_cand.compute(ctx, "test_run")

    # 选择 (all 模式)
    plugin_sel = S1S2PairSelectionPlugin()
    ctx.set_data("test_run", "s1_s2_pair_candidates", candidates)
    ctx.set_config({"selection_mode": "all"}, plugin_name="S1S2PairSelectionPlugin")
    pairs = plugin_sel.compute(ctx, "test_run")

    # 验证: 所有候选都应该 selected
    assert np.all(pairs["selected"]), "all 模式下所有候选都应该 selected"
    assert len(pairs[pairs["selected"]]) == 2, "应该有 2 个候选"


def test_selection_empty_input():
    """测试空输入"""
    candidates = np.zeros(0, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)

    plugin = S1S2PairSelectionPlugin()
    ctx = MockContext()
    ctx.set_data("test_run", "s1_s2_pair_candidates", candidates)

    pairs = plugin.compute(ctx, "test_run")

    assert len(pairs) == 0
    assert pairs.dtype == S1_S2_PAIR_CANDIDATES_DTYPE
