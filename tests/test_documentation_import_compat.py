"""Compatibility contracts for the documentation subsystem relocation."""

from __future__ import annotations

import importlib
import inspect
import subprocess
import sys

LEGACY_TO_CANONICAL = {
    "waveform_analysis.utils.cli_docs": "waveform_analysis.documentation.cli",
    "waveform_analysis.utils.context_help": "waveform_analysis.documentation.context_help",
    "waveform_analysis.utils.doc_coverage": "waveform_analysis.documentation.doc_coverage",
    "waveform_analysis.utils.doc_links": "waveform_analysis.documentation.doc_links",
    "waveform_analysis.utils.plugin_doc_generator": (
        "waveform_analysis.documentation.plugin_doc_generator"
    ),
    "waveform_analysis.utils.site_doc_generator": (
        "waveform_analysis.documentation.site_doc_generator"
    ),
    "waveform_analysis.utils.site_guides": "waveform_analysis.documentation.site_guides",
}


def test_legacy_modules_are_canonical_module_aliases():
    for legacy_name, canonical_name in LEGACY_TO_CANONICAL.items():
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)
        assert legacy is canonical
        assert dir(legacy) == dir(canonical)


def test_public_generator_exports_are_identical():
    from waveform_analysis.documentation import DocumentationSiteGenerator, PluginDocGenerator
    from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator as LegacyPlugin
    from waveform_analysis.utils.site_doc_generator import (
        DocumentationSiteGenerator as LegacySite,
    )

    assert DocumentationSiteGenerator is LegacySite
    assert PluginDocGenerator is LegacyPlugin
    assert inspect.signature(DocumentationSiteGenerator) == inspect.signature(LegacySite)
    assert inspect.signature(PluginDocGenerator) == inspect.signature(LegacyPlugin)


def test_private_attribute_monkeypatch_is_shared(monkeypatch):
    legacy = importlib.import_module("waveform_analysis.utils.context_help")
    canonical = importlib.import_module("waveform_analysis.documentation.context_help")

    def marker():
        return False

    monkeypatch.setattr(legacy, "_is_jupyter", marker)
    assert canonical._is_jupyter is marker


def test_legacy_and_canonical_cli_module_entrypoints():
    for module_name in (
        "waveform_analysis.utils.cli_docs",
        "waveform_analysis.documentation.cli",
    ):
        result = subprocess.run(
            [sys.executable, "-m", module_name, "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "waveform-docs" in result.stdout
