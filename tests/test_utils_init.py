import subprocess
import sys


def test_utils_import_does_not_eagerly_import_preview():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import waveform_analysis.utils as utils; "
                "assert 'plot_records_waveforms' in dir(utils); "
                "print('waveform_analysis.utils.preview' in sys.modules)"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_utils_lazy_export_still_resolves_plot_records_waveforms():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from waveform_analysis.utils import plot_records_waveforms; "
                "print(callable(plot_records_waveforms))"
            ),
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
