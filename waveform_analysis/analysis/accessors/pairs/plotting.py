"""S1-S2 pair plotting methods."""

from ...s1_s2_pair_accessor import S1S2PairAccessor

plot = S1S2PairAccessor.plot
plot_s2_candidates = S1S2PairAccessor.plot_s2_candidates

__all__ = ["plot", "plot_s2_candidates"]
