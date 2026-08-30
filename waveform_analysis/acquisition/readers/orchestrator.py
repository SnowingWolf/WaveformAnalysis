"""Unified acquisition parsing orchestration entry point."""

from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from waveform_analysis.acquisition.formats.base import FormatReader


def parse_and_stack_files(
    file_paths: list[str],
    skiprows: int = 2,
    delimiter: str = ";",
    chunksize: int | None = None,
    engine: str = "auto",
    n_jobs: int = 1,
    use_process_pool: bool = False,
    show_progress: bool = False,
    progress_desc: str | None = None,
    format_type: str | None = None,
    format_reader: Optional["FormatReader"] = None,
    samples_start: int = 7,
) -> np.ndarray:
    """Parse and stack files through the canonical acquisition implementation."""
    from waveform_analysis.acquisition.io import _parse_and_stack_files_impl

    return _parse_and_stack_files_impl(
        file_paths=file_paths,
        skiprows=skiprows,
        delimiter=delimiter,
        chunksize=chunksize,
        engine=engine,
        n_jobs=n_jobs,
        use_process_pool=use_process_pool,
        show_progress=show_progress,
        progress_desc=progress_desc,
        format_type=format_type,
        format_reader=format_reader,
        samples_start=samples_start,
    )


# Keep introspection consistent with the historical implementation module.
parse_and_stack_files.__module__ = "waveform_analysis.acquisition.io"


__all__ = ["parse_and_stack_files"]
