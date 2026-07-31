import pytest

from experiments.velox_chain import select_seeds


def test_select_seeds_uses_strict_threshold():
    assert select_seeds(
        {"a": 1.0, "b": 2.0, "c": 2.0},
        2.0,
        None,
    ) == set()


def test_select_seeds_uses_deterministic_capacity():
    assert select_seeds(
        {"c": 2.0, "b": 2.0, "a": 1.0},
        9.0,
        2,
    ) == {"b", "c"}


def test_select_seeds_rejects_invalid_capacity():
    with pytest.raises(ValueError):
        select_seeds({"a": 1.0}, 0.0, 2)
