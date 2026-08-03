"""
Shared fixtures for contract tests.
"""

from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin


@pytest.fixture
def temp_storage_dir():
    """Create a temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def context(temp_storage_dir):
    """Create a Context with temporary storage."""
    return Context(storage_dir=str(temp_storage_dir))


@pytest.fixture
def all_builtin_plugins() -> list[type[Plugin]]:
    """Get all builtin plugin classes from the cpu, peaks and hit modules.

    Plugins migrated out of ``builtin.cpu`` (PeaksPlugin, Peaklet*, ThresholdHitPlugin,
    HitMerge*...) are lazily re-exported by ``cpu`` via ``__getattr__`` and therefore
    do not appear in ``dir(cpu)``; enumerate the migrated modules explicitly so the
    contract tests cover the full builtin plugin set.
    """
    from waveform_analysis.core.plugins.builtin import cpu, hit, peaks

    plugins = []
    seen_classes = set()  # Track by class id to avoid duplicates
    for module in (cpu, peaks, hit):
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, Plugin)
                and obj is not Plugin
                and not name.startswith("_")
                and id(obj) not in seen_classes  # Deduplicate
            ):
                seen_classes.add(id(obj))
                plugins.append(obj)
    return plugins


@pytest.fixture
def registered_context(context, all_builtin_plugins):
    """Context with all builtin plugins registered."""
    for plugin_cls in all_builtin_plugins:
        try:
            context.register(plugin_cls())
        except Exception:
            # Some plugins may have dependencies or special requirements
            pass
    return context


@pytest.fixture
def simple_plugin_class():
    """A simple plugin class for testing."""

    class SimplePlugin(Plugin):
        provides = "simple_data"
        depends_on = ()
        version = "1.0.0"
        output_dtype = np.dtype([("value", "<f8"), ("time", "<i8")])

        def compute(self, context, run_id: str, **kwargs):  # noqa: ARG002
            return np.array([(1.0, 100), (2.0, 200)], dtype=self.output_dtype)

    return SimplePlugin
