import csv
import gzip
import hashlib
import json
from pathlib import Path

from experiments.optc_method_eval import evaluate_methods


def write_gzip(path: Path, payload: dict) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)


def test_method_evaluator_compares_only_frozen_outputs(tmp_path):
    official = [f"N{index:03d}" for index in range(512)]
    extras = ["FLOW", "V5", "V6"]
    manifest = {
        "root_budget": 512,
        "seeds": official,
        "official_scores": [
            [node, float(515 - index)]
            for index, node in enumerate(official + extras)
        ],
    }
    manifest_path = tmp_path / "manifest.json.gz"
    write_gzip(manifest_path, manifest)
    manifest_sha256 = hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()
    route = {
        "method": "flowsub_v1",
        "input_manifest_sha256": manifest_sha256,
        "budget": 512,
        "selections": {
            "full": {"nodes": official[1:] + ["FLOW"]},
        },
    }
    route_path = tmp_path / "route.json.gz"
    write_gzip(route_path, route)
    route_sha256 = hashlib.sha256(route_path.read_bytes()).hexdigest()

    def ravel_payload(method: str, node: str) -> dict:
        return {
            "method": method,
            "input_manifest_sha256": manifest_sha256,
            "route_manifest_sha256": route_sha256,
            "budget": 512,
            "selections": {
                "full": {"nodes": official[1:] + [node]},
            },
        }

    v5_path = tmp_path / "v5.json.gz"
    v6_path = tmp_path / "v6.json.gz"
    write_gzip(v5_path, ravel_payload("ravel_v5", "V5"))
    write_gzip(v6_path, ravel_payload("ravel_v6", "V6"))
    events_path = tmp_path / "events.json.gz"
    with gzip.open(events_path, "wt", encoding="utf-8") as handle:
        for actor in ("FLOW", "V6"):
            handle.write(
                json.dumps(
                    {
                        "actorID": actor,
                        "hostname": "SysClient0201.systemia.com",
                        "pid": 7,
                        "timestamp": "2019-09-23T11:23:00-04:00",
                    }
                )
                + "\n"
            )
    segments_path = tmp_path / "segments.csv"
    with segments_path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(
            [
                "SysClient0201.systemia.com",
                7,
                "2019-09-23T11:22:00-04:00",
                "2019-09-23T11:24:00-04:00",
            ]
        )
    result = evaluate_methods(
        manifest_path,
        route_path,
        v5_path,
        v6_path,
        events_path,
        segments_path,
        "0201",
    )
    assert result["comparison_status"] == "preregistered_before_host_labels"
    assert result["selections"]["velox"]["recovered"] == 0
    assert result["selections"]["flowsub"]["recovered"] == 1
    assert result["selections"]["ravel_v5"]["recovered"] == 0
    assert result["selections"]["ravel_v6"]["recovered"] == 1
    assert (
        result["comparisons"]["ravel_v5_to_ravel_v6"][
            "recovered_delta"
        ]
        == 1
    )
