"""Polars-backed acquisition reader implementation."""

import logging
from pathlib import Path
import time

import numpy as np

logger = logging.getLogger(__name__)
try:
    import polars as pl
except ImportError:  # pragma: no cover - optional dependency
    pl = None


def read_csv_polars(
    file_path: str,
    delimiter: str = ";",
    skiprows: int = 0,
    samples_start: int = 7,
    n_cols: int | None = None,
) -> np.ndarray:
    if pl is None:
        raise ImportError("Polars is not available")
    if n_cols is None:
        with open(file_path) as source:
            for _ in range(skiprows):
                source.readline()
            first_line = source.readline()
        if not first_line.strip():
            return np.empty((0, 0))
        n_cols = first_line.count(delimiter) + 1

    def to_int(value: object) -> int:
        text = "" if value is None else str(value).strip()
        if not text:
            return 0
        try:
            return int(text, 16) if text.startswith(("0x", "0X")) else int(text)
        except ValueError:
            try:
                return int(float(text))
            except ValueError:
                return 0

    schema = {
        f"column_{index}": pl.Int64 if index < samples_start else pl.Int16
        for index in range(n_cols)
    }
    options = {
        "separator": delimiter,
        "skip_rows": skiprows,
        "has_header": False,
        "infer_schema_length": 0,
    }
    try:
        frame = pl.read_csv(file_path, schema=schema, **options)
    except Exception:
        schema = {
            f"column_{index}": pl.Utf8 if index < samples_start else pl.Int16
            for index in range(n_cols)
        }
        frame = pl.read_csv(file_path, schema=schema, **options)
    if frame.is_empty():
        return np.empty((0, 0))
    if any(
        frame.dtypes[index] == pl.Utf8 for index in range(min(samples_start, len(frame.dtypes)))
    ):
        metadata_columns = [f"column_{index}" for index in range(min(samples_start, n_cols))]
        waveform_columns = [
            f"column_{index}" for index in range(min(samples_start, n_cols), n_cols)
        ]
        raw = frame.select(metadata_columns).to_numpy()
        metadata = np.empty(raw.shape, dtype=np.int64)
        for index in range(raw.shape[1]):
            metadata[:, index] = [to_int(value) for value in raw[:, index]]
        return (
            np.hstack([metadata, frame.select(waveform_columns).to_numpy()])
            if waveform_columns
            else metadata
        )
    return frame.to_numpy()


def _stack_arrays(arrays: list[np.ndarray]) -> np.ndarray:
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


def read_files_polars(
    file_paths: list[str],
    delimiter: str = ";",
    skiprows_first: int = 2,
    show_progress: bool = False,
    progress_desc: str | None = None,
    samples_start: int = 7,
) -> np.ndarray:
    if pl is None:
        raise ImportError("Polars is not available")
    if not file_paths:
        return np.empty((0, 0))
    paths = file_paths
    if show_progress:
        try:
            from tqdm import tqdm

            paths = tqdm(file_paths, desc=progress_desc or "Reading files (Polars)", leave=False)
        except ImportError:
            pass
    arrays = []
    for index, file_path in enumerate(paths):
        path = Path(file_path)
        if not path.exists() or path.stat().st_size == 0:
            continue
        started = time.perf_counter()
        try:
            array = read_csv_polars(
                file_path, delimiter, skiprows_first if index == 0 else 0, samples_start
            )
            if array.size and array.shape[1] > 2 and np.issubdtype(array[:, 2].dtype, np.floating):
                array = array[~np.isnan(array[:, 2])]
            if array.size:
                arrays.append(array)
        except Exception as error:
            logger.debug("Polars read failed for %s: %s", file_path, error)
        finally:
            if show_progress:
                logger.info("Polars parsed %s in %.2fs", file_path, time.perf_counter() - started)
    return _stack_arrays(arrays)


__all__ = ["read_csv_polars", "read_files_polars"]
