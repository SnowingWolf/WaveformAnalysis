"""Pandas-backed streaming CSV reader."""

from collections.abc import Iterator
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def parse_files_generator(
    file_paths: list[str],
    skiprows: int = 2,
    delimiter: str = ";",
    chunksize: int = 1000,
    show_progress: bool = False,
    samples_start: int = 7,
) -> Iterator[np.ndarray]:
    del samples_start
    if not file_paths:
        return
    paths = file_paths
    if show_progress:
        try:
            from tqdm import tqdm

            paths = tqdm(file_paths, desc="Streaming files", leave=False)
        except ImportError:
            pass
    for file_index, file_path in enumerate(paths):
        path = Path(file_path)
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            chunks = pd.read_csv(
                file_path,
                delimiter=delimiter,
                skiprows=skiprows if file_index == 0 else 0,
                header=None,
                engine="c",
                chunksize=chunksize,
                on_bad_lines="warn",
            )
            for chunk in chunks:
                chunk.dropna(how="all", inplace=True)
                if chunk.empty:
                    continue
                array = chunk.to_numpy()
                if array.shape[1] > 2 and np.issubdtype(array[:, 2].dtype, np.floating):
                    array = array[~np.isnan(array[:, 2])]
                if array.size:
                    yield array
        except Exception as error:
            logger.debug("Streaming failed for %s: %s", file_path, error)


__all__ = ["parse_files_generator"]
