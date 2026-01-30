"""Shared test utilities and helper functions.

This module provides:
- CSV file creation helpers
- Test data generation functions
- Mock/Dummy classes for testing
"""

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin

# =============================================================================
# CSV File Creation Helpers
# =============================================================================


def make_csv(
    dirpath: Path,
    ch: int,
    idx: int,
    start_tag: int,
    end_tag: int,
    n_samples: int = 200,
    meta: bool = True,
):
    """Create a CSV file with header and three rows (start, mid, end).

    Args:
        dirpath: Path to RAW directory
        ch: Channel number used in filename
        idx: Index used in filename
        start_tag: Starting timetag value
        end_tag: Ending timetag value
        n_samples: Number of sample columns (S0..)
        meta: Whether to add a metadata line before header (so skiprows=2 in loader works)
    """
    fname = dirpath / f"RUN_CH{ch}_{idx}.CSV"
    sample_headers = ";".join(f"S{i}" for i in range(n_samples))
    header = f"HEADER;X;TIMETAG;{sample_headers}\n"

    def row(tag):
        samples = ";".join(str((tag + i) % 100) for i in range(n_samples))
        return f"v;1;{tag};{samples}\n"

    content = ""
    if meta:
        content += "META;INFO\n"
    content += header + row(start_tag) + row((start_tag + end_tag) // 2) + row(end_tag)
    fname.write_text(content, encoding="utf-8")


def make_simple_csv(dirpath: Path, ch: int, idx: int, tag: int, n_samples: int = 50):
    """Create a simpler CSV used by some tests (two data rows)."""
    fname = dirpath / f"RUN_CH{ch}_{idx}.CSV"
    header = "HEADER;X;TIMETAG;" + ";".join(f"S{i}" for i in range(n_samples)) + "\n"
    body = "".join(
        f"v;1;{tag + i};" + ";".join(str((tag + i + j) % 100) for j in range(n_samples)) + "\n"
        for i in range(2)
    )
    fname.write_text(header + body, encoding="utf-8")


def make_csv_with_header(
    dirpath: Path,
    ch: int,
    idx: int,
    start_tag: int,
    end_tag: int,
    n_samples: int = 50,
):
    """Create a CSV file with header (first file in a channel).

    Args:
        dirpath: Path to RAW directory
        ch: Channel number
        idx: File index
        start_tag: Starting timetag
        end_tag: Ending timetag
        n_samples: Number of sample columns
    """
    fname = dirpath / f"RUN_CH{ch}_{idx}.CSV"
    sample_headers = ";".join(f"S{i}" for i in range(n_samples))
    header = f"HEADER;X;TIMETAG;{sample_headers}\n"

    # Metadata line
    meta = "META;INFO\n"

    def row(tag):
        samples = ";".join(str((tag + i) % 100) for i in range(n_samples))
        return f"v;1;{tag};{samples}\n"

    content = meta + header + row(start_tag) + row((start_tag + end_tag) // 2) + row(end_tag)
    fname.write_text(content, encoding="utf-8")


def make_csv_without_header(
    dirpath: Path,
    ch: int,
    idx: int,
    start_tag: int,
    end_tag: int,
    n_samples: int = 50,
):
    """Create a CSV file without header (subsequent files in a channel).

    Args:
        dirpath: Path to RAW directory
        ch: Channel number
        idx: File index
        start_tag: Starting timetag
        end_tag: Ending timetag
        n_samples: Number of sample columns
    """
    fname = dirpath / f"RUN_CH{ch}_{idx}.CSV"

    def row(tag):
        samples = ";".join(str((tag + i) % 100) for i in range(n_samples))
        return f"v;1;{tag};{samples}\n"

    # No metadata and header, just data rows
    content = row(start_tag) + row((start_tag + end_tag) // 2) + row(end_tag)
    fname.write_text(content, encoding="utf-8")


# =============================================================================
# Test Data Generation
# =============================================================================

# Field name constants (matching chunk.py)
TIME_FIELD = "time"
DT_FIELD = "dt"
LENGTH_FIELD = "length"
ENDTIME_FIELD = "endtime"


def make_test_dtype(with_endtime: bool = False) -> np.dtype:
    """Create a test dtype for chunk/record testing.

    Args:
        with_endtime: Whether to include the endtime field

    Returns:
        NumPy dtype with time, dt, length fields (and optionally endtime)
    """
    fields = [
        (TIME_FIELD, "<i8"),
        (DT_FIELD, "<i4"),
        (LENGTH_FIELD, "<i4"),
    ]
    if with_endtime:
        fields.append((ENDTIME_FIELD, "<i8"))
    return np.dtype(fields)


def make_test_data(
    n: int = 10,
    start_time: int = 0,
    dt: int = 10,
    length: int = 100,
    gap: int = 0,
    with_endtime: bool = False,
) -> np.ndarray:
    """Create test data array for chunk/record testing.

    Args:
        n: Number of records to create
        start_time: Starting time value
        dt: Time step per sample
        length: Number of samples per record
        gap: Gap between records (can be negative for overlap)
        with_endtime: Whether to include computed endtime field

    Returns:
        Structured numpy array with test data
    """
    dtype = make_test_dtype(with_endtime)
    data = np.zeros(n, dtype=dtype)

    current_time = start_time
    for i in range(n):
        data[i][TIME_FIELD] = current_time
        data[i][DT_FIELD] = dt
        data[i][LENGTH_FIELD] = length
        if with_endtime:
            data[i][ENDTIME_FIELD] = current_time + dt * length
        current_time += dt * length + gap

    return data


# =============================================================================
# Mock Plugin Classes
# =============================================================================


class MockPlugin(Plugin):
    """A simple mock plugin for testing basic plugin functionality."""

    provides = "mock_data"
    depends_on = []
    output_dtype = np.dtype([("time", "f8"), ("value", "f8")])

    def compute(self, context, run_id, **kwargs):
        return np.array([(1.0, 10.0), (2.0, 20.0)], dtype=self.output_dtype)


class DependentPlugin(Plugin):
    """A mock plugin that depends on MockPlugin."""

    provides = "dependent_data"
    depends_on = ["mock_data"]
    output_dtype = np.dtype([("time", "f8"), ("sum", "f8")])

    def compute(self, context, run_id, **kwargs):
        mock_data = context.get_data(run_id, "mock_data")
        return np.array([(d["time"], d["value"] + 1) for d in mock_data], dtype=self.output_dtype)


class SimplePlugin(Plugin):
    """A minimal plugin for basic tests."""

    provides = "simple_data"
    depends_on = []
    output_dtype = np.dtype([("value", np.int32)])

    def compute(self, context, run_id, **kwargs):
        return np.array([(1,), (2,), (3,)], dtype=self.output_dtype)


class ConfigurablePlugin(Plugin):
    """A plugin with configurable options for testing config resolution."""

    provides = "config_data"
    depends_on = []
    options = {"multiplier": Option(default=1, type=int)}
    output_dtype = np.dtype([("val", "i4")])

    def compute(self, context, run_id, **kwargs):
        multiplier = context.get_config(self, "multiplier")
        return np.array([(multiplier,)], dtype=self.output_dtype)


# =============================================================================
# Mock Context Classes
# =============================================================================


class DummyContext:
    """A lightweight mock Context for plugin unit tests.

    This class simulates the Context interface without the full implementation,
    useful for testing plugins in isolation.

    Attributes:
        config: Configuration dictionary
        _data: Pre-seeded data dictionary
        _results: Cache for computed results
    """

    def __init__(
        self, config: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None
    ):
        self.config = config or {}
        self._data = data or {}
        self._results: Dict[tuple, Any] = {}

    def get_config(self, plugin, name: str):
        """Resolve configuration value for a plugin option.

        Resolution order:
        1. Nested dict: config[plugin.provides][name]
        2. Namespaced key: config["plugin.provides.name"]
        3. Global key: config[name]
        4. Plugin default: plugin.options[name].default
        """
        provides = plugin.provides

        # Check nested dict style: {"plugin_name": {"option": value}}
        if provides in self.config and isinstance(self.config[provides], dict):
            if name in self.config[provides]:
                return self.config[provides][name]

        # Check namespaced key style: {"plugin_name.option": value}
        namespaced_key = f"{provides}.{name}"
        if namespaced_key in self.config:
            return self.config[namespaced_key]

        # Check global key
        if name in self.config:
            return self.config[name]

        # Fall back to plugin default
        if hasattr(plugin, "options") and name in plugin.options:
            return plugin.options[name].default

        return None

    def get_data(self, run_id: str, name: str):
        """Get pre-seeded data by name."""
        # Check results cache first
        if (run_id, name) in self._results:
            return self._results[(run_id, name)]
        # Then check pre-seeded data
        return self._data.get(name)

    def _set_data(self, run_id: str, name: str, data):
        """Store data in results cache."""
        self._results[(run_id, name)] = data

    def get_lineage(self, name: str) -> Dict:
        """Return empty lineage for testing."""
        return {}

    def key_for(self, run_id: str, data_name: str) -> str:
        """Generate a cache key."""
        return f"{run_id}-{data_name}-key"


class FakeContext(DummyContext):
    """Extended mock Context with plugin registry support.

    Useful for testing plugin chains and dependencies.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        plugins: Optional[Dict[str, Plugin]] = None,
    ):
        super().__init__(config, data)
        self._plugins = plugins or {}

    def get_plugin(self, name: str) -> Plugin:
        """Get a registered plugin by name."""
        return self._plugins[name]

    def register_plugin(self, plugin: Plugin):
        """Register a plugin instance."""
        self._plugins[plugin.provides] = plugin
