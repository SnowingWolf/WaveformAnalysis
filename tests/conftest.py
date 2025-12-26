from pathlib import Path

import pytest

from tests.utils import make_csv, make_simple_csv


@pytest.fixture
def make_csv_fn():
    """Fixture that returns the make_csv helper function."""
    return make_csv


@pytest.fixture
def make_simple_csv_fn():
    """Fixture that returns the make_simple_csv helper function."""
    return make_simple_csv


@pytest.fixture
def create_daq_run(tmp_path: Path):
    """Factory fixture to create a DAQ run directory structure.

    Usage:
        daq_root, run_dir, raw_dir = create_daq_run('my_run')
        # optionally create files with make_csv_fn in tests
    """

    def _create(run_name: str = "run"):
        daq_root = tmp_path / "DAQ"
        run_dir = daq_root / run_name
        raw_dir = run_dir / "RAW"
        raw_dir.mkdir(parents=True)
        return daq_root, run_dir, raw_dir

    return _create
