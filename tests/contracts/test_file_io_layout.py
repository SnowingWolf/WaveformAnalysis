"""Import compatibility and reading behavior across the file I/O migration."""

import importlib
import pickle
import subprocess
import sys

import numpy as np
import pytest

from waveform_analysis.acquisition.file_io import orchestration


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("acquisition.io", "acquisition.file_io.orchestration"),
        ("utils.io", "acquisition.file_io.orchestration"),
        ("acquisition.readers", "acquisition.file_io"),
        ("acquisition.readers.orchestrator", "acquisition.file_io.orchestration"),
        ("acquisition.readers.base_csv", "acquisition.file_io.csv_pandas"),
        ("acquisition.readers.polars_backend", "acquisition.file_io.csv_polars"),
        ("acquisition.readers.pyarrow_backend", "acquisition.file_io.csv_pyarrow"),
    ],
)
@pytest.mark.parametrize("legacy_first", [True, False])
def test_fresh_import_order_identity(legacy, canonical, legacy_first):
    paths = [f"waveform_analysis.{legacy}", f"waveform_analysis.{canonical}"]
    if not legacy_first:
        paths.reverse()
    subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib; a=importlib.import_module({paths[0]!r}); "
            f"b=importlib.import_module({paths[1]!r}); assert a is b",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("waveform_analysis.acquisition.io", "parse_and_stack_files"),
        ("waveform_analysis.acquisition.readers.base_csv", "parse_files_generator"),
        ("waveform_analysis.acquisition.readers.polars_backend", "read_csv_polars"),
        ("waveform_analysis.acquisition.readers.polars_backend", "read_files_polars"),
        ("waveform_analysis.acquisition.readers.pyarrow_backend", "read_csv_pyarrow"),
        ("waveform_analysis.acquisition.readers.pyarrow_backend", "read_files_pyarrow"),
    ],
)
def test_historical_function_pickle(module, name):
    function = getattr(importlib.import_module(module), name)
    historical = f"c{module}\n{name}\n.".encode()
    assert pickle.loads(historical) is function
    assert pickle.loads(pickle.dumps(function)) is function
    assert function.__module__ == module


@pytest.mark.parametrize(
    "legacy", ["acquisition.io", "utils.io", "acquisition.readers.orchestrator"]
)
@pytest.mark.parametrize("backend", ["polars", "pyarrow"])
def test_legacy_monkeypatch_controls_actual_dispatch(monkeypatch, legacy, backend):
    old = importlib.import_module(f"waveform_analysis.{legacy}")
    monkeypatch.setattr(old, "_POLARS_AVAILABLE", backend == "polars")
    monkeypatch.setattr(old, "_PYARROW_AVAILABLE", backend == "pyarrow")
    expected = np.array([[1, 2, 3]])
    calls = []

    def read(paths, **kwargs):
        calls.append((paths, kwargs))
        return expected

    monkeypatch.setattr(old, f"_read_files_{backend}", read)
    from waveform_analysis.acquisition.file_io import parse_and_stack_files

    assert parse_and_stack_files(["input.csv"], engine="auto") is expected
    assert calls[0][0] == ["input.csv"]
    assert calls[0][1]["skiprows_first"] == 2


@pytest.fixture
def csv_parts(tmp_path):
    first = tmp_path / "part_0.csv"
    second = tmp_path / "part_1.csv"
    first.write_text("metadata\ncolumns\n1;2;30;4\n1;2;31;5\n")
    second.write_text("1;2;32;6\n")
    return [str(first), str(second)], np.array([[1, 2, 30, 4], [1, 2, 31, 5], [1, 2, 32, 6]])


@pytest.mark.parametrize("engine", ["auto", "polars", "pyarrow", "pandas"])
@pytest.mark.parametrize("chunksize,n_jobs", [(None, 1), (1, 1), (None, 2), (1, 2)])
def test_csv_headers_chunks_threads_without_optional_backends(
    monkeypatch, csv_parts, engine, chunksize, n_jobs
):
    paths, expected = csv_parts
    monkeypatch.setattr(orchestration, "_POLARS_AVAILABLE", False)
    monkeypatch.setattr(orchestration, "_PYARROW_AVAILABLE", False)
    actual = orchestration.parse_and_stack_files(
        paths, engine=engine, chunksize=chunksize, n_jobs=n_jobs
    )
    np.testing.assert_array_equal(actual, expected)


def test_pandas_streaming_headers_and_chunks(csv_parts):
    from waveform_analysis.acquisition.file_io.csv_pandas import parse_files_generator

    paths, expected = csv_parts
    chunks = list(parse_files_generator(paths, chunksize=1))
    assert len(chunks) == 3
    np.testing.assert_array_equal(np.vstack(chunks), expected)
    assert list(parse_files_generator([])) == []
    assert orchestration.parse_and_stack_files([]).shape == (0,)


def test_format_reader_dispatch_keeps_original_arguments():
    paths = ["device.bin"]
    expected = np.array([[7]])

    class Reader:
        def read_files(self, file_paths, show_progress):
            assert file_paths is paths
            assert show_progress is True
            return expected

    assert (
        orchestration.parse_and_stack_files(paths, format_reader=Reader(), show_progress=True)
        is expected
    )


def test_fresh_import_and_read_without_optional_backend_modules(csv_parts):
    paths, expected = csv_parts
    source = f"""
import sys
sys.modules['polars'] = None
sys.modules['pyarrow'] = None
sys.modules['pyarrow.csv'] = None
from waveform_analysis.acquisition import file_io
assert 'waveform_analysis.acquisition.file_io.orchestration' not in sys.modules
from waveform_analysis.acquisition.file_io import orchestration
assert not orchestration._POLARS_AVAILABLE
assert not orchestration._PYARROW_AVAILABLE
assert orchestration.pl is None
assert orchestration.pa is None
assert orchestration.pa_csv is None
actual = file_io.parse_and_stack_files({paths!r}, engine='auto')
assert actual.tolist() == {expected.tolist()!r}
"""
    subprocess.run([sys.executable, "-c", source], check=True, capture_output=True, text=True)
