"""Generic file reading and batch orchestration."""

import csv
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from waveform_analysis.acquisition.formats.base import FormatReader

logger = logging.getLogger(__name__)

# Check for Polars availability (fastest option)
_POLARS_AVAILABLE = False
try:
    import polars as pl

    _POLARS_AVAILABLE = True
except ImportError:
    pl = None

# Check for PyArrow availability
_PYARROW_AVAILABLE = False
try:
    import pyarrow as pa
    import pyarrow.csv as pa_csv

    _PYARROW_AVAILABLE = True
except ImportError:
    pa = None
    pa_csv = None


from waveform_analysis.acquisition.file_io.csv_pandas import parse_files_generator
from waveform_analysis.acquisition.file_io.csv_polars import (
    read_csv_polars as _read_csv_polars,
)
from waveform_analysis.acquisition.file_io.csv_polars import (
    read_files_polars as _read_files_polars,
)
from waveform_analysis.acquisition.file_io.csv_pyarrow import (
    read_csv_pyarrow as _read_csv_pyarrow,
)
from waveform_analysis.acquisition.file_io.csv_pyarrow import (
    read_files_pyarrow as _read_files_pyarrow,
)


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
        progress_desc: 进度条描述（可选）
        format_type: 格式类型名称（如 "vx2730_csv"），使用新的格式读取器
        format_reader: 格式读取器实例（可选），优先于 format_type
        samples_start: Column index where waveform samples start (for dtype specification)
        engine: "auto" | "polars" | "pyarrow" | "pandas"

    Returns:
        所有文件数据堆叠后的数组
    """
    # 如果提供了 format_reader 或 format_type，使用新的格式读取器
    if format_reader is not None or format_type is not None:
        if format_reader is None:
            from waveform_analysis.acquisition.formats import get_format_reader

            format_reader = get_format_reader(format_type)
        return format_reader.read_files(file_paths, show_progress=show_progress)
    if not file_paths:
        return np.array([])

    engine = (engine or "auto").lower()
    if engine not in {"auto", "polars", "pyarrow", "pandas"}:
        raise ValueError(f"Invalid engine: {engine}")
    if chunksize is not None and engine in {"polars", "pyarrow"}:
        logger.warning("engine=%s does not support chunksize; falling back to pandas", engine)
        engine = "pandas"

    # Detect engine for progress description
    engine_name = "pandas"
    if engine == "polars":
        engine_name = "polars"
    elif engine == "pyarrow":
        engine_name = "pyarrow"
    elif engine == "auto" and chunksize is None:
        if _POLARS_AVAILABLE:
            engine_name = "polars"
        elif _PYARROW_AVAILABLE:
            engine_name = "pyarrow"

    # Add engine info to progress description
    if progress_desc and engine_name != "pandas":
        progress_desc = f"{progress_desc} [engine={engine_name}]"
    elif not progress_desc:
        progress_desc = f"Parsing files [engine={engine_name}]"

    # Priority: Polars > PyArrow > Pandas (for non-chunked reading)
    # Polars is fastest (Rust implementation, 2-3x faster than PyArrow)
    # Polars 支持文件间并行（n_jobs > 1），内部自动控制线程数
    if chunksize is None and engine != "pandas":
        if engine == "polars" and not _POLARS_AVAILABLE:
            logger.warning("engine=polars requested but polars unavailable; falling back to pandas")
        elif (
            engine in {"auto", "polars"}
            and _POLARS_AVAILABLE
            and (engine == "polars" or n_jobs <= 1)
        ):
            try:
                result = _read_files_polars(
                    file_paths,
                    delimiter=delimiter,
                    skiprows_first=skiprows,
                    show_progress=show_progress,
                    progress_desc=progress_desc,
                    samples_start=samples_start,
                )
                if result.size > 0:
                    return result
            except Exception as e:
                logger.warning(
                    "Polars batch read failed, falling back to PyArrow: %s: %s",
                    type(e).__name__,
                    e,
                )
                # Update engine name for fallback
                engine_name = "pyarrow" if _PYARROW_AVAILABLE else "pandas"
                if progress_desc:
                    progress_desc = progress_desc.replace(
                        "[engine=polars]", f"[engine={engine_name}]"
                    )

        if engine == "polars":
            engine = "pandas"

    # PyArrow fallback (40-60% faster than pandas)
    if chunksize is None and engine != "pandas":
        if engine == "pyarrow" and not _PYARROW_AVAILABLE:
            logger.warning(
                "engine=pyarrow requested but pyarrow unavailable; falling back to pandas"
            )
        elif (
            engine in {"auto", "pyarrow"}
            and _PYARROW_AVAILABLE
            and (engine == "pyarrow" or n_jobs <= 1)
        ):
            try:
                result = _read_files_pyarrow(
                    file_paths,
                    delimiter=delimiter,
                    skiprows_first=skiprows,
                    show_progress=show_progress,
                    progress_desc=progress_desc,
                    samples_start=samples_start,
                )
                if result.size > 0:
                    return result
            except Exception as e:
                logger.debug(f"PyArrow batch read failed, falling back to pandas: {e}")
                # Update engine name for fallback
                if progress_desc:
                    progress_desc = progress_desc.replace("[engine=pyarrow]", "[engine=pandas]")

    if engine != "pandas":
        engine = "pandas"

    # Progress bar will be set up later if needed
    # (removed duplicate tqdm setup here)

    def _parse_single(fp: str, file_skiprows: int):
        start = time.perf_counter()
        try:
            return _parse_single_impl(fp, file_skiprows)
        finally:
            if show_progress:
                elapsed = time.perf_counter() - start
                logger.info("Parsed %s in %.2fs", fp, elapsed)

    def _parse_single_impl(fp: str, file_skiprows: int):
        p = Path(fp)
        if not p.exists() or p.stat().st_size == 0:
            logger.debug("Skipping empty or missing file %s", fp)
            return None

        # 优先使用 Polars（文件间并行时，每个文件用 Polars 读取）
        if chunksize is None and _POLARS_AVAILABLE:
            try:
                arr = _read_csv_polars(
                    fp,
                    delimiter=delimiter,
                    skiprows=file_skiprows,  # 使用传入的 file_skiprows
                    samples_start=samples_start,
                )
                if arr.size > 0:
                    # 验证时间戳列有效性
                    try:
                        timestamp_col = arr[:, 2]
                        if np.issubdtype(timestamp_col.dtype, np.floating):
                            valid_mask = ~np.isnan(timestamp_col)
                            if not np.all(valid_mask):
                                arr = arr[valid_mask]
                    except (IndexError, TypeError):
                        pass
                    return arr if arr.size > 0 else None
            except Exception as e:
                logger.warning(
                    f"Polars read failed for {fp}: {type(e).__name__}: {e}, falling back to pandas"
                )

        # 不指定 dtype，让 pandas 自动推断（更快）
        try:
            if chunksize:
                # 分块读取
                chunk_iter = pd.read_csv(
                    fp,
                    delimiter=delimiter,
                    skiprows=file_skiprows,
                    header=None,
                    engine="c",
                    chunksize=chunksize,
                    on_bad_lines="warn",
                )
                file_arrs = []
                for chunk in chunk_iter:
                    chunk.dropna(how="all", inplace=True)
                    if chunk.empty:
                        continue
                    arr = chunk.to_numpy()
                    # 验证时间戳列有效性
                    try:
                        timestamp_col = arr[:, 2]
                        if np.issubdtype(timestamp_col.dtype, np.floating):
                            valid_mask = ~np.isnan(timestamp_col)
                            if not np.all(valid_mask):
                                arr = arr[valid_mask]
                    except (IndexError, TypeError):
                        pass
                    if arr.size > 0:
                        file_arrs.append(arr)

                if not file_arrs:
                    return None
                try:
                    return np.vstack(file_arrs)
                except ValueError:
                    # 处理列数不一致
                    max_cols = max(a.shape[1] for a in file_arrs)
                    padded = []
                    for a in file_arrs:
                        if a.shape[1] < max_cols:
                            pad_width = ((0, 0), (0, max_cols - a.shape[1]))
                            a = np.pad(a, pad_width, mode="constant", constant_values=np.nan)
                        padded.append(a)
                    return np.vstack(padded)
            else:
                # 一次性读取
                df = pd.read_csv(
                    fp,
                    delimiter=delimiter,
                    skiprows=file_skiprows,
                    header=None,
                    on_bad_lines="warn",
                )
                df.dropna(how="all", inplace=True)
                if df.empty:
                    return None

                arr = df.to_numpy()
                # 验证时间戳列有效性
                try:
                    timestamp_col = arr[:, 2]
                    if np.issubdtype(timestamp_col.dtype, np.floating):
                        valid_mask = ~np.isnan(timestamp_col)
                        if not np.all(valid_mask):
                            arr = arr[valid_mask]
                except (IndexError, TypeError):
                    pass

                return arr if arr.size > 0 else None

        except Exception as e:
            logger.debug(f"pandas 读取失败 {fp}: {e}，使用回退逻辑")

        # 回退到默认读取（无显式 dtype）
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
                    df = None

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

        # 直接返回数组，不再进行 pd.to_numeric 转换
        try:
            arr = df.to_numpy()
            # 验证时间戳列有效性
            try:
                timestamp_col = arr[:, 2]
                if np.issubdtype(timestamp_col.dtype, np.floating):
                    valid_mask = ~np.isnan(timestamp_col)
                    if not np.all(valid_mask):
                        arr = arr[valid_mask]
            except (IndexError, TypeError):
                pass
            return arr if arr.size > 0 else None
        except Exception as e:
            logger.warning("Failed to convert to numpy for %s: %s", fp, e)
            return None

    arrs = []
    fps = sorted(file_paths)

    # Optional progress bar setup
    if show_progress:
        try:
            from tqdm import tqdm

            desc = progress_desc or "Parsing files"
            pbar = tqdm(total=len(fps), desc=desc, leave=True)  # leave=True 保持进度条显示
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

    # Close progress bar if it was created
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


# Preserve the historical public function pickle path.
parse_and_stack_files.__module__ = "waveform_analysis.acquisition.io"
