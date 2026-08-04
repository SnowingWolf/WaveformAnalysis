"""Baseline-window normalization and validation helpers."""


def normalize_baseline_samples(
    baseline_samples: int | tuple[int, int] | list[int] | None,
) -> int | tuple[int, int] | None:
    """Normalize JSON-friendly list inputs to the internal tuple form."""
    if isinstance(baseline_samples, list):
        return tuple(baseline_samples)
    return baseline_samples


def validate_baseline_samples(
    baseline_samples: int | tuple[int, int] | list[int] | None,
) -> None:
    """Validate a baseline sample count or half-open sample range."""
    baseline_samples = normalize_baseline_samples(baseline_samples)
    if baseline_samples is None:
        return
    if isinstance(baseline_samples, tuple):
        if len(baseline_samples) != 2:
            raise ValueError(
                "baseline_samples tuple must have 2 elements (start, end), "
                f"got {len(baseline_samples)}"
            )
        start, end = baseline_samples
        if not isinstance(start, int) or not isinstance(end, int):
            raise TypeError(
                "baseline_samples tuple elements must be int, "
                f"got ({type(start).__name__}, {type(end).__name__})"
            )
        if start < 0 or end < 0:
            raise ValueError(f"baseline_samples indices must be non-negative, got ({start}, {end})")
        if start >= end:
            raise ValueError(f"baseline_samples start must be less than end, got ({start}, {end})")
        return
    if isinstance(baseline_samples, int):
        if baseline_samples <= 0:
            raise ValueError(f"baseline_samples must be positive, got {baseline_samples}")
        return
    raise TypeError(
        "baseline_samples must be int or tuple (start, end), "
        f"got {type(baseline_samples).__name__}"
    )
