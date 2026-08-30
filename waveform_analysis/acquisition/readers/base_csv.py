"""Base CSV streaming reader.

The implementation remains owned by :mod:`waveform_analysis.acquisition.io`
so its historical private monkeypatch surface stays shared with the legacy
module alias.
"""

from ..io import parse_files_generator

__all__ = ["parse_files_generator"]
