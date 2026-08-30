"""Responsibility-oriented entry points for acquisition readers."""

from .base_csv import parse_files_generator
from .orchestrator import parse_and_stack_files
from .polars_backend import read_csv_polars, read_files_polars
from .pyarrow_backend import read_csv_pyarrow, read_files_pyarrow

__all__ = [
    "parse_and_stack_files",
    "parse_files_generator",
    "read_csv_polars",
    "read_csv_pyarrow",
    "read_files_polars",
    "read_files_pyarrow",
]
