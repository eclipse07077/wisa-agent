import pytest

from experiments.pidsmaker import label_access_guard


def test_label_access_guard_blocks_ground_truth_reads():
    with pytest.raises(RuntimeError):
        label_access_guard(
            "open",
            ("/repo/Ground_Truth/orthrus/node.csv", "r", 0),
        )


def test_label_access_guard_allows_non_label_artifacts():
    assert label_access_guard(
        "open",
        ("/repo/artifacts/test.csv", "r", 0),
    ) is None
