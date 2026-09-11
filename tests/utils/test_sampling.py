import numpy as np
import pandas as pd
import pytest

from waveform_analysis.utils import adaptive_sample_count, adaptive_stratified_sample_2d
from waveform_analysis.utils.sampling import (
    __all__ as sampling_all,
)
from waveform_analysis.utils.sampling import (
    _assign_bins_2d,
    _make_bin_edges,
    _parse_2d_bins,
)


def test_parse_2d_bins_supports_uniform_separate_explicit_and_mixed_specs():
    x = np.linspace(-1.0, 5.0, 20)
    y = np.linspace(0.0, 100.0, 20)
    x_edges = np.array([-1.0, 0.0, 2.0, 5.0])
    y_edges = np.array([0.0, 10.0, 40.0, 100.0])

    uniform_x, uniform_y = _parse_2d_bins(x, y, bins=10)
    assert len(uniform_x) == len(uniform_y) == 11

    separate_x, separate_y = _parse_2d_bins(x, y, bins=(10, 20))
    assert len(separate_x) == 11
    assert len(separate_y) == 21

    explicit_x, explicit_y = _parse_2d_bins(x, y, bins=(x_edges, y_edges))
    np.testing.assert_array_equal(explicit_x, x_edges)
    np.testing.assert_array_equal(explicit_y, y_edges)

    mixed_x, mixed_y = _parse_2d_bins(
        x,
        y,
        bins=(10, y_edges),
        range=((-2.0, 6.0), (999.0, 1000.0)),
    )
    assert (mixed_x[0], mixed_x[-1]) == (-2.0, 6.0)
    np.testing.assert_array_equal(mixed_y, y_edges)


@pytest.mark.parametrize(
    "bins",
    [
        0,
        -1,
        True,
        2.5,
        (10,),
        (10, 20, 30),
        (np.array([0.0, 1.0, 1.0, 2.0]), np.array([0.0, 1.0])),
        (np.array([0.0, 2.0, 1.0]), np.array([0.0, 1.0])),
        (np.array([0.0, np.nan, 2.0]), np.array([0.0, 1.0])),
    ],
)
def test_invalid_bin_specs_raise_value_error(bins):
    with pytest.raises(ValueError):
        _parse_2d_bins(np.arange(5.0), np.arange(5.0), bins=bins)


@pytest.mark.parametrize(
    "value_range",
    [
        (0.0,),
        (0.0, 1.0, 2.0),
        (0.0, np.inf),
        (1.0, 1.0),
        (2.0, 1.0),
        "bad",
    ],
)
def test_invalid_integer_bin_ranges_raise_value_error(value_range):
    with pytest.raises(ValueError):
        _make_bin_edges(np.arange(5.0), 4, value_range=value_range)


def test_assign_bins_includes_both_outer_edges_and_rejects_outside_values():
    x_edges = np.array([0.0, 1.0, 2.0])
    y_edges = np.array([0.0, 10.0, 20.0])
    x_bin, y_bin = _assign_bins_2d(
        np.array([-0.1, 0.0, 1.0, 2.0, 2.1]),
        np.array([1.0, 0.0, 10.0, 20.0, 20.1]),
        x_edges,
        y_edges,
    )

    np.testing.assert_array_equal(x_bin, [-1, 0, 1, 1, 2])
    np.testing.assert_array_equal(y_bin, [0, 0, 1, 1, 2])


def test_adaptive_sample_count_is_bounded_and_monotonic():
    counts = [adaptive_sample_count(n, n_full=4, n_max=12) for n in range(101)]

    assert counts[0] == 0
    assert counts[4] == 4
    assert counts[5] >= 5
    assert all(a <= b for a, b in zip(counts, counts[1:], strict=False))
    assert all(count <= 12 for count in counts)
    assert all(count <= n for n, count in enumerate(counts))
    assert adaptive_sample_count(20, n_full=4, n_max=4) == 4


@pytest.mark.parametrize(
    ("n", "n_full", "n_max"),
    [
        (-1, 4, 12),
        (5.5, 4, 12),
        (5, -1, 12),
        (5, 4.0, 12),
        (5, 4, 3),
        (5, True, 12),
    ],
)
def test_adaptive_sample_count_rejects_invalid_parameters(n, n_full, n_max):
    with pytest.raises(ValueError):
        adaptive_sample_count(n, n_full=n_full, n_max=n_max)


def test_sampler_handles_boundaries_nonfinite_rows_and_bin_info_without_mutation():
    data = pd.DataFrame(
        {
            "x": [0.0, 1.0, 2.0, -0.1, 2.1, np.nan, 1.5],
            "y": [0.0, 10.0, 20.0, 10.0, 20.0, 10.0, np.inf],
            "waveform_id": list(range(7)),
        },
        index=[10, 11, 12, 13, 14, 15, 16],
    )
    original = data.copy(deep=True)

    sampled, bin_info = adaptive_stratified_sample_2d(
        data,
        x="x",
        y="y",
        bins=(np.array([0.0, 1.0, 2.0]), np.array([0.0, 10.0, 20.0])),
        n_full=10,
        n_max=12,
        representative=False,
        random_state=42,
        return_bin_info=True,
    )

    assert sampled.index.tolist() == [10, 11, 12]
    assert list(sampled.columns) == list(data.columns)
    assert set(bin_info.columns) == {
        "x_bin",
        "y_bin",
        "x_left",
        "x_right",
        "y_left",
        "y_right",
        "occupancy",
        "n_sampled",
        "sampling_fraction",
        "representative_index",
    }
    assert bin_info["occupancy"].sum() == 3
    assert bin_info["n_sampled"].sum() == len(sampled)
    assert bin_info["sampling_fraction"].tolist() == [1.0, 1.0]
    pd.testing.assert_frame_equal(data, original)


def test_sampler_is_seeded_and_representative_is_seed_independent():
    x = np.full(30, 0.2)
    y = np.full(30, 0.2)
    x[5] = 0.5
    y[5] = 0.5
    data = pd.DataFrame(
        {"x": x, "y": y, "value": np.arange(len(x))},
        index=100 + np.arange(len(x)),
    )
    kwargs = {
        "bins": (np.array([0.0, 1.0]), np.array([0.0, 1.0])),
        "n_full": 4,
        "n_max": 6,
        "return_bin_info": True,
    }

    first, first_info = adaptive_stratified_sample_2d(data, "x", "y", random_state=42, **kwargs)
    second, second_info = adaptive_stratified_sample_2d(data, "x", "y", random_state=42, **kwargs)
    other, other_info = adaptive_stratified_sample_2d(data, "x", "y", random_state=43, **kwargs)

    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(first_info, second_info)
    assert first_info.loc[0, "representative_index"] == 105
    assert other_info.loc[0, "representative_index"] == 105
    assert not first.index.equals(other.index)
    assert len(first) == len(other) == 6


def test_representative_false_uses_only_seeded_random_selection():
    data = pd.DataFrame({"x": np.full(30, 0.5), "y": np.full(30, 0.5)})

    sampled, info = adaptive_stratified_sample_2d(
        data,
        "x",
        "y",
        bins=(np.array([0.0, 1.0]), np.array([0.0, 1.0])),
        n_full=1,
        n_max=3,
        representative=False,
        random_state=7,
        return_bin_info=True,
    )

    assert len(sampled) == 3
    assert info.loc[0, "n_sampled"] == 3
    assert info.loc[0, "representative_index"] is None


@pytest.mark.parametrize("representative", [True, False])
def test_zero_cap_never_selects_a_row(representative):
    data = pd.DataFrame({"x": [0.2, 0.3], "y": [0.2, 0.3]}, index=[20, 21])

    sampled, info = adaptive_stratified_sample_2d(
        data,
        "x",
        "y",
        bins=(np.array([0.0, 1.0]), np.array([0.0, 1.0])),
        n_full=0,
        n_max=0,
        representative=representative,
        random_state=42,
        return_bin_info=True,
    )

    assert sampled.empty
    assert info.loc[0, "occupancy"] == 2
    assert info.loc[0, "n_sampled"] == 0
    assert info.loc[0, "sampling_fraction"] == 0.0
    assert info.loc[0, "representative_index"] is None


def test_explicit_edges_support_empty_input_but_integer_bins_need_a_range():
    data = pd.DataFrame({"x": pd.Series(dtype=float), "y": pd.Series(dtype=float)})

    sampled, info = adaptive_stratified_sample_2d(
        data,
        "x",
        "y",
        bins=(np.array([0.0, 1.0]), np.array([0.0, 1.0])),
        return_bin_info=True,
    )
    assert sampled.empty
    assert info.empty

    with pytest.raises(ValueError, match="Cannot determine bin range"):
        adaptive_stratified_sample_2d(data, "x", "y", bins=4)

    ranged = adaptive_stratified_sample_2d(
        data,
        "x",
        "y",
        bins=4,
        range=((0.0, 1.0), (0.0, 1.0)),
    )
    assert ranged.empty


def test_sampler_accepts_coordinate_arrays_and_validates_input_contract():
    data = pd.DataFrame({"value": [1, 2, 3]})
    sampled = adaptive_stratified_sample_2d(
        data,
        x=np.array([0.0, 0.5, 1.0]),
        y=np.array([0.0, 0.5, 1.0]),
        bins=2,
        n_full=3,
    )
    assert len(sampled) == 3

    with pytest.raises(TypeError, match="pandas-style iloc"):
        adaptive_stratified_sample_2d([], [], [], bins=2)
    with pytest.raises(KeyError, match="missing"):
        adaptive_stratified_sample_2d(data, "missing", [0.0, 0.5, 1.0], bins=2)
    with pytest.raises(ValueError, match="same length"):
        adaptive_stratified_sample_2d(data, [0.0], [0.0, 0.5, 1.0], bins=2)
    with pytest.raises(ValueError, match="one-dimensional"):
        adaptive_stratified_sample_2d(
            data,
            np.array([[0.0, 0.5, 1.0]]),
            [0.0, 0.5, 1.0],
            bins=2,
        )


def test_public_module_exports_only_the_supported_functions():
    assert sampling_all == ["adaptive_sample_count", "adaptive_stratified_sample_2d"]
