"""Pair-table one-to-one and one-to-many indexes."""

import numpy as np


def build_one_to_many_index(pairs: np.ndarray, field_name: str) -> dict[int, np.ndarray]:
    result: dict[int, list[int]] = {}
    for index, pair in enumerate(pairs):
        result.setdefault(int(pair[field_name]), []).append(index)
    return {key: np.asarray(indices, dtype=np.int64) for key, indices in result.items()}


def build_indices(self) -> None:
    assert self._pairs is not None, "_load_pairs must be called first"
    self._pair_id_to_idx = {int(pair["pair_id"]): index for index, pair in enumerate(self._pairs)}
    self._s1_to_indices = build_one_to_many_index(self._pairs, "s1_peak_id")
    self._s2_to_indices = build_one_to_many_index(self._pairs, "s2_peak_id")


__all__ = ["build_indices", "build_one_to_many_index"]
