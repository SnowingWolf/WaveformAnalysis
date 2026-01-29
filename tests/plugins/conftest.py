"""Shared pytest fixtures for plugin tests."""

import numpy as np
import pytest

from tests.utils import DummyContext, FakeContext, SimplePlugin
from waveform_analysis.core.plugins.core.base import Option, Plugin


# =============================================================================
# Plugin Test Fixtures
# =============================================================================


@pytest.fixture
def dummy_context():
    """Returns a DummyContext instance for plugin unit tests."""
    return DummyContext()


@pytest.fixture
def dummy_context_factory():
    """Factory fixture for creating DummyContext with custom config/data."""

    def _create(config=None, data=None):
        return DummyContext(config=config, data=data)

    return _create


@pytest.fixture
def fake_context():
    """Returns a FakeContext instance with plugin registry support."""
    return FakeContext()


@pytest.fixture
def fake_context_factory():
    """Factory fixture for creating FakeContext with custom config/data/plugins."""

    def _create(config=None, data=None, plugins=None):
        return FakeContext(config=config, data=data, plugins=plugins)

    return _create


@pytest.fixture
def simple_plugin():
    """Returns a SimplePlugin instance."""
    return SimplePlugin()


# =============================================================================
# Common Test Plugin Classes
# =============================================================================


class SlowPlugin(Plugin):
    """A plugin that simulates slow computation for timeout tests."""

    provides = "slow_data"
    depends_on = []
    output_dtype = np.dtype([("value", np.int32)])

    def __init__(self, delay: float = 0.1):
        super().__init__()
        self.delay = delay

    def compute(self, context, run_id, **kwargs):
        import time

        time.sleep(self.delay)
        return np.array([(1,), (2,), (3,)], dtype=self.output_dtype)


class FailingPlugin(Plugin):
    """A plugin that always raises an error for error handling tests."""

    provides = "failing_data"
    depends_on = []
    output_dtype = np.dtype([("value", np.int32)])

    def __init__(self, error_message: str = "Intentional failure"):
        super().__init__()
        self.error_message = error_message

    def compute(self, context, run_id, **kwargs):
        raise ValueError(self.error_message)


class CountingPlugin(Plugin):
    """A plugin that counts how many times compute() is called."""

    provides = "counting_data"
    depends_on = []
    output_dtype = np.dtype([("value", np.int32)])
    call_count = 0

    def compute(self, context, run_id, **kwargs):
        CountingPlugin.call_count += 1
        return np.array([(CountingPlugin.call_count,)], dtype=self.output_dtype)

    @classmethod
    def reset_count(cls):
        cls.call_count = 0


class VersionedPlugin(Plugin):
    """A plugin with explicit version for versioning tests."""

    provides = "versioned_data"
    depends_on = []
    version = "1.0.0"
    output_dtype = np.dtype([("value", np.int32)])

    def compute(self, context, run_id, **kwargs):
        return np.array([(42,)], dtype=self.output_dtype)


# =============================================================================
# Fixtures for Common Test Plugin Classes
# =============================================================================


@pytest.fixture
def slow_plugin():
    """Returns a SlowPlugin instance."""
    return SlowPlugin()


@pytest.fixture
def slow_plugin_factory():
    """Factory fixture for creating SlowPlugin with custom delay."""

    def _create(delay: float = 0.1):
        return SlowPlugin(delay=delay)

    return _create


@pytest.fixture
def failing_plugin():
    """Returns a FailingPlugin instance."""
    return FailingPlugin()


@pytest.fixture
def counting_plugin():
    """Returns a CountingPlugin instance with reset count."""
    CountingPlugin.reset_count()
    return CountingPlugin()


@pytest.fixture
def versioned_plugin():
    """Returns a VersionedPlugin instance."""
    return VersionedPlugin()
