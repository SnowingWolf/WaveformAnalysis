"""
Common utility functions shared across the waveform_analysis package.

This module contains functions that are used in multiple places across
the codebase to avoid duplication.
"""

try:
    from numba import jit as _numba_jit

    NUMBA_AVAILABLE = True
except ImportError:
    _numba_jit = None
    NUMBA_AVAILABLE = False


def jit(*args, **kwargs):
    """Numba JIT decorator with fallback when numba is not available."""
    if _numba_jit is not None:
        return _numba_jit(*args, **kwargs)

    def decorator(func):
        return func

    return decorator
