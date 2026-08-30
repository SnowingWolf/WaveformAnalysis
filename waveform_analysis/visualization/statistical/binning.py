"""Statistical plot bin construction."""

from matplotlib.scale import SymmetricalLogTransform
import numpy as np


def symlog_bin_edges(lo, hi, nbin, linthresh):
    """Return bins that are evenly spaced in Matplotlib symlog space."""
    transform = SymmetricalLogTransform(base=10, linthresh=linthresh, linscale=1)
    transformed_limits = transform.transform(np.asarray([lo, hi], dtype=np.float64))
    transformed_edges = np.linspace(transformed_limits[0], transformed_limits[1], nbin + 1)
    edges = transform.inverted().transform(transformed_edges)
    edges[0] = lo
    edges[-1] = hi
    return edges
