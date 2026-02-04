"""
数据 I/O 工具 - 高效的波形数据读取和解析

本模块提供流式和批量读取 CSV 波形文件的工具函数。

主要功能:
- parse_files_generator: 流式生成器，逐块读取大型文件
- 支持多种分隔符（CSV, TSV 等）
- 自动处理文件头（仅首个文件跳过头部）
- 可配置的 chunk size 用于内存优化
- 可选的进度条显示（需要 tqdm）
- 支持 PyArrow 引擎加速解析

性能特性:
- 内存高效：流式处理，不一次性加载整个文件
- 支持并行：可与多进程配合处理多通道数据
- 容错处理：自动跳过空文件或损坏文件

Examples:
    >>> from waveform_analysis.utils.io import parse_files_generator
    >>> files = ['path/to/CH0_0.CSV', 'path/to/CH0_1.CSV']
    >>> for chunk in parse_files_generator(files, chunksize=1000):
    ...     handle_chunk(chunk)

Note:
    推荐安装 pyarrow 以获得更快的解析速度:
    pip install pyarrow
"""

import csv
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, List, Optional

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from waveform_analysis.utils.formats.base import FormatReader

logger = logging.getLogger(__name__)

# Check for PyArrow availability
_PYARROW_AVAILABLE = False
try:
    import pyarrow.csv as pa_csv

    _PYARROW_AVAILABLE = True
except ImportError:
    pa_csv = None


def _read_csv_pyarrow(
    file_path: str,
    delimiter: str = ";",
    skiprows: int = 0,
) -> np.ndarray:
    """Read CSV file using PyArrow for faster parsing.

    Args:
        file_path: Path to CSV file
        delimiter: CSV delimiter
        skiprows: Number of rows to skip at the beginning

    Returns:
        NumPy array of the data
    """
    if not _PYARROW_AVAILABLE:
        raise ImportError("PyArrow is not available")

    read_options = pa_csv.ReadOptions(
        skip_rows=skiprows,
        autogenerate_column_names=True,
    )
    parse_options = pa_csv.ParseOptions(delimiter=delimiter)
    convert_options = pa_csv.ConvertOptions(
        strings_can_be_null=True,
        auto_dict_encode=False,
    )

    table = pa_csv.read_csv(
        str(file_path),
        read_options=read_options,
        parse_options=parse_options,
        convert_options=convert_options,
    )
    return table.to_pandas().to_numpy()


def _read_files_pyarrow(
    file_paths: List[str],
    delimiter: str = ";",
    skiprows_first: int = 2,
    show_progress: bool = False,
) -> np.ndarray:
    """Read multiple CSV files using PyArrow.

    Args:
        file_paths: List of file paths
        delimiter: CSV delimiter
        skiprows_first: Number of rows to skip in the first file
        show_progress: Whether to show progress bar

    Returns:
        Stacked NumPy array of all files
    """
    if not _PYARROW_AVAILABLE:
        raise ImportError("PyArrow is not available")

    if not file_paths:
        return np.array([]).reshape(0, 0)

    # Optional progress bar
    if show_progress:
        try:
            from tqdm import tqdm

            pbar = tqdm(file_paths, desc="Reading files (PyArrow)", leave=False)
        except ImportError:
            pbar = file_paths
    else:
        pbar = file_paths

    arrays = []
    for idx, fp in enumerate(pbar):
        p = Path(fp)
        if not p.exists() or p.stat().st_size == 0:
            continue

        skiprows = skiprows_first if idx == 0 else 0
        try:
            arr = _read_csv_pyarrow(fp, delimiter=delimiter, skiprows=skiprows)
            if arr.size > 0:
                # Vectorized numeric conversion
                try:
                    numeric_part = arr[:, 2:].astype(np.float64)
                    valid_mask = ~np.isnan(numeric_part[:, 0])
                    if np.any(valid_mask):
                        result = np.column_stack([arr[valid_mask, :2], numeric_part[valid_mask]])
                        arrays.append(result)
                except (ValueError, TypeError):
                    arrays.append(arr)
        except Exception as e:
            logger.debug(f"PyArrow read failed for {fp}: {e}")
            continue

    if not arrays:
        return np.array([]).reshape(0, 0)

    try:
        return np.vstack(arrays)
    except ValueError:
        # Handle column count mismatch
        max_cols = max(a.shape[1] for a in arrays)
        padded = []
        for a in arrays:
            if a.shape[1] < max_cols:
                pad_width = ((0, 0), (0, max_cols - a.shape[1]))
                a = np.pad(a, pad_width, mode="constant", constant_values=np.nan)
            padded.append(a)
        return np.vstack(padded)


def parse_files_generator(
    file_paths: List[str],
    skiprows: int = 2,
    delimiter: str = ";",
    chunksize: int = 1000,
    show_progress: bool = False,
) -> Iterator[np.ndarray]:
    """
    Yields chunks of parsed waveform data from a list of files.

    Note: Only the first file in the list will skip header rows (skiprows).
    Subsequent files will not skip any rows (skiprows=0) as they don't contain headers.
    """
    if not file_paths:
        return

    # Optional progress bar
    if show_progress:
        try:
            from tqdm import tqdm

            pbar = tqdm(file_paths, desc="Streaming files", leave=False)
        except ImportError:
            pbar = file_paths
    else:
        pbar = file_paths

    for file_idx, fp in enumerate(pbar):
        p = Path(fp)
        if not p.exists() or p.stat().st_size == 0:
            continue

        # Only the first file has header, subsequent files don't
        file_skiprows = skiprows if file_idx == 0 else 0

        try:
            # Use pyarrow engine if available for faster parsing
            # Note: pyarrow doesn't support chunksize, so use 'c' engine when chunking
            engine = "c"
            if not chunksize:
                try:
                    import pyarrow

                    engine = "pyarrow"
                except ImportError:
                    pass

            if chunksize:
                chunk_iter = pd.read_csv(
                    fp,
                    delimiter=delimiter,
                    skiprows=file_skiprows,
                    header=None,
                    engine=engine,
                    chunksize=chunksize,
                    on_bad_lines="warn",
                )
            else:
                chunk_iter = [
                    pd.read_csv(
                        fp,
                        delimiter=delimiter,
                        skiprows=file_skiprows,
                        header=None,
                        engine=engine,
                        on_bad_lines="warn",
                    )
                ]

            for chunk in chunk_iter:
                chunk.dropna(how="all", inplace=True)
                if chunk.empty:
                    continue

                # Numeric coercion logic - optimized to avoid repeated pd.to_numeric
                try:
                    arr = chunk.to_numpy()
                    # Vectorized numeric conversion for columns 2+
                    try:
                        numeric_part = arr[:, 2:].astype(np.float64)
                    except (ValueError, TypeError):
                        # Fallback: convert column by column
                        numeric_part = np.empty((arr.shape[0], arr.shape[1] - 2), dtype=np.float64)
                        for col_idx in range(arr.shape[1] - 2):
                            numeric_part[:, col_idx] = pd.to_numeric(
                                arr[:, col_idx + 2], errors="coerce"
                            )
                    # Filter valid rows (where TIMETAG column is not NaN)
                    valid_mask = ~np.isnan(numeric_part[:, 0])
                    if not np.any(valid_mask):
                        continue
                    result = np.column_stack([arr[valid_mask, :2], numeric_part[valid_mask]])
                except Exception:
                    result = chunk.to_numpy()

                if result.size == 0:
                    continue

                yield result

        except Exception as e:
            logger.debug(f"Streaming failed for {fp}: {e}")


def parse_and_stack_files(
    file_paths: List[str],
    skiprows: int = 2,
    delimiter: str = ";",
    chunksize: Optional[int] = None,
    n_jobs: int = 1,
    use_process_pool: bool = False,
    show_progress: bool = False,
    format_type: Optional[str] = None,
    format_reader: Optional["FormatReader"] = None,
) -> np.ndarray:
    """Parse a list of CSV files and return a single vstacked numpy array.

    Behaves like helper previously in loader and DAQRun: skips empty files,
    drops all-empty rows, attempts numeric coercion for TIMETAG and samples,
    and returns an empty array if no valid data. When `chunksize` is set,
    files are read in streaming chunks to reduce memory usage.

    Note: Only the first file in the list will skip header rows (skiprows).
    Subsequent files will not skip any rows (skiprows=0) as they don't contain headers.

    Args:
        file_paths: 文件路径列表
        skiprows: 首文件跳过的行数（默认2）
        delimiter: CSV 分隔符（默认";"）
        chunksize: 分块大小（可选）
        n_jobs: 并行任务数
        use_process_pool: 是否使用进程池
        show_progress: 是否显示进度条
        format_type: 格式类型名称（如 "vx2730_csv"），使用新的格式读取器
        format_reader: 格式读取器实例（可选），优先于 format_type

    Returns:
        所有文件数据堆叠后的数组
    """
    # 如果提供了 format_reader 或 format_type，使用新的格式读取器
    if format_reader is not None or format_type is not None:
        if format_reader is None:
            from waveform_analysis.utils.formats import get_format_reader

            format_reader = get_format_reader(format_type)
        return format_reader.read_files(file_paths, show_progress=show_progress)
    if not file_paths:
        return np.array([])

    # Try PyArrow first for non-chunked reading (40-60% faster)
    if chunksize is None and _PYARROW_AVAILABLE and n_jobs <= 1:
        try:
            result = _read_files_pyarrow(
                file_paths,
                delimiter=delimiter,
                skiprows_first=skiprows,
                show_progress=show_progress,
            )
            if result.size > 0:
                return result
        except Exception as e:
            logger.debug(f"PyArrow batch read failed, falling back to pandas: {e}")

    # Optional progress bar
    if show_progress:
        try:
            from tqdm import tqdm

            pbar = tqdm(file_paths, desc="Parsing files", leave=False)
        except ImportError:
            pbar = file_paths
    else:
        pbar = file_paths

    def _parse_single(fp: str, file_skiprows: int):
        p = Path(fp)
        if not p.exists() or p.stat().st_size == 0:
            logger.debug("Skipping empty or missing file %s", fp)
            return None

        file_arrs = []
        # attempt chunked reading per-file if chunksize provided
        try:
            # Use pyarrow engine if available for faster parsing
            # Note: pyarrow doesn't support chunksize, so use 'c' engine when chunking
            engine = "c"
            if not chunksize:
                try:
                    import pyarrow

                    engine = "pyarrow"
                except ImportError:
                    pass

            if chunksize:
                chunk_iter = pd.read_csv(
                    fp,
                    delimiter=delimiter,
                    skiprows=file_skiprows,
                    header=None,
                    engine=engine,
                    chunksize=chunksize,
                    on_bad_lines="warn",  # Strax-like: warn on bad lines instead of failing
                )
            else:
                chunk_iter = [
                    pd.read_csv(
                        fp,
                        delimiter=delimiter,
                        skiprows=file_skiprows,
                        header=None,
                        engine=engine,
                        on_bad_lines="warn",
                    )
                ]

            if chunk_iter is not None:
                for chunk in chunk_iter:
                    chunk.dropna(how="all", inplace=True)
                    if chunk.empty:
                        continue
                    try:
                        # Optimized: vectorized numeric conversion
                        arr = chunk.to_numpy()
                        try:
                            numeric_part = arr[:, 2:].astype(np.float64)
                        except (ValueError, TypeError):
                            # Fallback: convert column by column
                            numeric_part = np.empty((arr.shape[0], arr.shape[1] - 2), dtype=np.float64)
                            for col_idx in range(arr.shape[1] - 2):
                                numeric_part[:, col_idx] = pd.to_numeric(
                                    arr[:, col_idx + 2], errors="coerce"
                                )
                        # Filter valid rows (where TIMETAG column is not NaN)
                        valid_mask = ~np.isnan(numeric_part[:, 0])
                        if not np.any(valid_mask):
                            continue
                        result = np.column_stack([arr[valid_mask, :2], numeric_part[valid_mask]])
                        file_arrs.append(result)
                    except Exception as e:
                        logger.warning(
                            "Failed to coerce numeric columns for chunk in %s: %s", fp, e
                        )
                        try:
                            file_arrs.append(chunk.to_numpy())
                        except Exception as e2:
                            logger.warning(
                                "to_numpy failed for chunk in %s: %s; falling back to per-row coercion",
                                fp,
                                e2,
                            )
                            rows = [list(r) for r in chunk.values]
                            max_cols = max(len(r) for r in rows)
                            norm_rows = []
                            for r in rows:
                                if len(r) < max_cols:
                                    r = list(r) + [np.nan] * (max_cols - len(r))
                                norm_rows.append(np.asarray(r, dtype=object))
                            file_arrs.append(np.vstack([np.asarray(r) for r in norm_rows]))
                        file_arrs.append(np.vstack([np.asarray(r) for r in norm_rows]))
                if not file_arrs:
                    return None
                try:
                    return np.vstack(file_arrs)
                except Exception:
                    # pad to max cols
                    max_cols = max(a.shape[1] for a in file_arrs)
                    padded = []
                    for a in file_arrs:
                        if a.shape[1] < max_cols:
                            pad = np.full((a.shape[0], max_cols - a.shape[1]), np.nan, dtype=object)
                            padded.append(np.hstack([a.astype(object), pad]))
                        else:
                            padded.append(a.astype(object))
                    return np.vstack(padded)
            # no chunking: fall through to full-file parse
        except Exception:
            logger.debug(
                "chunked read failed for %s, falling back to full parse", fp, exc_info=True
            )

        # Primary attempt: pandas read_csv with the fast C engine
        df = None
        try:
            df = pd.read_csv(
                fp, delimiter=delimiter, skiprows=file_skiprows, header=None, engine="c"
            )
        except Exception:
            logger.debug(
                "pandas read_csv (C engine) failed for %s, trying python engine with on_bad_lines='skip'",
                fp,
            )
            try:
                # on_bad_lines='skip' will drop malformed rows rather than failing
                df = pd.read_csv(
                    fp,
                    delimiter=delimiter,
                    skiprows=file_skiprows,
                    header=None,
                    engine="python",
                    on_bad_lines="skip",
                )
            except Exception:
                logger.debug(
                    "pandas read_csv (python engine) also failed for %s; attempting line-by-line fallback",
                    fp,
                    exc_info=True,
                )

                # try to sniff delimiter from a small sample and retry
                try:
                    sample = p.open("r", encoding="utf-8", errors="replace").read(4096)
                    sniffed = csv.Sniffer().sniff(sample)
                    sniff_delim = sniffed.delimiter
                    logger.debug(
                        "Sniffed delimiter '%s' for %s; retrying pandas read_csv", sniff_delim, fp
                    )
                    try:
                        df = pd.read_csv(
                            fp,
                            delimiter=sniff_delim,
                            skiprows=file_skiprows,
                            header=None,
                            engine="c",
                        )
                    except Exception:
                        try:
                            df = pd.read_csv(
                                fp,
                                delimiter=sniff_delim,
                                skiprows=file_skiprows,
                                header=None,
                                engine="python",
                                on_bad_lines="skip",
                            )
                        except Exception:
                            df = None
                except Exception:
                    # sniffing failed; fall back to line-by-line below
                    pass

        # If pandas couldn't parse, fall back to line-by-line parsing
        if df is None:
            rows = []
            bad_lines = []
            with p.open("r", encoding="utf-8", errors="replace") as fh:
                # skip header lines if any
                for _ in range(file_skiprows):
                    try:
                        next(fh)
                    except StopIteration:
                        break
                for line_no, line in enumerate(fh, start=skiprows + 1):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(delimiter)
                    # require at least 3 columns (e.g., id, tag, first sample)
                    if len(parts) < 3:
                        bad_lines.append((line_no, line))
                        logger.debug("Skipping malformed line %d in %s: %r", line_no, fp, line)
                        continue
                    rows.append(parts)
            if not rows:
                logger.debug("No recoverable rows in fallback parse for %s", fp)
                return None
            if bad_lines:
                logger.info(
                    "File %s: skipped %d malformed lines during fallback parse", fp, len(bad_lines)
                )
            df = pd.DataFrame(rows)

        # drop rows that are entirely empty
        df.dropna(how="all", inplace=True)
        if df.empty:
            logger.debug("File has no data after parsing: %s", fp)
            return None

        # Basic structural validation: expect at least 3 columns (TIMETAG + samples)
        if df.shape[1] < 3:
            logger.debug("Parsed file has insufficient columns (%d) in %s", df.shape[1], fp)
            return None

        # Coerce numeric columns for samples and TIMETAG column (index 2)
        # Optimized: use vectorized numpy conversion instead of pandas apply
        try:
            arr = df.to_numpy()
            try:
                numeric_part = arr[:, 2:].astype(np.float64)
            except (ValueError, TypeError):
                # Fallback: convert column by column
                numeric_part = np.empty((arr.shape[0], arr.shape[1] - 2), dtype=np.float64)
                for col_idx in range(arr.shape[1] - 2):
                    numeric_part[:, col_idx] = pd.to_numeric(
                        arr[:, col_idx + 2], errors="coerce"
                    )
            # Filter valid rows (where TIMETAG column is not NaN)
            valid_mask = ~np.isnan(numeric_part[:, 0])
            if not np.any(valid_mask):
                logger.debug("No numeric data left after coercion: %s", fp)
                return None
            return np.column_stack([arr[valid_mask, :2], numeric_part[valid_mask]])
        except Exception as e:
            logger.warning("Failed to coerce numeric columns for %s: %s", fp, e)
            # Fallback: try to return raw data
            try:
                return df.to_numpy()
            except Exception:
                logger.debug("to_numpy failed for %s, attempting per-row coercion", fp, exc_info=True)
                rows = []
                max_cols = 0
                for r in df.values:
                    rows.append(list(r))
                    if len(r) > max_cols:
                        max_cols = len(r)
                norm_rows = []
                for r in rows:
                    if len(r) < max_cols:
                        r = list(r) + [np.nan] * (max_cols - len(r))
                    norm_rows.append(np.array(r, dtype=object))
                return np.vstack([np.asarray(r) for r in norm_rows])

    arrs = []
    fps = sorted(file_paths)

    # Optional progress bar setup
    if show_progress:
        try:
            from tqdm import tqdm

            pbar = tqdm(total=len(fps), desc="Parsing files", leave=False)
        except ImportError:
            pbar = None
    else:
        pbar = None

    if n_jobs and n_jobs > 1:
        from concurrent.futures import as_completed

        from waveform_analysis.core.execution.manager import get_executor

        # 使用全局执行器管理器
        executor_type = "process" if use_process_pool else "thread"
        executor_name = "file_parsing_process" if use_process_pool else "file_parsing_thread"

        with get_executor(executor_name, executor_type, max_workers=n_jobs, reuse=True) as ex:
            # Only first file skips header rows, subsequent files don't
            futures = {
                ex.submit(_parse_single, fp, skiprows if idx == 0 else 0): fp
                for idx, fp in enumerate(fps)
            }
            results_map = {}
            for future in as_completed(futures):
                fp = futures[future]
                try:
                    res = future.result()
                    results_map[fp] = res
                except Exception as e:
                    logger.error("Error parsing %s: %s", fp, e)
                    results_map[fp] = None
                if pbar:
                    pbar.update(1)

            # Maintain original sorted order
            results = [results_map[fp] for fp in fps]
    else:
        results = []
        for idx, fp in enumerate(fps):
            # Only first file skips header rows, subsequent files don't
            file_skiprows = skiprows if idx == 0 else 0
            results.append(_parse_single(fp, file_skiprows))
            if pbar:
                pbar.update(1)

    if pbar:
        pbar.close()

    for r in results:
        if r is None:
            continue
        arrs.append(r)

    if not arrs:
        return np.array([])

    try:
        return np.vstack(arrs)
    except Exception:
        logger.debug(
            "vstack failed for collected arrays, attempting safe concat with padding", exc_info=True
        )
        # Find max cols and pad
        max_cols = max(a.shape[1] for a in arrs)
        padded = []
        for a in arrs:
            if a.shape[1] < max_cols:
                pad = np.full((a.shape[0], max_cols - a.shape[1]), np.nan, dtype=object)
                padded.append(np.hstack([a.astype(object), pad]))
            else:
                padded.append(a.astype(object))
        return np.vstack(padded)
