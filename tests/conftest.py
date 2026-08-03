"""Shared pytest fixtures and configuration for all tests."""

import numpy as np
import pytest

from tests.utils import DependentPlugin, MockPlugin, make_csv
from waveform_analysis.core.context import Context

# =============================================================================
# CSV File Creation Fixtures
# =============================================================================


@pytest.fixture
def make_csv_fn():
    """Fixture that returns the make_csv helper function."""
    return make_csv


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
def sample_dtype():
    """Common sample dtype for storage tests."""
    return np.dtype([("time", "<i8"), ("channel", "<u1"), ("value", "<f8")])
