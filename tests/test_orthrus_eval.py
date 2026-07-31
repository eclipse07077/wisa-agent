import gzip
import json
from pathlib import Path

from experiments.orthrus_eval import evaluate, malicious_uuids


def write_gzip(path: Path, value: dict) -> str:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(value, handle)
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_malicious_uuids_preserves_unique_rows(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text(
        "a,path,process\nA,path,process\nb,path,file\n",
        encoding="utf-8",
    )
    values, rows = malicious_uuids(path)
    assert values == {"A", "B"}
    assert rows == 3


def test_heldout_evaluation_uses_frozen_endpoints(tmp_path):
    manifest_path = tmp_path / "score.json.gz"
    routes_path = tmp_path / "route.json.gz"
    source_path = tmp_path / "v6.json.gz"
    candidate_path = tmp_path / "cert.json.gz"
    labels_path = tmp_path / "labels.csv"
    manifest = {
        "dataset": "optc_h051",
        "seeds": ["A", "B"],
        "official_scores": [["A", 3], ["B", 2], ["C", 1]],
    }
    manifest_sha256 = write_gzip(manifest_path, manifest)
    routes_sha256 = write_gzip(
        routes_path,
        {
            "method": "flowsub_v1",
            "input_manifest_sha256": manifest_sha256,
            "selections": {"full": {"nodes": ["A", "B"]}},
        },
    )
    source_sha256 = write_gzip(
        source_path,
        {
            "method": "ravel_v6",
            "input_manifest_sha256": manifest_sha256,
            "route_manifest_sha256": routes_sha256,
            "selections": {"full": {"nodes": ["A", "B"]}},
        },
    )
    write_gzip(
        candidate_path,
        {
            "method": "ravel_cert_v4",
            "input_manifest_sha256": manifest_sha256,
            "source_sha256": source_sha256,
            "certified_transports": 1,
            "selections": {"full": {"nodes": ["A", "C"]}},
        },
    )
    labels_path.write_text("A,x,p\nC,y,p\n", encoding="utf-8")
    result = evaluate(
        manifest_path,
        routes_path,
        source_path,
        candidate_path,
        labels_path,
    )
    assert result["metrics"]["official"]["recovered"] == 1
    assert result["metrics"]["certified"]["recovered"] == 2
    assert result["primary_safety"] is True
    assert result["secondary_efficacy"] is True
    assert result["competitive_noninferiority"] is True
    assert result["strict_all_comparators"] is True
