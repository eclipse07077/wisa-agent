import gzip
import json
from pathlib import Path

import pytest

from experiments.freeze import freeze
from experiments.frozen_check import audit


def write_gzip(path: Path, payload: dict) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)


def bundle(directory: Path) -> list[Path]:
    nodes = [f"n{index:03d}" for index in range(512)]
    score = directory / "score-501.json.gz"
    route = directory / "route-501.json.gz"
    v5 = directory / "v5-501.json.gz"
    v6 = directory / "v6-501.json.gz"
    ablation = directory / "ablation-501.json.gz"
    write_gzip(
        score,
        {
            "method": "official_velox_seeded_chain_v1",
            "detector": "velox",
            "dataset": "optc_h501",
            "root_budget": 512,
            "official_scores": [[node, index] for index, node in enumerate(nodes)],
            "seeds": nodes,
        },
    )
    from experiments.frozen_check import digest

    write_gzip(
        route,
        {
            "method": "flowsub_v1",
            "dataset": "optc_h501",
            "input_manifest_sha256": digest(score),
            "chains": [],
        },
    )
    common = {
        "dataset": "optc_h501",
        "input_manifest_sha256": digest(score),
        "route_manifest_sha256": digest(route),
        "budget": 512,
    }
    write_gzip(
        v5,
        {
            **common,
            "method": "ravel_v5",
            "selections": {"full": {"nodes": nodes}},
        },
    )
    write_gzip(
        v6,
        {
            **common,
            "method": "ravel_v6",
            "certificate": {
                "roots": 512,
                "nodes": 512,
                "budget": 512,
                "root_degree_min": 1,
                "root_degree_max": 1,
                "node_degree_max": 1,
                "mass": 1.0,
                "objective": 2.0,
                "optimal": True,
            },
            "selections": {
                "full": {
                    "nodes": nodes,
                    "ledger": 2.0,
                    "expanded": 4,
                }
            },
        },
    )
    write_gzip(
        ablation,
        {
            **common,
            "method": "ravel_transport_ablation_v1",
            "selections": {
                "topology": {"nodes": nodes},
                "rank": {"nodes": nodes},
            },
        },
    )
    return [score, route, v5, v6, ablation]


def test_audit_checks_complete_bundle(tmp_path):
    files = bundle(tmp_path)
    frozen = tmp_path / "frozen-501.json"
    frozen.write_text(
        json.dumps(freeze(files)),
        encoding="utf-8",
    )
    result = audit(frozen, tmp_path)
    assert result["files"] == 5
    assert result["bundles"][0]["budget"] == 512
    assert result["bundles"][0]["proof_transports"] == 4


def test_audit_rejects_mutated_frozen_file(tmp_path):
    files = bundle(tmp_path)
    frozen = tmp_path / "frozen-501.json"
    frozen.write_text(
        json.dumps(freeze(files)),
        encoding="utf-8",
    )
    with gzip.open(files[0], "at", encoding="utf-8") as handle:
        handle.write(" ")
    with pytest.raises(ValueError, match="size mismatch"):
        audit(frozen, tmp_path)
