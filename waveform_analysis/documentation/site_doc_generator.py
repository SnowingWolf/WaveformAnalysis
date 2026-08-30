"""Canonical alias for the offline documentation site generator."""

from importlib import import_module
import sys

_implementation = import_module("waveform_analysis.documentation.site_docs.generator")
sys.modules[__name__] = _implementation
