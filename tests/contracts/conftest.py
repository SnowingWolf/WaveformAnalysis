"""
Shared fixtures for contract tests.
"""

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Type

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
def all_builtin_plugins() -> List[Type[Plugin]]:
    """Get all builtin plugin classes from cpu module."""
    from waveform_analysis.core.plugins.builtin import cpu

    plugins = []
    seen_classes = set()  # Track by class id to avoid duplicates
    for name in dir(cpu):
        obj = getattr(cpu, name)
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
def fake_daq_data(temp_storage_dir) -> Dict[str, Any]:
    """Create minimal fake DAQ data for golden path tests."""
    run_name = "test_run_001"
    run_dir = temp_storage_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    # Create minimal CSV files that mimic VX2730 format
    # Format: board, channel, timestamp, trigger_id, samples...
    n_samples = 100
    n_events = 10

    for board in range(1):
        for channel in range(2):
            csv_path = run_dir / f"wave{board}_{channel}.csv"
            with open(csv_path, "w") as f:
                for event_idx in range(n_events):
                    # board, channel, timestamp, trigger_id, then samples
                    row = [board, channel, event_idx * 1000, event_idx]
                    # Add waveform samples (baseline + pulse)
                    samples = [100] * n_samples  # baseline
                    samples[30:40] = [150] * 10  # pulse
                    row.extend(samples)
                    f.write(",".join(map(str, row)) + "\n")

    return {
        "data_root": str(temp_storage_dir),
        "run_name": run_name,
        "run_dir": run_dir,
        "n_channels": 2,
        "n_events": n_events,
        "n_samples": n_samples,
    }


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


@pytest.fixture
def dependent_plugin_class():
    """A plugin that depends on simple_plugin."""

    class DependentPlugin(Plugin):
        provides = "dependent_data"
        depends_on = ("simple_data",)
        version = "1.0.0"
        output_dtype = np.dtype([("result", "<f8")])

        def compute(self, context, run_id: str, **kwargs):  # noqa: ARG002
            simple_data = context.get_data(run_id, "simple_data")
            if simple_data is None:
                return np.array([(0.0,)], dtype=self.output_dtype)
            return np.array([(simple_data["value"].sum(),)], dtype=self.output_dtype)

    return DependentPlugin
