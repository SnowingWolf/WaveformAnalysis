"""Private Matplotlib helper for S1-candidate and S2 waveform plots."""

from typing import Any

import numpy as np


def _relative_time_ns(waveform: dict[str, Any], event_t0_ns: float) -> np.ndarray:
    """Return waveform sample times relative to a shared event origin."""
    return float(waveform["time_start_ns"]) - event_t0_ns + np.asarray(waveform["time_rel_ns"])


def _plot_s2_candidates(
    *,
    s2_peak_id: int,
    candidate_s1_peak_ids: list[int],
    selected_s1_peak_id: int | None,
    s1_waveforms: dict[int, dict[str, Any]],
    s2_waveform: dict[str, Any],
    peak_intervals_ns: dict[int, tuple[float, float]],
    drift_time_ns: float | None,
    yscale: str,
    show_intervals: bool,
    show_info: bool,
    ax: Any,
) -> tuple[Any, tuple[Any, Any], float]:
    """Draw S1 candidates and S2 on independent y axes."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError(
            "plot_s2_candidates() requires matplotlib. Install it with: pip install matplotlib"
        ) from exc

    if ax is None:
        fig, ax_s1 = plt.subplots(figsize=(14, 5))
    else:
        ax_s1 = ax
        fig = ax_s1.get_figure()
    ax_s2 = ax_s1.twinx()

    ax_s1.set_yscale(yscale)
    ax_s2.set_yscale(yscale)

    available_waveforms = [s2_waveform, *s1_waveforms.values()]
    event_t0_ns = min(float(waveform["time_start_ns"]) for waveform in available_waveforms)

    all_time_arrays: list[np.ndarray] = []
    for peak_id, waveform in s1_waveforms.items():
        time_ns = _relative_time_ns(waveform, event_t0_ns)
        all_time_arrays.append(time_ns)
        is_selected = peak_id == selected_s1_peak_id
        ax_s1.plot(
            time_ns,
            waveform["waveform"],
            color="tab:green" if is_selected else "tab:blue",
            lw=2.6 if is_selected else 1.0,
            alpha=0.95 if is_selected else 0.45,
            label=(
                f"Selected S1 (peak_id={peak_id})"
                if is_selected
                else f"Candidate S1 (peak_id={peak_id})"
            ),
            zorder=3 if is_selected else 2,
        )

    s2_time_ns = _relative_time_ns(s2_waveform, event_t0_ns)
    all_time_arrays.append(s2_time_ns)
    ax_s2.plot(
        s2_time_ns,
        s2_waveform["waveform"],
        color="tab:red",
        lw=1.8,
        alpha=0.95,
        label=f"S2 (peak_id={s2_peak_id})",
        zorder=3,
    )

    if show_intervals:
        for peak_id in s1_waveforms:
            interval = peak_intervals_ns.get(peak_id)
            if interval is None:
                waveform = s1_waveforms[peak_id]
                time_ns = _relative_time_ns(waveform, event_t0_ns)
                interval = (float(time_ns[0]), float(time_ns[-1]))
            else:
                interval = (interval[0] - event_t0_ns, interval[1] - event_t0_ns)
            ax_s1.axvspan(
                *interval,
                color="tab:green" if peak_id == selected_s1_peak_id else "tab:blue",
                alpha=0.12 if peak_id == selected_s1_peak_id else 0.06,
                linewidth=0,
            )

        s2_interval = peak_intervals_ns.get(s2_peak_id)
        if s2_interval is None:
            s2_interval = (float(s2_time_ns[0]), float(s2_time_ns[-1]))
        else:
            s2_interval = (
                s2_interval[0] - event_t0_ns,
                s2_interval[1] - event_t0_ns,
            )
        ax_s2.axvspan(*s2_interval, color="tab:red", alpha=0.08, linewidth=0)

    ax_s1.set_xlabel("Time from event start (ns)")
    ax_s1.set_ylabel("S1 amplitude (summed signal)", color="tab:blue")
    ax_s2.set_ylabel("S2 amplitude (summed signal)", color="tab:red")
    ax_s1.grid(True, alpha=0.3)

    if show_info:
        selected_label = "None" if selected_s1_peak_id is None else str(selected_s1_peak_id)
        drift_label = "None" if drift_time_ns is None else f"{drift_time_ns / 1000.0:.2f} us"
        ax_s1.set_title(
            f"S2={s2_peak_id} | Candidates={len(candidate_s1_peak_ids)} | "
            f"Selected S1={selected_label} | Drift={drift_label}"
        )

    for axis in (ax_s1, ax_s2):
        axis.relim()
        axis.autoscale_view(scalex=True, scaley=True)

    finite_time_arrays = [times[np.isfinite(times)] for times in all_time_arrays]
    finite_time_arrays = [times for times in finite_time_arrays if len(times)]
    if finite_time_arrays:
        x_min = min(float(times.min()) for times in finite_time_arrays)
        x_max = max(float(times.max()) for times in finite_time_arrays)
        margin = max((x_max - x_min) * 0.02, 1.0)
        ax_s1.set_xlim(x_min - margin, x_max + margin)

    handles_s1, labels_s1 = ax_s1.get_legend_handles_labels()
    handles_s2, labels_s2 = ax_s2.get_legend_handles_labels()
    ax_s1.legend(handles_s1 + handles_s2, labels_s1 + labels_s2, loc="best")
    fig.tight_layout()

    return fig, (ax_s1, ax_s2), event_t0_ns
