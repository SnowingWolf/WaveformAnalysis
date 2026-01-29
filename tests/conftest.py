"""Shared pytest fixtures and configuration for all tests."""

from pathlib import Path

import numpy as np
import pytest

from tests.utils import (
    DependentPlugin,
    DummyContext,
    MockPlugin,
    make_csv,
    make_csv_with_header,
    make_csv_without_header,
    make_simple_csv,
    make_test_data,
    make_test_dtype,
)
from waveform_analysis.core.context import Context


# =============================================================================
# CSV File Creation Fixtures
# =============================================================================


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


# =============================================================================
# Context Fixtures
# =============================================================================


@pytest.fixture
def context(tmp_path):
    """Standard Context fixture with temporary storage directory."""
    storage_dir = str(tmp_path / "strax_data")
    return Context(storage_dir=storage_dir)


@pytest.fixture
def context_with_mock_plugins(tmp_path):
    """Context with MockPlugin and DependentPlugin pre-registered."""
    storage_dir = str(tmp_path / "strax_data")
    ctx = Context(storage_dir=storage_dir)
    ctx.register(MockPlugin)
    ctx.register(DependentPlugin)
    return ctx


# =============================================================================
# Mock Plugin Fixtures
# =============================================================================


@pytest.fixture
def mock_plugin():
    """Returns a MockPlugin instance."""
    return MockPlugin()


@pytest.fixture
def mock_plugin_class():
    """Returns the MockPlugin class for registration."""
    return MockPlugin


@pytest.fixture
def dummy_context():
    """Returns a DummyContext instance for plugin unit tests."""
    return DummyContext()


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_dtype():
    """Common sample dtype for storage tests."""
    return np.dtype([("time", "<i8"), ("channel", "<u1"), ("value", "<f8")])


@pytest.fixture
def make_test_dtype_fn():
    """Factory fixture for creating test dtypes."""
    return make_test_dtype


@pytest.fixture
def make_test_data_fn():
    """Factory fixture for creating test data arrays."""
    return make_test_data


@pytest.fixture
def make_csv_with_header_fn():
    """Fixture that returns the make_csv_with_header helper function."""
    return make_csv_with_header


@pytest.fixture
def make_csv_without_header_fn():
    """Fixture that returns the make_csv_without_header helper function."""
    return make_csv_without_header
