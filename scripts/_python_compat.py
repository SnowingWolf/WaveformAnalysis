"""Small interpreter guard shared by documentation maintenance scripts."""

import sys

MIN_PYTHON = (3, 10)


def require_supported_python(script_name: str = "documentation script") -> bool:
    """Return whether the current interpreter satisfies the project baseline."""

    if sys.version_info[:2] >= MIN_PYTHON:
        return True
    required = ".".join(str(part) for part in MIN_PYTHON)
    current = ".".join(str(part) for part in sys.version_info[:3])
    print(
        f"{script_name} requires Python >= {required} (current: {current}). "
        "Set WAVEFORM_PYTHON to a compatible interpreter.",
        file=sys.stderr,
    )
    return False


__all__ = ["MIN_PYTHON", "require_supported_python"]
