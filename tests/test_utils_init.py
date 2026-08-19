import subprocess
import sys


def test_utils_no_longer_exports_plot_records_waveforms():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import waveform_analysis.utils as utils; "
                "print('plot_records_waveforms' in dir(utils))"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_utils_removed_lazy_export_for_plot_records_waveforms():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from waveform_analysis.utils import plot_records_waveforms",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0


def test_utils_import_does_not_eagerly_import_statistical_plots_or_matplotlib():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import waveform_analysis.utils as utils; "
                "assert 'corner_hist' in dir(utils); "
                "print("
                "'waveform_analysis.utils.visualization.statistical_plots' in sys.modules, "
                "'matplotlib' in sys.modules"
                ")"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False False"


def test_utils_exposes_visualization_helpers_at_top_level():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import waveform_analysis.utils as utils; "
                "expected = {"
                "'plot_lineage_labview', "
                "'plot_lineage_plotly', "
                "'plot_waveforms', "
                "'corner_hist'"
                "}; "
                "print(expected.issubset(set(dir(utils))))"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "True"


def test_utils_lazy_export_still_resolves_corner_hist():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            ("from waveform_analysis.utils import corner_hist; " "print(callable(corner_hist))"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "True"


def test_root_daqanalyzer_import_does_not_eagerly_import_pandas_or_matplotlib():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "from waveform_analysis import DAQAnalyzer; "
                "assert DAQAnalyzer is not None; "
                "print('pandas' in sys.modules, 'matplotlib' in sys.modules)"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False False"
