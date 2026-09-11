"""Common test plugin classes for plugin tests (used via direct import).

Note: previously defined plugin fixtures here were dead code - tests in
tests/plugins/ instantiate these classes directly (e.g. ``SlowPlugin()``).
``SlowPlugin`` / ``FailingPlugin`` are canonicalized in
``tests.batch_processor_helpers`` and re-exported here for import compatibility.
"""

import numpy as np

from tests.batch_processor_helpers import FailingPlugin, SlowPlugin
from tests.utils import SimplePlugin
from waveform_analysis.core.plugins.core.base import Plugin


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
