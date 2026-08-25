"""Canonical interactive 2D position dashboard entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dashboard_2d_hist_layout import _render_position_dashboard_2d_impl

if TYPE_CHECKING:
    import pandas as pd

    from waveform_analysis.core.hardware.geometry import PmtLayout


def render_position_dashboard_2d(
    df: pd.DataFrame,
    layout: PmtLayout,
    run_id: str = "unknown",
    output_dir: str = "output",
    detector_radius_mm: float = 62.5,
    return_html: bool = False,
) -> str | None:
    """Render the canonical interactive 2D position dashboard.

    The implementation is shared with the deprecated histogram-layout entry
    point.  This public function is the supported API for the enhanced 2D
    dashboard and writes ``run_{run_id}_position_dashboard_2d.html``.
    """
    return _render_position_dashboard_2d_impl(
        df=df,
        layout=layout,
        run_id=run_id,
        output_dir=output_dir,
        detector_radius_mm=detector_radius_mm,
        return_html=return_html,
    )
