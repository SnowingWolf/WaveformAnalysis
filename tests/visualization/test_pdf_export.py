"""Tests for PDF figure export utilities."""

import re

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

from waveform_analysis.utils import save_figures_pdf
from waveform_analysis.utils.visualization import save_figures_pdf as visualization_save_figures_pdf


def _page_count(pdf_path) -> int:
    return len(re.findall(rb"/Type /Page(?!s)\b", pdf_path.read_bytes()))


def test_save_figures_pdf_writes_single_page_and_keeps_figure_open(tmp_path):
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3])
    output_path = tmp_path / "reports" / "waveform"

    try:
        written_path = save_figures_pdf(fig, output_path)

        assert written_path == output_path.with_suffix(".pdf")
        assert written_path.read_bytes().startswith(b"%PDF")
        assert _page_count(written_path) == 1
        assert plt.fignum_exists(fig.number)
    finally:
        plt.close(fig)


def test_save_figures_pdf_writes_one_page_per_figure_in_input_order(tmp_path):
    figures = []
    for label in ("first", "second"):
        fig, ax = plt.subplots()
        ax.set_title(label)
        figures.append(fig)

    try:
        written_path = save_figures_pdf((figure for figure in figures), tmp_path / "report.pdf")

        assert written_path == tmp_path / "report.pdf"
        assert _page_count(written_path) == len(figures)
        assert all(plt.fignum_exists(figure.number) for figure in figures)
    finally:
        plt.close("all")


def test_save_figures_pdf_rejects_empty_or_invalid_input(tmp_path):
    with pytest.raises(ValueError, match="at least one"):
        save_figures_pdf([], tmp_path / "empty.pdf")

    with pytest.raises(TypeError, match="Figure or an iterable"):
        save_figures_pdf(42, tmp_path / "invalid.pdf")

    with pytest.raises(TypeError, match="only Matplotlib Figure"):
        save_figures_pdf(["not-a-figure"], tmp_path / "invalid-element.pdf")


def test_pdf_export_has_stable_utils_and_visualization_imports():
    assert save_figures_pdf is visualization_save_figures_pdf
