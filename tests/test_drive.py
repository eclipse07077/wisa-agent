from pathlib import Path

import pytest

from experiments.drive import FILES, digest, request, sha256


def test_drive_ids_are_frozen():
    assert FILES == {
        "optc_h501": "1046BVjpMql1bb5WHr9yQeB6Uq6RpngbM",
        "optc_h201": "1OSZXCQrocFSRN7wkPM02p-BqE2WmgdLD",
    }


def test_drive_request_keeps_token_in_header():
    value = request("https://example.test", "secret", 10)
    assert value.get_header("Authorization") == "Bearer secret"
    assert value.get_header("Range") == "bytes=10-"
    assert "secret" not in value.full_url


def test_drive_request_supports_public_access():
    value = request("https://example.test", None, 0, 511)
    assert value.get_header("Authorization") is None
    assert value.get_header("Range") == "bytes=0-511"


def test_digest_reads_binary_file(tmp_path: Path):
    path = tmp_path / "sample"
    path.write_bytes(b"abc")
    assert digest(path) == "900150983cd24fb0d6963f7d28e17f72"
    assert sha256(path) == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )


def test_unknown_dataset_is_rejected(tmp_path: Path):
    with pytest.raises(KeyError):
        FILES["unknown"]
