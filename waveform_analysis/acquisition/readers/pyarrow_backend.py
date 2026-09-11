"""PyArrow-backed acquisition reader implementation."""

import logging
from pathlib import Path
import time

import numpy as np

logger = logging.getLogger(__name__)
try:
    import pyarrow as pa
    import pyarrow.csv as pa_csv
except ImportError:  # pragma: no cover - optional dependency
    pa = pa_csv = None


def read_csv_pyarrow(
    file_path: str,
    delimiter: str = ";",
    skiprows: int = 0,
    samples_start: int = 7,
    n_cols: int | None = None,
) -> np.ndarray:
    if pa_csv is None:
        raise ImportError("PyArrow is not available")
    column_types = {f"f{index}": pa.int64() for index in range(samples_start)}
    if n_cols is not None:
        column_types.update({f"f{index}": pa.int16() for index in range(samples_start, n_cols)})
    table = pa_csv.read_csv(
        str(file_path),
        read_options=pa_csv.ReadOptions(skip_rows=skiprows, autogenerate_column_names=True),
        parse_options=pa_csv.ParseOptions(delimiter=delimiter),
        convert_options=pa_csv.ConvertOptions(
            column_types=column_types, strings_can_be_null=False, auto_dict_encode=False
        ),
    )
    return table.to_pandas().to_numpy()


def read_files_pyarrow(
    file_paths: list[str],
    delimiter: str = ";",
    skiprows_first: int = 2,
    show_progress: bool = False,
    progress_desc: str | None = None,
    samples_start: int = 7,
) -> np.ndarray:
    if pa_csv is None:
        raise ImportError("PyArrow is not available")
    if not file_paths:
        return np.empty((0, 0))
    paths = file_paths
    if show_progress:
        try:
            from tqdm import tqdm

            paths = tqdm(file_paths, desc=progress_desc or "Reading files (PyArrow)", leave=False)
        except ImportError:
            pass
    arrays = []
    for index, file_path in enumerate(paths):
        path = Path(file_path)
        if not path.exists() or path.stat().st_size == 0:
            continue
        started = time.perf_counter()
        try:
            array = read_csv_pyarrow(
                file_path, delimiter, skiprows_first if index == 0 else 0, samples_start
            )
            if array.size and array.shape[1] > 2 and np.issubdtype(array[:, 2].dtype, np.floating):
                array = array[~np.isnan(array[:, 2])]
            if array.size:
                arrays.append(array)
        except Exception as error:
            logger.debug("PyArrow read failed for %s: %s", file_path, error)
        finally:
            if show_progress:
                logger.info("PyArrow parsed %s in %.2fs", file_path, time.perf_counter() - started)
    if not arrays:
        return np.empty((0, 0))
    try:
        return np.vstack(arrays)
    except ValueError:
        max_columns = max(array.shape[1] for array in arrays)
        return np.vstack(
            [
                np.pad(array, ((0, 0), (0, max_columns - array.shape[1])), constant_values=np.nan)
                for array in arrays
            ]
        )


__all__ = ["read_csv_pyarrow", "read_files_pyarrow"]
