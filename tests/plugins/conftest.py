"""Common test plugin classes for plugin tests (used via direct import).

Note: previously defined plugin fixtures here were dead code - tests in
tests/plugins/ instantiate these classes directly (e.g. ``SlowPlugin()``).
"""

import numpy as np

from tests.utils import SimplePlugin
from waveform_analysis.core.plugins.core.base import Plugin


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
