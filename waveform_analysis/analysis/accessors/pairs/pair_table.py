"""Pair-table source selection."""


def pair_data_key(source: str) -> str:
    """Resolve an Accessor source name to its Context data product."""
    try:
        return {
            "pairs": "s1_s2_pairs",
            "candidates": "s1_s2_pair_candidates",
            "events": "events",
        }[source]
    except KeyError as exc:
        raise ValueError(
            f"Invalid source '{source}'. Must be 'pairs', 'candidates', or 'events'."
        ) from exc
