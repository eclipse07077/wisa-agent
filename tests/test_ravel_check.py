import gzip
import json

from ravel_check import check


def write(path, runtime):
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(
            {
                "method": "ravel_v5",
                "selections": {"full": {"nodes": ["a", "b"]}},
                "runtime_seconds": runtime,
            },
            handle,
        )


def test_runtime_only_difference_is_equivalent(tmp_path):
    reference = tmp_path / "reference.json.gz"
    candidate = tmp_path / "candidate.json.gz"
    write(reference, 10.0)
    write(candidate, 2.0)
    result = check(reference, candidate)
    assert result["content_equal_except_runtime"] is True
    assert result["reference_runtime_seconds"] == 10.0
    assert result["candidate_runtime_seconds"] == 2.0
