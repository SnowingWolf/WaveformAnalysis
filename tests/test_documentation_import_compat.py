"""Import and CLI contracts for the canonical documentation package."""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

LEGACY_MODULES = (
    "waveform_analysis.utils.cli_docs",
    "waveform_analysis.utils.context_help",
    "waveform_analysis.utils.doc_coverage",
    "waveform_analysis.utils.doc_links",
    "waveform_analysis.utils.plugin_doc_generator",
    "waveform_analysis.utils.site_doc_generator",
    "waveform_analysis.utils.site_guides",
)


@pytest.mark.parametrize("module_name", LEGACY_MODULES)
def test_legacy_documentation_aliases_are_removed(module_name):
    with pytest.raises(ModuleNotFoundError) as raised:
        importlib.import_module(module_name)
    assert raised.value.name == module_name


def test_canonical_documentation_exports_are_available():
    from waveform_analysis.documentation import PluginDocGenerator, build_site_model
    from waveform_analysis.documentation.cli import main
    from waveform_analysis.documentation.context_help import HelpDocument
    from waveform_analysis.documentation.doc_coverage import DocCoverageChecker
    from waveform_analysis.documentation.doc_links import check_markdown_links

    assert callable(main)
    assert PluginDocGenerator.__module__ == "waveform_analysis.documentation.plugin_docs.generator"
    assert callable(build_site_model)
    assert HelpDocument.__module__ == "waveform_analysis.documentation.context_help"
    assert callable(DocCoverageChecker)
    assert callable(check_markdown_links)


def test_canonical_cli_module_entrypoint():
    result = subprocess.run(
        [sys.executable, "-m", "waveform_analysis.documentation.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "waveform-docs" in result.stdout
    assert "plugins-web" not in result.stdout
