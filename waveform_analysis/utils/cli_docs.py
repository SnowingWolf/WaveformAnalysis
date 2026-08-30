"""Compatibility alias for :mod:`waveform_analysis.documentation.cli`."""

from importlib import import_module
import sys

if __name__ == "__main__":
    from waveform_analysis.documentation.cli import main

    sys.exit(main())

_implementation = import_module("waveform_analysis.documentation.cli")
sys.modules[__name__] = _implementation
