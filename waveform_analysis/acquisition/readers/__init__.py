"""Lazy responsibility-oriented entry points for acquisition readers."""

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
    "parse_and_stack_files": "orchestrator",
    "parse_files_generator": "base_csv",
    "read_csv_polars": "polars_backend",
    "read_files_polars": "polars_backend",
    "read_csv_pyarrow": "pyarrow_backend",
    "read_files_pyarrow": "pyarrow_backend",
}


def __getattr__(name: str):
    if name in _MODULE_BY_NAME:
        value = getattr(import_module(f".{_MODULE_BY_NAME[name]}", __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
