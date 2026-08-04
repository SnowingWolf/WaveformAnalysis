"""Utilities for exporting Matplotlib figures to PDF files."""

from collections.abc import Iterable, Iterator
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure


def save_figures_pdf(figures: Figure | Iterable[Figure], output_path: str | Path) -> Path:
    """Save one or more Matplotlib figures as a PDF.

    Args:
        figures: A single :class:`~matplotlib.figure.Figure` or an iterable of
            figures. Each figure becomes one page, in input order.
        output_path: Destination path. Its suffix is normalized to ``.pdf`` and
            missing parent directories are created.

    Returns:
        The PDF path that was written.

    Raises:
        TypeError: If ``figures`` is neither a figure nor an iterable of figures.
        ValueError: If ``figures`` is empty.

    Examples:
        >>> import matplotlib.pyplot as plt
        >>> fig, ax = plt.subplots()
        >>> _ = ax.plot([1, 2, 3])
        >>> save_figures_pdf(fig, "output/waveform")
        PosixPath('output/waveform.pdf')
    """
    figure_iterator = _as_figure_iterator(figures)
    try:
        first_figure = next(figure_iterator)
    except StopIteration as error:
        raise ValueError("figures must contain at least one Matplotlib Figure") from error

    _validate_figure(first_figure)
    pdf_path = Path(output_path).with_suffix(".pdf")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with PdfPages(pdf_path) as pdf:
        pdf.savefig(first_figure)
        for figure in figure_iterator:
            _validate_figure(figure)
            pdf.savefig(figure)

    return pdf_path


def _as_figure_iterator(figures: Figure | Iterable[Figure]) -> Iterator[Figure]:
    if isinstance(figures, Figure):
        return iter((figures,))

    try:
        return iter(figures)
    except TypeError as error:
        raise TypeError("figures must be a Matplotlib Figure or an iterable of Figures") from error


def _validate_figure(figure: object) -> None:
    if not isinstance(figure, Figure):
        raise TypeError("figures must contain only Matplotlib Figure instances")
