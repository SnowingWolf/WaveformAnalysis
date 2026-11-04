"""Lazy responsibility-oriented entry points for file I/O."""

from importlib import import_module

__all__ = [
    "parse_and_stack_files",
    "parse_files_generator",
    "read_csv_polars",
    "read_csv_pyarrow",
    "read_files_polars",
    "read_files_pyarrow",
]

_MODULE_BY_NAME = {
    "parse_and_stack_files": "orchestration",
    "parse_files_generator": "csv_pandas",
    "read_csv_polars": "csv_polars",
    "read_files_polars": "csv_polars",
    "read_csv_pyarrow": "csv_pyarrow",
    "read_files_pyarrow": "csv_pyarrow",
}


def __getattr__(name: str):
    if name in _MODULE_BY_NAME:
        value = getattr(import_module(f".{_MODULE_BY_NAME[name]}", __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
