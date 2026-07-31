import hashlib

from experiments.freeze import freeze


def test_freeze_orders_and_hashes_files(tmp_path):
    second = tmp_path / "b.txt"
    first = tmp_path / "a.txt"
    second.write_bytes(b"second")
    first.write_bytes(b"first")
    payload = freeze([second, first])
    assert [item["name"] for item in payload["files"]] == [
        "a.txt",
        "b.txt",
    ]
    assert payload["files"][0]["sha256"] == hashlib.sha256(
        b"first"
    ).hexdigest()
    assert payload["files"][1]["bytes"] == 6
