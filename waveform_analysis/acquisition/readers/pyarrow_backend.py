"""PyArrow-backed acquisition reader entry points."""

from ..io import _read_csv_pyarrow as read_csv_pyarrow
from ..io import _read_files_pyarrow as read_files_pyarrow

__all__ = ["read_csv_pyarrow", "read_files_pyarrow"]
