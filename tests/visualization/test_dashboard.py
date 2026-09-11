"""测试位置重建可视化功能

验证集成的可视化模块是否正常工作。
"""

from pathlib import Path
import tempfile
import warnings

import numpy as np
import pandas as pd
import pytest

from waveform_analysis.core.hardware.geometry import load_fallback_layout


def test_visualization_import():
    """测试可视化模块导入"""
    print("[*] 测试可视化模块导入...")

    try:
        from waveform_analysis.visualization import render_position_dashboard

        print("[✓] 成功导入 render_position_dashboard")
        return True
    except ImportError as e:
        print(f"[✗] 导入失败: {e}")
        return False


def test_dashboard_with_mock_data():
    """使用模拟数据测试仪表板生成"""
    print("\n[*] 测试仪表板生成（模拟数据）...")

    try:
        from waveform_analysis.visualization import render_position_dashboard

        # 生成模拟数据（100 个事件）
        np.random.seed(42)
        n_events = 100

        # 在探测器内均匀分布
        r = np.sqrt(np.random.uniform(0, 50**2, n_events))  # r < 50 mm
        theta = np.random.uniform(0, 2 * np.pi, n_events)

        df = pd.DataFrame(
            {
                "x_rec": r * np.cos(theta),
                "y_rec": r * np.sin(theta),
                "z_rec": np.random.uniform(-100, -10, n_events),
                "s1_area": np.random.lognormal(4, 0.5, n_events),
                "s2_area": np.random.lognormal(6, 0.7, n_events),
                "s2_peak_id": np.arange(n_events),
                "drift_time_ns": np.random.uniform(100, 1000, n_events),
            }
        )

        # 加载 PMT 布局
        layout = load_fallback_layout()

        # 生成仪表板
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = render_position_dashboard(
                df=df,
                layout=layout,
                run_id="test_001",
                output_dir=tmpdir,
                detector_radius_mm=62.5,
            )

            # 验证文件生成
            if Path(output_file).exists():
                file_size = Path(output_file).stat().st_size
                print(f"[✓] 仪表板已生成: {output_file}")
                print(f"    文件大小: {file_size / 1024:.1f} KB")
                return True
            else:
                print(f"[✗] 文件未生成: {output_file}")
                return False

    except Exception as e:
        print(f"[✗] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_layout_loading():
    """测试 PMT 布局加载"""
    print("\n[*] 测试 PMT 布局加载...")

    try:
        layout = load_fallback_layout()

        print(f"[✓] 布局来源: {layout.source}")
        print(f"    PMT 数量: {len(layout.entries)}")
        print(
            f"    示例 PMT: {layout.entries[0].pmt_id} at ({layout.entries[0].x_mm}, {layout.entries[0].y_mm})"
        )

        return True
    except Exception as e:
        print(f"[✗] 测试失败: {e}")
        return False


def test_html_return():
    """测试返回 HTML 字符串（用于 Jupyter）"""
    print("\n[*] 测试 HTML 字符串返回...")

    try:
        from waveform_analysis.visualization import render_position_dashboard

        # 简单数据
        df = pd.DataFrame(
            {
                "x_rec": [0, 10, -10],
                "y_rec": [0, 5, -5],
                "z_rec": [-50, -60, -70],
                "s1_area": [100, 200, 150],
                "s2_area": [1000, 2000, 1500],
                "s2_peak_id": [1, 2, 3],
            }
        )

        layout = load_fallback_layout()

        html_content = render_position_dashboard(
            df=df,
            layout=layout,
            run_id="test_002",
            return_html=True,  # 关键参数
        )

        if html_content and len(html_content) > 1000:
            print("[✓] HTML 内容已生成")
            print(f"    长度: {len(html_content)} 字符")
            print(f"    包含 Plotly: {'plotly' in html_content.lower()}")
            return True
        else:
            print(f"[✗] HTML 内容异常: {len(html_content) if html_content else 0} 字符")
            return False

    except Exception as e:
        print(f"[✗] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_dashboard_2d_canonical_html_guards_large_frontend_arrays():
    """The canonical 2D dashboard should keep robust frontend guards."""
    from waveform_analysis.visualization import render_position_dashboard_2d

    rng = np.random.default_rng(42)
    n_events = 100
    r = np.sqrt(rng.uniform(0, 50**2, n_events))
    theta = rng.uniform(0, 2 * np.pi, n_events)
    df = pd.DataFrame(
        {
            "x_rec": r * np.cos(theta),
            "y_rec": r * np.sin(theta),
            "z_rec": rng.uniform(-100, -10, n_events),
            "s1_area": rng.lognormal(4, 0.5, n_events),
            "s2_area": rng.lognormal(6, 0.7, n_events),
            "s2_peak_id": np.arange(n_events),
        }
    )

    original = df.copy(deep=True)
    html_content = render_position_dashboard_2d(
        df=df,
        layout=load_fallback_layout(),
        run_id="test_2d_hist_layout",
        return_html=True,
    )

    pd.testing.assert_frame_equal(df, original)
    assert "type: 'heatmap'" in html_content
    assert 'class="plot-grid plot-grid-two"' in html_content
    assert "function showPlotlyLoadError" in html_content
    assert "function waitForDashboardLayout" in html_content
    assert "function resizeAllPlots" in html_content
    assert "function renderPlot" in html_content
    assert "function requestUpdate" in html_content
    assert "MAX_SELECTION_POINTS = 2000" in html_content
    assert "responsive: true" in html_content
    assert "for (const value of values)" in html_content
    assert "type: 'scatter3d'" in html_content
    assert "type: 'scattergl'" not in html_content
    assert "range: [-r_tpc*1.2, r_tpc*1.2]" not in html_content
    assert "Math.min(...values.map" not in html_content
    assert "Math.max(...values.map" not in html_content
    assert "Math.max(1, ...counts.flat())" not in html_content


def test_dashboard_2d_rejects_invalid_input_and_serializes_nonfinite_values():
    from waveform_analysis.visualization import render_position_dashboard_2d

    df = pd.DataFrame(
        {
            "x_rec": [0.0, np.inf, 2.0],
            "y_rec": [0.0, 1.0, 2.0],
            "z_rec": [-10.0, -20.0, -30.0],
            "s1_area": [10.0, np.nan, 30.0],
            "s2_area": [100.0, 200.0, 300.0],
            "s2_peak_id": [1, 2, 3],
        }
    )

    html_content = render_position_dashboard_2d(
        df=df,
        layout=load_fallback_layout(),
        return_html=True,
    )
    assert '"x_rec": null' in html_content
    assert '"s1_area": null' in html_content
    assert '"x_rec": Infinity' not in html_content
    assert '"s1_area": NaN' not in html_content

    invalid = df.astype({"x_rec": object}).copy()
    invalid.loc[0, "x_rec"] = "not-a-number"
    with pytest.raises(ValueError, match="x_rec"):
        render_position_dashboard_2d(
            df=invalid,
            layout=load_fallback_layout(),
            return_html=True,
        )


def test_dashboard_2d_hist_alias_warns_and_uses_canonical_output(tmp_path):
    from waveform_analysis.visualization import render_position_dashboard_with_2d_hist

    df = pd.DataFrame(
        {
            "x_rec": [0.0, 1.0],
            "y_rec": [0.0, 1.0],
            "z_rec": [-10.0, -20.0],
            "s1_area": [10.0, 20.0],
            "s2_area": [100.0, 200.0],
            "s2_peak_id": [1, 2],
        }
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        output = render_position_dashboard_with_2d_hist(
            df=df,
            layout=load_fallback_layout(),
            run_id="deprecated",
            output_dir=str(tmp_path),
        )

    assert any(issubclass(item.category, DeprecationWarning) for item in caught)
    assert Path(output).name == "run_deprecated_position_dashboard_2d.html"
    assert Path(output).exists()


def main():
    """运行所有测试"""
    print("=" * 60)
    print("位置重建可视化功能测试")
    print("=" * 60)

    results = {
        "模块导入": test_visualization_import(),
        "PMT 布局加载": test_layout_loading(),
        "仪表板生成": test_dashboard_with_mock_data(),
        "HTML 返回": test_html_return(),
    }

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "[✓]" if passed else "[✗]"
        print(f"{status} {test_name}")

    total = len(results)
    passed = sum(results.values())
    print(f"\n总计: {passed}/{total} 测试通过")

    return all(results.values())


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
