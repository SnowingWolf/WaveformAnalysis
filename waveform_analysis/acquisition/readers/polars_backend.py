"""Polars-backed acquisition reader entry points."""

from ..io import _read_csv_polars as read_csv_polars
from ..io import _read_files_polars as read_files_polars

__all__ = ["read_csv_polars", "read_files_polars"]
