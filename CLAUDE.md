# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WaveformAnalysis is a Python package for processing and analyzing DAQ (Data Acquisition) system waveform data. It features a **plugin-based architecture** inspired by strax, with support for both static and streaming data processing, automatic caching with lineage tracking, and memory-optimized workflows.

**Key Characteristics:**
- Plugin-based processing with automatic dependency resolution (DAG)
- Context-managed stateless execution (explicit `run_id` required)
- Zero-copy caching via `numpy.memmap` with atomic writes
- Streaming support for memory-efficient processing of large datasets
- Global executor management for thread/process pool reuse

## Development Commands

### Installation
```bash
# Quick install (recommended)
./install.sh

# Manual install (development mode)
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

### Testing
```bash
# Run tests (auto-activates conda env pyroot-kernel)
./scripts/run_tests.sh

# Or via Makefile
make test

# Run tests with specific pytest args
./scripts/run_tests.sh -v -k test_name

# Custom conda environment
CONDA_ENV=my-env ./scripts/run_tests.sh
```

### Benchmarking
```bash
# Run I/O benchmark
make bench

# Custom benchmark parameters
python scripts/benchmark_io.py --n-files 100 --n-channels 2 --n-samples 500 --reps 3
```

### Code Quality
```bash
# Format code (Black)
black waveform_analysis/ --line-length 100

# Type checking
mypy waveform_analysis/

# Run tests with coverage
pytest -v --cov=waveform_analysis --cov-report=html
```

### CLI Usage
```bash
# Process a run
waveform-process --run-name 50V_OV_circulation_20thr --verbose

# Scan DAQ directory
waveform-process --scan-daq --daq-root DAQ

# Show DAQ overview
waveform-process --show-daq --daq-root DAQ
```

## Architecture Overview

### Core Components

1. **Context Layer** (`core/context.py`)
   - Central coordinator managing plugins, configuration, and caching
   - **Stateless**: All operations require explicit `run_id` parameter
   - Data stored in `_results[(run_id, data_name)]`
   - Automatic dependency resolution with cycle detection
   - Lineage-based caching with SHA1 hashing of plugin code, version, config, dtype

2. **Plugin System** (`core/plugins.py`, `core/standard_plugins.py`)
   - Each plugin declares: `provides`, `depends_on`, `options`, `version`, `dtype`
   - `compute()` returns ndarray or generator
   - `is_side_effect=True` isolates outputs to `_side_effects/{run_id}/{plugin_name}`
   - Standard plugins: RawFiles → Waveforms → StWaveforms → EventLength → Features → DataFrame → GroupedEvents → PairedEvents

3. **Storage Layer** (`core/storage.py`)
   - `MemmapStorage`: Zero-copy array persistence with atomic writes (`.tmp` → rename)
   - Validates `dtype.descr` and `STORAGE_VERSION`
   - File locking for concurrent access protection
   - Watch signature (`WATCH_SIG_KEY`) tracks input file mtime/size for cache invalidation

4. **Streaming Framework** (`core/streaming.py`, `core/streaming_plugins.py`)
   - `StreamingPlugin`: Returns chunk iterators instead of static data
   - `StreamingContext`: Manages chunk flows with automatic parallelization
   - Time-aligned chunk processing with boundary validation
   - Mixed static/streaming plugin support

5. **Executor Management** (`core/executor_manager.py`, `core/executor_config.py`)
   - Global singleton `ExecutorManager` for thread/process pool reuse
   - Predefined configs: `io_intensive`, `cpu_intensive`, `large_data`, `small_data`
   - Context manager support: `with get_executor('io_intensive') as executor:`
   - Helper functions: `parallel_map()`, `parallel_apply()`

6. **Dataset API** (`core/dataset.py`)
   - High-level chainable interface wrapping Context
   - Memory optimization: `load_waveforms=False` skips waveform extraction (saves 70-80% memory)
   - Feature registration system
   - Timestamp indexing for fast `get_waveform_at()` lookups

7. **Chunk Utilities** (`core/chunk_utils.py`)
   - `Chunk(data, start, end, run_id, ...)`: Encapsulates data with time boundaries
   - Time range operations: `select_time_range()`, `clip_to_time_range()`
   - Validation: `check_monotonic()`, `check_no_overlap()`, `check_chunk_boundaries()`
   - Splitting/merging: `split_by_time()`, `merge_chunks()`, `rechunk()`

8. **Time Range Query** (`core/time_range_query.py`) [NEW - Phase 2.2]
   - `TimeIndex`: Efficient time indexing with O(log n) binary search queries
   - `TimeRangeQueryEngine`: Manages multiple data type indices
   - Context integration: `get_data_time_range()`, `build_time_index()`, `clear_time_index()`
   - Query result caching for repeated queries
   - Example: `ctx.get_data_time_range('run_001', 'st_waveforms', start_time=1000, end_time=2000)`

9. **Strax Plugin Adapter** (`core/strax_adapter.py`) [NEW - Phase 2.3]
   - `StraxPluginAdapter`: Wraps strax plugins for seamless integration
   - `StraxContextAdapter`: Provides strax-style API (`get_array`, `get_df`, `search_field`)
   - Automatic metadata extraction and parameter mapping
   - Configuration option compatibility
   - Example: `adapter = wrap_strax_plugin(MyStraxPlugin); ctx.register_plugin(adapter)`

10. **Batch Processing & Export** (`core/batch_export.py`) [NEW - Phase 3.1 & 3.2]
    - `BatchProcessor`: Parallel/serial processing of multiple runs
    - `DataExporter`: Unified export interface (Parquet, HDF5, CSV, JSON, NumPy)
    - Progress tracking and flexible error handling
    - Example: `processor.process_runs(run_ids, 'peaks', max_workers=4)`
    - Example: `exporter.export(data, 'output.parquet')`

11. **Hot Reload** (`core/hot_reload.py`) [NEW - Phase 3.3]
    - `PluginHotReloader`: File change monitoring and automatic module reloading
    - Cache consistency maintenance after reload
    - Auto-reload daemon thread support
    - Example: `reloader = enable_hot_reload(ctx, ['my_plugin'], auto_reload=True)`

### Data Flow (Standard Pipeline)

```
CSV Files → RawFilesPlugin → WaveformsPlugin → StWaveformsPlugin → EventLengthPlugin
                                                                           ↓
                                                                    BasicFeaturesPlugin
                                                                     ↙           ↘
                                                               PeaksPlugin   ChargesPlugin
                                                                     ↘           ↙
                                                                   DataFramePlugin
                                                                           ↓
                                                                 GroupedEventsPlugin
                                                                   (Numba + MP)
                                                                           ↓
                                                                 PairedEventsPlugin
```

## Important Conventions

### Architecture & Responsibility Separation
- **Context**: Only manages plugin DAG, config, lineage, and caching
- **Dataset**: Provides chainable interface and result access (delegates to Context)
- **Never** maintain parallel state in Dataset; map attributes (like `self.char` → Context) to ensure single source of truth
- **Plugin Responsibility**: Each plugin does ONE thing; add new features as new plugins, not by expanding existing ones

### Run Identification
- **Always use `run_name`** instead of `char` (legacy term being phased out)
- Pass `run_id` explicitly to all `Context.get_data()` calls
- Missing `run_id` causes data overwrites and lineage conflicts

### Module Exports (`core/utils.py`)
All new modules **must** use the `exporter()` pattern:

```python
from waveform_analysis.core.utils import exporter
export, __all__ = exporter()

@export
class MyClass: ...

@export(name="AlternativeName")
def my_func(): ...

MY_CONST = export(42, name="MY_CONST")
```

### Naming Conventions
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Terminology: Use consistent business terms (waveforms/events/hits/chunks) across code and docs
- Event size: Use `event_length`, not `pair_len` or `pair_length`

### Cache Management
- Step-level cache: `set_step_cache(step, enabled=True, attrs=[...], persist_path=..., watch_attrs=[...])`
- Persistent cache writes `WATCH_SIG_KEY="__watch_sig__"` (mtime/size SHA1) for validation
- Cache automatically invalidates on plugin version/config/dtype changes
- Generator outputs consumed once; re-access triggers recomputation

### Time & Chunk Operations
- Records have `time`, `dt`, `length` fields; `endtime = time + dt * length`
- Chunk boundaries must be respected: record endtime ≤ chunk end
- Use `Chunk` objects for time-aligned data processing
- Validate with `check_sorted_by_time()` and `check_chunk_boundaries()`

### Performance Optimization
- **Numba JIT**: Available for hot loops (e.g., `group_multi_channel_hits` with `use_numba=True`)
- **Multiprocessing**: Use for large-scale CPU-bound tasks
- **Vectorization**: Prefer NumPy broadcasting over explicit loops
- **IO parallelization**: Use `ExecutorManager` with `io_intensive` config
- **CPU parallelization**: Use `ExecutorManager` with `cpu_intensive` config

## Common Patterns

### Basic Dataset Usage
```python
from waveform_analysis import WaveformDataset

ds = WaveformDataset(run_name="50V_OV_circulation_20thr", n_channels=2)
(ds
    .load_raw_data()
    .extract_waveforms()
    .structure_waveforms()
    .build_waveform_features()
    .build_dataframe()
    .group_events(time_window_ns=100)
    .pair_events())

df = ds.get_paired_events()
```

### Memory-Optimized Workflow
```python
# Skip waveform extraction (saves 70-80% memory)
ds = WaveformDataset(run_name="...", load_waveforms=False)
ds.load_raw_data().extract_waveforms().structure_waveforms()  # All skipped
ds.build_waveform_features()  # Still computes features
ds.get_waveform_at(0)  # Returns None with warning
```

### Plugin-Based Context Usage
```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.standard_plugins import *

ctx = Context(storage_dir="./strax_data")
ctx.register_plugin(RawFilesPlugin())
ctx.register_plugin(WaveformsPlugin())
ctx.set_config({"data_root": "DAQ", "n_channels": 2})

hits = ctx.get_data("run_001", "hits")  # Auto-resolves dependencies
```

### Streaming Processing
```python
from waveform_analysis.core.streaming import get_streaming_context

stream_ctx = get_streaming_context(ctx, run_id="run_001", chunk_size=50000)
for chunk in stream_ctx.get_stream("st_waveforms_stream"):
    process_chunk(chunk)
```

### Adding Custom Features
```python
def my_feature_fn(self, st_waveforms, event_length, **params):
    # Returns list of feature arrays (one per channel)
    return [np.array(...) for _ in range(self.n_channels)]

ds.register_feature("my_feature", my_feature_fn, param1=value1)
ds.compute_registered_features()  # Called during build_dataframe()
```

### Using New Features (Phase 2 & 3)

#### Time Range Queries
```python
from waveform_analysis.core.context import Context

ctx = Context()
# ... register plugins and set config ...

# Query specific time range
data = ctx.get_data_time_range(
    'run_001', 'st_waveforms',
    start_time=1000000,
    end_time=2000000
)

# Pre-build index for better performance
ctx.build_time_index('run_001', 'st_waveforms', endtime_field='computed')

# Get index statistics
stats = ctx.get_time_index_stats()
print(f"Total indices: {stats['total_indices']}")
```

#### Strax Plugin Integration
```python
from waveform_analysis.core.strax_adapter import (
    wrap_strax_plugin,
    create_strax_context
)

# Wrap existing strax plugin
adapter = wrap_strax_plugin(MyStraxPlugin)
ctx.register_plugin(adapter)

# Or use strax-style API
strax_ctx = create_strax_context('./data')
strax_ctx.register(MyStraxPlugin)
data = strax_ctx.get_array('run_001', 'peaks')
df = strax_ctx.get_df('run_001', ['peaks', 'hits'])
```

#### Batch Processing
```python
from waveform_analysis.core.batch_export import BatchProcessor

processor = BatchProcessor(ctx)

# Process multiple runs in parallel
results = processor.process_runs(
    run_ids=['run_001', 'run_002', 'run_003'],
    data_name='peaks',
    max_workers=4,
    show_progress=True,
    on_error='continue'  # 'continue', 'stop', or 'raise'
)

# Access results
for run_id, data in results['results'].items():
    print(f"{run_id}: {len(data)} events")

# Check errors
if results['errors']:
    print(f"Errors: {results['errors']}")
```

#### Data Export
```python
from waveform_analysis.core.batch_export import DataExporter, batch_export

# Export single dataset
exporter = DataExporter()
exporter.export(data, 'output.parquet')  # Auto-detect format
exporter.export(data, 'output.hdf5', key='waveforms')
exporter.export(data, 'output.csv')

# Batch export multiple runs
batch_export(
    ctx,
    run_ids=['run_001', 'run_002'],
    data_name='peaks',
    output_dir='./exports',
    format='parquet',
    max_workers=4
)
```

#### Hot Reload (Development)
```python
from waveform_analysis.core.hot_reload import enable_hot_reload

# Enable auto-reload for development
reloader = enable_hot_reload(
    ctx,
    plugin_names=['my_plugin'],
    auto_reload=True,
    interval=2.0  # Check every 2 seconds
)

# Manually reload after changes
reloader.reload_plugin('my_plugin', clear_cache=True)

# Disable when done
reloader.disable_auto_reload()
```

## Common Pitfalls

1. **Generator Exhaustion**: Generators can only be consumed once; repeat access triggers recomputation
2. **Missing run_id**: Always pass `run_id` to `Context.get_data()` to avoid data conflicts
3. **Cache Invalidation**: Bump `version` when changing plugin logic/dtype/options
4. **Data Paths**: Default data directory is `DAQ/<run_name>`; missing files cause `FileNotFoundError`
5. **Chunk Boundaries**: Record endtime must not exceed chunk boundary; validate with `check_chunk_boundaries()`
6. **Timestamp Index**: After modifying `st_waveforms`, call `_build_timestamp_index()` to rebuild index
7. **Waveform Access**: With `load_waveforms=False`, `get_waveform_at()` returns None

## Testing Notes

- Test script auto-activates conda environment `pyroot-kernel`
- If DAQ data files missing, tests will `pytest.skip()` gracefully
- Coverage report generated in `htmlcov/` directory
- Use `scripts/benchmark_io.py` to test I/O performance with different chunksizes

## File Structure Notes

- `waveform_analysis/core/`: Core processing logic (context, plugins, storage, executor management)
- `waveform_analysis/utils/`: Utilities (DAQ adapters, I/O, visualization)
- `waveform_analysis/fitting/`: Physics fitting models
- `tests/`: Unit and integration tests
- `examples/`: Usage demonstrations
- `docs/`: Architecture, guides, and implementation details
- `scripts/`: Helper scripts (testing, benchmarking)
- `DAQ/`: Data directory (not in package)
- `outputs/`: Results directory (not in package)

## Key Documentation Files

- `docs/ARCHITECTURE.md`: Complete architecture and data flow
- `docs/CACHE.md`: Lineage tracking and cache strategy
- `docs/STREAMING_GUIDE.md`: Streaming framework usage
- `docs/MEMORY_OPTIMIZATION.md`: Memory-saving techniques
- `docs/EXECUTOR_MANAGER_GUIDE.md`: Parallel execution management
- `docs/QUICKSTART.md`: Quick start examples
- `.github/copilot-instructions.md`: Detailed development guidelines (Chinese)
