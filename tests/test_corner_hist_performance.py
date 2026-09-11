"""
corner_hist 性能和正确性测试

本模块测试 corner_hist 的优化效果，包括：
1. 数值一致性验证（Numba vs NumPy）
2. 性能基准测试（不同数据规模）
3. 边界情况测试
"""

import inspect
import time

import numpy as np
import pytest

# 尝试导入 matplotlib，如果不可用则跳过测试
pytest.importorskip("matplotlib")

from waveform_analysis.utils.visualization.statistical_plots import (
    _ensure_numba_histogram2d,
    _numba_histogram2d,
    _safe_histogram2d,
    _symlog_bin_edges,
    corner_hist,
)


class TestHistogram2DCorrectness:
    """测试 Numba 优化的 2D 直方图数值正确性"""

    def test_numba_vs_numpy_basic(self):
        """基本情况：Numba 结果应与 NumPy 一致"""
        np.random.seed(42)
        x = np.random.randn(10000)
        y = np.random.randn(10000)
        xbins = np.linspace(-3, 3, 50)
        ybins = np.linspace(-3, 3, 50)

        # NumPy 版本
        H_numpy, _, _ = np.histogram2d(x, y, bins=[xbins, ybins])
        H_numpy = H_numpy.T

        # Numba 版本
        H_numba = _safe_histogram2d(x, y, xbins, ybins, weights=None)

        # 验证数值一致性
        np.testing.assert_allclose(H_numpy, H_numba, rtol=1e-14, atol=0)

    def test_numba_vs_numpy_with_weights(self):
        """带权重的情况"""
        np.random.seed(43)
        x = np.random.randn(5000)
        y = np.random.randn(5000)
        weights = np.random.uniform(0.1, 2.0, 5000)
        xbins = np.linspace(-3, 3, 30)
        ybins = np.linspace(-3, 3, 30)

        # NumPy 版本
        H_numpy, _, _ = np.histogram2d(x, y, bins=[xbins, ybins], weights=weights)
        H_numpy = H_numpy.T

        # Numba 版本
        H_numba = _safe_histogram2d(x, y, xbins, ybins, weights=weights)

        # 验证数值一致性
        np.testing.assert_allclose(H_numpy, H_numba, rtol=1e-12, atol=1e-10)

    def test_numba_vs_numpy_logspace_bins(self):
        """对数刻度 bins"""
        np.random.seed(44)
        x = np.random.lognormal(0, 1, 10000)
        y = np.random.lognormal(1, 0.5, 10000)
        xbins = np.logspace(0, 3, 40)
        ybins = np.logspace(0, 3, 40)

        # NumPy 版本
        H_numpy, _, _ = np.histogram2d(x, y, bins=[xbins, ybins])
        H_numpy = H_numpy.T

        # Numba 版本
        H_numba = _safe_histogram2d(x, y, xbins, ybins, weights=None)

        # 验证数值一致性
        np.testing.assert_allclose(H_numpy, H_numba, rtol=1e-14, atol=0)

    def test_edge_cases_empty(self):
        """边界情况：空数据"""
        x = np.array([])
        y = np.array([])
        xbins = np.linspace(0, 10, 20)
        ybins = np.linspace(0, 10, 20)

        H_numpy, _, _ = np.histogram2d(x, y, bins=[xbins, ybins])
        H_numpy = H_numpy.T

        H_numba = _safe_histogram2d(x, y, xbins, ybins, weights=None)

        np.testing.assert_array_equal(H_numpy, H_numba)
        assert H_numba.sum() == 0

    def test_edge_cases_single_point(self):
        """边界情况：单点数据"""
        x = np.array([1.5])
        y = np.array([2.5])
        xbins = np.linspace(0, 10, 20)
        ybins = np.linspace(0, 10, 20)

        H_numpy, _, _ = np.histogram2d(x, y, bins=[xbins, ybins])
        H_numpy = H_numpy.T

        H_numba = _safe_histogram2d(x, y, xbins, ybins, weights=None)

        np.testing.assert_array_equal(H_numpy, H_numba)
        assert H_numba.sum() == 1

    def test_edge_cases_out_of_bounds(self):
        """边界情况：数据在 bins 范围外"""
        x = np.array([-10, -5, 15, 20])
        y = np.array([-10, -5, 15, 20])
        xbins = np.linspace(0, 10, 20)
        ybins = np.linspace(0, 10, 20)

        H_numpy, _, _ = np.histogram2d(x, y, bins=[xbins, ybins])
        H_numpy = H_numpy.T

        H_numba = _safe_histogram2d(x, y, xbins, ybins, weights=None)

        np.testing.assert_array_equal(H_numpy, H_numba)
        assert H_numba.sum() == 0  # 所有点都在范围外

    def test_rightmost_edges_match_numpy(self):
        xbins = np.array([-10.0, 0.0, 10.0])
        ybins = np.array([-5.0, 0.0, 5.0])
        x = np.array([-10.0, 0.0, 10.0])
        y = np.array([-5.0, 0.0, 5.0])

        expected, _, _ = np.histogram2d(x, y, bins=[xbins, ybins])
        actual = _safe_histogram2d(x, y, xbins, ybins)

        np.testing.assert_array_equal(actual, expected.T)
        assert actual.sum() == len(x)

    def test_different_dtypes(self):
        """测试不同数据类型"""
        np.random.seed(45)

        for dtype in [np.float32, np.float64, np.int32, np.int64]:
            x = np.random.randn(1000).astype(dtype)
            y = np.random.randn(1000).astype(dtype)
            xbins = np.linspace(-3, 3, 30)
            ybins = np.linspace(-3, 3, 30)

            H_numpy, _, _ = np.histogram2d(x, y, bins=[xbins, ybins])
            H_numpy = H_numpy.T

            H_numba = _safe_histogram2d(x, y, xbins, ybins, weights=None)

            # 不同 dtype 可能有微小差异（整数类型在边界上可能有不同的舍入行为）
            # 大部分 bin 应该完全一致，只有极少数边界点可能有 ±1 差异
            diff = np.abs(H_numpy - H_numba)
            max_diff = np.max(diff)
            n_mismatched = np.sum(diff > 0)

            # 验证：最大差异不超过 1，且不匹配的 bin 数量很少（< 1%）
            assert max_diff <= 1.0, f"dtype {dtype}: 最大差异 {max_diff} 超过 1"
            assert (
                n_mismatched < 0.01 * H_numpy.size
            ), f"dtype {dtype}: {n_mismatched}/{H_numpy.size} bins 不匹配（超过 1%）"


class TestCornerHistPerformance:
    """corner_hist 性能基准测试"""

    @pytest.mark.parametrize(
        "n_points,n_vars,desc",
        [
            (1_000, 3, "小规模-3变量"),
            (10_000, 5, "中规模-5变量"),
            (50_000, 5, "大规模-5变量"),
            (10_000, 8, "中规模-8变量"),
        ],
    )
    def test_corner_hist_performance(self, n_points, n_vars, desc):
        """性能基准测试：不同数据规模"""
        np.random.seed(100)
        data = [np.random.randn(n_points) for _ in range(n_vars)]
        names = [f"Var{i}" for i in range(n_vars)]

        # 预热 Numba（首次编译）
        _ensure_numba_histogram2d()

        # Matplotlib 的首次 figure/artist 初始化会受到整个测试进程中
        # 已加载后端和字体缓存的影响；预热一次，避免把冷启动噪声当作
        # corner_hist 算法回归。
        import matplotlib.pyplot as plt

        warm_fig, _ = corner_hist(data, names=names, bins=50)
        plt.close(warm_fig)

        # 性能测试
        t0 = time.time()
        fig, axes = corner_hist(data, names=names, bins=50)
        elapsed = time.time() - t0

        print(f"\n{desc}: {n_points:,} 点, {n_vars} 变量 -> {elapsed:.3f}s")

        # 验证结果正确性
        assert fig is not None
        assert axes is not None
        assert axes.shape == (n_vars, n_vars)

        # 清理
        plt.close(fig)

        # 性能断言（宽松，主要用于回归检测）
        # 实际性能取决于系统，这里只确保不会严重退化
        if n_points == 1_000 and n_vars == 3:
            assert elapsed < 5.0, f"小规模测试耗时过长: {elapsed:.2f}s"
        elif n_points == 10_000 and n_vars == 5:
            assert elapsed < 10.0, f"中规模测试耗时过长: {elapsed:.2f}s"


class TestCornerHistIntegration:
    """集成测试：确保优化不破坏现有功能"""

    def test_corner_hist_with_log_scale(self):
        """对数刻度测试"""
        np.random.seed(200)
        data = [np.random.lognormal(0, 1, 5000) for _ in range(3)]
        names = ["X", "Y", "Z"]

        fig, axes = corner_hist(data, names=names, scales="log", bins=30, ranges=[(1e-2, 1e3)] * 3)

        assert fig is not None
        assert axes.shape == (3, 3)

        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_corner_hist_with_mixed_symlog_scales(self):
        data = [
            np.linspace(-1e3, 1e3, 5001),
            np.linspace(-20, 20, 5001),
            np.geomspace(1e-2, 1e2, 5001),
        ]

        fig, axes = corner_hist(
            data,
            names=["signed", "linear", "positive"],
            scales=["symlog", "linear", "log"],
            symlog_linthresh=[5.0, 1.0, 1.0],
            bins=30,
        )

        assert axes[0, 0].get_xscale() == "symlog"
        assert axes[1, 0].get_xscale() == "symlog"
        assert axes[1, 0].xaxis.get_transform().linthresh == 5.0
        assert axes[1, 0].get_yscale() == "linear"
        assert axes[2, 1].get_yscale() == "log"

        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_symlog_bins_are_uniform_in_transform_space(self):
        from matplotlib.scale import SymmetricalLogTransform

        edges = _symlog_bin_edges(-1e3, 1e3, 40, linthresh=5.0)
        transform = SymmetricalLogTransform(base=10, linthresh=5.0, linscale=1)
        transformed_edges = transform.transform(edges)

        assert np.all(np.diff(edges) > 0)
        assert edges[0] == -1e3
        assert edges[-1] == 1e3
        assert np.any(edges < 0)
        assert np.any(edges > 0)
        np.testing.assert_allclose(
            np.diff(transformed_edges),
            np.diff(transformed_edges)[0],
            rtol=1e-12,
            atol=1e-12,
        )

        values = np.array([-1e3, 0.0, 1e3])
        counts, _ = np.histogram(values, bins=edges)
        assert counts.sum() == len(values)

        counts_2d = _safe_histogram2d(values, values, edges, edges)
        assert counts_2d.sum() == len(values)

    def test_symlog_retains_negative_zero_and_positive_values(self, monkeypatch):
        from waveform_analysis.utils.visualization import statistical_plots

        captured = {}

        def capture_histogram(x, y, xbins, ybins, weights=None):
            captured["x"] = np.asarray(x)
            captured["y"] = np.asarray(y)
            return np.zeros((len(ybins) - 1, len(xbins) - 1))

        monkeypatch.setattr(statistical_plots, "_safe_histogram2d", capture_histogram)
        signed = np.array([-10.0, 0.0, 10.0])
        fig, _ = corner_hist(
            [signed, signed],
            scales=["symlog", "linear"],
            symlog_linthresh=1.0,
            bins=10,
            tight_layout=False,
        )

        np.testing.assert_array_equal(captured["x"], signed)
        np.testing.assert_array_equal(captured["y"], signed)

        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.parametrize("value", [0, -1, np.inf, np.nan, "invalid"])
    def test_invalid_symlog_linthresh(self, value):
        with pytest.raises(ValueError, match="symlog_linthresh"):
            corner_hist(
                [np.array([-1.0, 0.0, 1.0])],
                scales="symlog",
                symlog_linthresh=value,
            )

    def test_symlog_linthresh_length_must_match_data(self):
        with pytest.raises(ValueError, match="symlog_linthresh 长度"):
            corner_hist(
                [np.array([-1.0, 1.0]), np.array([-2.0, 2.0])],
                scales="symlog",
                symlog_linthresh=[1.0],
            )

    def test_layout_runs_once_for_new_figure_and_not_overlay(self, monkeypatch):
        from matplotlib.figure import Figure

        calls = 0
        original = Figure.tight_layout

        def counted_tight_layout(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Figure, "tight_layout", counted_tight_layout)
        data = [np.linspace(-5, 5, 1000), np.linspace(-2, 2, 1000)]

        fig, axes = corner_hist(data, bins=20)
        assert calls == 1

        corner_hist(data, bins=20, fig=fig, axes=axes)
        assert calls == 1

        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_tight_layout_can_be_disabled(self, monkeypatch):
        from matplotlib.figure import Figure

        def unexpected_tight_layout(self, *args, **kwargs):
            raise AssertionError("tight_layout should not be called")

        monkeypatch.setattr(Figure, "tight_layout", unexpected_tight_layout)
        fig, _ = corner_hist([np.arange(10.0)], tight_layout=False)

        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_corner_hist_with_weights(self):
        """权重测试"""
        np.random.seed(201)
        n = 5000
        data = [np.random.randn(n) for _ in range(3)]
        weights = np.random.uniform(0.5, 1.5, n)

        fig, axes = corner_hist(data, names=["A", "B", "C"], bins=30, weights=weights)

        assert fig is not None
        assert axes.shape == (3, 3)

        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_corner_hist_overlay(self):
        """叠加绘制测试"""
        np.random.seed(202)
        data1 = [np.random.randn(3000) for _ in range(3)]
        data2 = [np.random.randn(3000) + 1 for _ in range(3)]

        # 第一次绘制
        fig, axes = corner_hist(
            data1, names=["X", "Y", "Z"], bins=30, hist_color="blue", hist_alpha=0.5
        )

        # 叠加第二次
        fig, axes = corner_hist(
            data2,
            names=["X", "Y", "Z"],
            bins=30,
            hist_color="red",
            hist_alpha=0.5,
            fig=fig,
            axes=axes,
        )

        assert fig is not None
        assert axes.shape == (3, 3)

        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_corner_hist_different_bins(self):
        """不同 bins 设置测试"""
        np.random.seed(203)
        data = [np.random.randn(5000) for _ in range(3)]

        # 整数 bins
        fig1, _ = corner_hist(data, bins=50)
        assert fig1 is not None

        # 列表 bins
        fig2, _ = corner_hist(data, bins=[30, 40, 50])
        assert fig2 is not None

        # 显式边界
        bins_explicit = [np.linspace(-3, 3, 40) for _ in range(3)]
        fig3, _ = corner_hist(data, bins=bins_explicit)
        assert fig3 is not None

        import matplotlib.pyplot as plt

        plt.close(fig1)
        plt.close(fig2)
        plt.close(fig3)

    def test_hist_density_is_appended_after_legacy_positional_parameters(self):
        parameters = list(inspect.signature(corner_hist).parameters)
        assert parameters == [
            "data",
            "names",
            "bins",
            "ranges",
            "scales",
            "weights",
            "figsize_per_panel",
            "cmap",
            "hist_color",
            "hist2d_norm",
            "hist2d_vmin",
            "hist2d_vmax",
            "add_colorbar",
            "title",
            "min_count",
            "hist_alpha",
            "hist2d_alpha",
            "fig",
            "axes",
            "triangle",
            "label_mode",
            "label_fontsize",
            "label_fontweight",
            "tick_labelsize",
            "diag_title",
            "show_ticks",
            "show_ticklabels",
            "hist_density",
            "symlog_linthresh",
            "tight_layout",
        ]


class TestNumbaAvailability:
    """测试 Numba 可用性和降级机制"""

    def test_numba_initialization(self):
        """测试 Numba 初始化"""
        _ensure_numba_histogram2d()

        # 检查全局变量状态（需要重新导入以获取更新后的值）
        from waveform_analysis.utils.visualization import statistical_plots

        assert statistical_plots._NUMBA_AVAILABLE is not None  # 应该已初始化
        print(f"\nNumba 可用: {statistical_plots._NUMBA_AVAILABLE}")

        if statistical_plots._NUMBA_AVAILABLE:
            assert statistical_plots._numba_histogram2d is not None
        else:
            print("Numba 不可用，将使用 NumPy fallback")

    def test_safe_histogram2d_fallback(self):
        """测试降级机制始终能返回正确结果"""
        np.random.seed(300)
        x = np.random.randn(1000)
        y = np.random.randn(1000)
        xbins = np.linspace(-3, 3, 30)
        ybins = np.linspace(-3, 3, 30)

        # 调用 safe 版本（无论 Numba 是否可用都应该工作）
        H = _safe_histogram2d(x, y, xbins, ybins, weights=None)

        assert H.shape == (len(ybins) - 1, len(xbins) - 1)
        assert H.sum() <= len(x)  # 所有点都在范围内或部分在范围外
        assert not np.any(np.isnan(H))


if __name__ == "__main__":
    # 运行性能基准测试
    print("=" * 60)
    print("corner_hist 性能基准测试")
    print("=" * 60)

    test_perf = TestCornerHistPerformance()

    test_cases = [
        (1_000, 3, "小规模-3变量"),
        (10_000, 5, "中规模-5变量"),
        (50_000, 5, "大规模-5变量"),
        (10_000, 8, "中规模-8变量"),
    ]

    for n_points, n_vars, desc in test_cases:
        test_perf.test_corner_hist_performance(n_points, n_vars, desc)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
