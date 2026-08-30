"""Pair-table index methods."""

from ...s1_s2_pair_accessor import S1S2PairAccessor

build_indices = S1S2PairAccessor._build_indices
build_one_to_many_index = S1S2PairAccessor._build_one_to_many_index

__all__ = ["build_indices", "build_one_to_many_index"]
