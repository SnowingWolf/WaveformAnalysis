"""Shared test utilities and helper functions.

This module provides:
- CSV file creation helpers
- Test data generation functions
- Mock/Dummy classes for testing
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np

from waveform_analysis.core.config import ConfigSource, ConfigValue
from waveform_analysis.core.data.records_view import RecordsView
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import RECORDS_DTYPE

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


def make_st_waveforms(
    n_events: int = 1,
    n_samples: int = 128,
    n_channels: int = 1,
    *,
    baseline: float = 0.0,
    dt: int = 1,
    timestamp_start: int = 0,
    timestamp: int | np.ndarray | None = None,
    timestamp_scale: int = 1,
    board: int | np.ndarray | None = None,
    channel: int | np.ndarray | None = None,
    record_id: bool | np.ndarray | None = None,
    seed: int | None = None,
    wave_fill: int | float | None = None,
) -> np.ndarray:
    """Create a structured st_waveforms array with standard metadata filled.

    Extra knobs (defaults keep the historical behavior):
    - ``timestamp``: override timestamps (scalar broadcast or per-event array);
      when None, timestamps are ``(arange(n_events) + timestamp_start) * timestamp_scale``.
    - ``board`` / ``channel``: override board/channel (scalar or per-event array).
    - ``record_id``: ``True`` fills ``arange(n_events)``, or pass a per-event array.
    - ``seed``: fill ``wave`` with deterministic random int16 values in [-200, 200).
    - ``wave_fill``: fill ``wave`` with a constant value.
    """
    dtype = create_record_dtype(n_samples)
    st_waveforms = np.zeros(n_events, dtype=dtype)
    if channel is None:
        st_waveforms["channel"] = np.arange(n_events, dtype=np.int16) % np.int16(max(n_channels, 1))
    else:
        st_waveforms["channel"] = channel
    if timestamp is None:
        st_waveforms["timestamp"] = (
            np.arange(n_events, dtype=np.int64) + np.int64(timestamp_start)
        ) * np.int64(timestamp_scale)
    else:
        st_waveforms["timestamp"] = timestamp
    if board is not None:
        st_waveforms["board"] = board
    if record_id is True:
        st_waveforms["record_id"] = np.arange(n_events, dtype=np.int64)
    elif record_id is not None:
        st_waveforms["record_id"] = record_id
    st_waveforms["baseline"] = baseline
    st_waveforms["event_length"] = n_samples
    st_waveforms["dt"] = dt
    if seed is not None:
        rng = np.random.default_rng(seed)
        st_waveforms["wave"] = rng.integers(-200, 200, size=(n_events, n_samples), dtype=np.int16)
    if wave_fill is not None:
        st_waveforms["wave"] = wave_fill
    return st_waveforms


def make_records(
    n_records: int = 1,
    *,
    event_length: int = 8,
    baseline: float = 100.0,
    dt: int = 1,
    timestamp_start: int = 0,
    board: int = 0,
    channel_start: int = 0,
    record_id: np.ndarray | list | None = None,
    timestamp: np.ndarray | list | None = None,
    channel: np.ndarray | list | None = None,
    polarity: str | None = None,
) -> np.ndarray:
    """Create a records array with contiguous wave offsets.

    Extra knobs (defaults keep the historical behavior):
    - ``record_id`` / ``timestamp`` / ``channel``: per-record value overrides.
    - ``polarity``: set the polarity field (e.g. "negative").
    """
    records = np.zeros(n_records, dtype=RECORDS_DTYPE)
    if record_id is None:
        records["record_id"] = np.arange(n_records, dtype=np.int64)
    else:
        records["record_id"] = record_id
    if timestamp is None:
        records["timestamp"] = np.arange(n_records, dtype=np.int64) + np.int64(timestamp_start)
    else:
        records["timestamp"] = timestamp
    records["board"] = np.int16(board)
    if channel is None:
        records["channel"] = np.arange(channel_start, channel_start + n_records, dtype=np.int16)
    else:
        records["channel"] = channel
    records["baseline"] = baseline
    records["wave_offset"] = np.arange(0, n_records * event_length, event_length, dtype=np.int64)
    records["event_length"] = np.int32(event_length)
    records["dt"] = np.int32(dt)
    if polarity is not None:
        records["polarity"] = polarity
    return records


def make_records_view(
    n_records: int = 1,
    *,
    baseline: float = 100.0,
    dt: int = 1,
    event_length: int = 8,
    board: int | np.ndarray = 0,
    channel: int | np.ndarray | list | None = None,
    timestamp: int | np.ndarray | list | None = None,
    record_id: np.ndarray | list | None = None,
    polarity: str | None = None,
    wave_pool: np.ndarray | None = None,
) -> RecordsView:
    """Create a RecordsView with contiguous wave offsets.

    Defaults build a single-record view (wave_pool zeros); pass arrays to
    build multi-record views with custom metadata.
    """
    records = np.zeros(n_records, dtype=RECORDS_DTYPE)
    records["baseline"] = baseline
    records["dt"] = np.int32(dt)
    records["event_length"] = np.int32(event_length)
    records["board"] = board
    if channel is None:
        records["channel"] = np.arange(n_records, dtype=np.int16)
    else:
        records["channel"] = channel
    if timestamp is None:
        records["timestamp"] = np.arange(n_records, dtype=np.int64)
    else:
        records["timestamp"] = timestamp
    if record_id is None:
        records["record_id"] = np.arange(n_records, dtype=np.int64)
    else:
        records["record_id"] = record_id
    if polarity is not None:
        records["polarity"] = polarity
    records["wave_offset"] = np.arange(0, n_records * event_length, event_length, dtype=np.int64)
    if wave_pool is None:
        wave_pool = np.zeros(n_records * event_length, dtype=np.uint16)
    return RecordsView(records, wave_pool)


def make_hit(
    record_id: int,
    *,
    board: int = 0,
    channel: int = 0,
    edge_start: int | float = 2,
    edge_end: int | float = 5,
    dt: int = 2,
    timestamp: int = 0,
    position: int | float | None = None,
):
    """Create a single THRESHOLD_HIT_DTYPE record.

    When ``position`` is None it is computed as ``(edge_start + edge_end - 1) // 2``
    and ``timestamp`` is shifted by ``position * dt * 1000`` (the merged-features /
    peaklets convention). When ``position`` is given explicitly, ``timestamp`` is
    used verbatim (the grouped-plugin convention).
    """
    arr = np.zeros(1, dtype=THRESHOLD_HIT_DTYPE)
    if position is None:
        position = (edge_start + edge_end - 1) // 2
        timestamp = timestamp + position * dt * 1000
    arr[0]["position"] = position
    arr[0]["edge_start"] = edge_start
    arr[0]["edge_end"] = edge_end
    arr[0]["width"] = edge_end - edge_start
    arr[0]["dt"] = dt
    arr[0]["timestamp"] = timestamp
    arr[0]["board"] = board
    arr[0]["channel"] = channel
    arr[0]["record_id"] = record_id
    return arr[0]


def register_test_adapter(name: str, sampling_rate_hz: float = 1e9) -> None:
    """Register a simple generic DAQ adapter for tests."""
    from waveform_analysis.utils.formats import (
        FLAT_LAYOUT,
        ColumnMapping,
        DAQAdapter,
        FormatSpec,
        GenericCSVReader,
        TimestampUnit,
        register_adapter,
    )

    spec = FormatSpec(
        name=f"{name}_spec",
        columns=ColumnMapping(),
        timestamp_unit=TimestampUnit.NANOSECONDS,
        sampling_rate_hz=sampling_rate_hz,
    )
    adapter = DAQAdapter(
        name=name,
        format_reader=GenericCSVReader(spec),
        directory_layout=FLAT_LAYOUT,
    )
    register_adapter(adapter)


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

    def __init__(self, config: dict[str, Any] | None = None, data: dict[str, Any] | None = None):
        self.config = config or {}
        self._data = data or {}
        self._results: dict[tuple, Any] = {}

    def get_config_value(self, plugin, name: str) -> ConfigValue:
        """Resolve configuration value for a plugin option.

        Resolution order:
        1. Nested dict: config[plugin.provides][name]
        2. Namespaced key: config["plugin.provides.name"]
        3. Global key: config[name]
        4. Plugin default: plugin.options[name].default
        """
        provides = plugin.provides
        canonical_key = f"{provides}.{name}"

        # Check nested dict style: {"plugin_name": {"option": value}}
        if provides in self.config and isinstance(self.config[provides], dict):
            if name in self.config[provides]:
                return ConfigValue(
                    self.config[provides][name],
                    ConfigSource.EXPLICIT,
                    canonical_key,
                    canonical_key,
                )

        # Check namespaced key style: {"plugin_name.option": value}
        namespaced_key = f"{provides}.{name}"
        if namespaced_key in self.config:
            return ConfigValue(
                self.config[namespaced_key],
                ConfigSource.EXPLICIT,
                namespaced_key,
                canonical_key,
            )

        # Check global key
        if name in self.config:
            return ConfigValue(
                self.config[name],
                ConfigSource.EXPLICIT,
                name,
                canonical_key,
            )

        # Fall back to plugin default
        if hasattr(plugin, "options") and name in plugin.options:
            return ConfigValue(
                plugin.options[name].default,
                ConfigSource.PLUGIN_DEFAULT,
                name,
                canonical_key,
            )

        return ConfigValue(None, ConfigSource.GLOBAL_DEFAULT, name, canonical_key)

    def get_config(self, plugin, name: str):
        return self.get_config_value(plugin, name).value

    def get_data(self, run_id: str, name: str, *, output: str = "native", **_kwargs):
        """Get pre-seeded data by name."""
        if output not in {"native", "chunk_stream", "array"}:
            raise ValueError(
                "get_data output must be one of 'native', 'chunk_stream', or 'array'; "
                f"got {output!r}."
            )
        # Check results cache first
        if (run_id, name) in self._results:
            data = self._results[(run_id, name)]
        # Then check pre-seeded data
        else:
            data = self._data.get(name)

        if output in {"native", "chunk_stream"}:
            return data
        array = self._materialize_get_data_array(name, data)
        if array is not data:
            self._set_data(run_id, name, array)
        return array

    def _materialize_get_data_array(self, name: str, data):
        """Materialize generator/chunk outputs like Context.get_data(output='array')."""
        if isinstance(data, np.ndarray):
            return data

        if not isinstance(data, Iterator) and not hasattr(data, "__next__"):
            raise TypeError(
                f"Cannot convert get_data result for '{name}' to array: "
                f"unsupported result type {type(data).__name__}."
            )

        arrays = []
        for item in data:
            chunk_data = item if isinstance(item, np.ndarray) else getattr(item, "data", item)
            if not isinstance(chunk_data, np.ndarray):
                raise TypeError(
                    f"Cannot convert get_data stream for '{name}' to array: "
                    f"stream item {type(item).__name__} does not provide ndarray data."
                )
            if len(chunk_data) > 0:
                arrays.append(chunk_data)

        if arrays:
            return np.concatenate(arrays)

        plugin = getattr(self, "_plugins", {}).get(name)
        output_dtype = getattr(plugin, "output_dtype", None) if plugin is not None else None
        if output_dtype is not None:
            return np.zeros(0, dtype=output_dtype)
        return np.array([])

    def _set_data(self, run_id: str, name: str, data):
        """Store data in results cache."""
        self._results[(run_id, name)] = data

    def get_lineage(self, name: str) -> dict:
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
        config: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        plugins: dict[str, Plugin] | None = None,
    ):
        super().__init__(config, data)
        self._plugins = plugins or {}

    def get_plugin(self, name: str) -> Plugin:
        """Get a registered plugin by name."""
        return self._plugins[name]

    def register_plugin(self, plugin: Plugin):
        """Register a plugin instance."""
        self._plugins[plugin.provides] = plugin
