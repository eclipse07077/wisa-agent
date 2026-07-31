import csv
import gzip
import hashlib
import json
from pathlib import Path

from experiments.optc_ablation_eval import evaluate_ablation


def write_gzip(path: Path, payload: dict) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)


def test_ablation_evaluator_uses_frozen_selections(tmp_path):
    official = [f"N{index:03d}" for index in range(512)]
    manifest = {
        "root_budget": 512,
        "seeds": official,
        "official_scores": [
            [node, float(513 - index)]
            for index, node in enumerate(official + ["MALICIOUS"])
        ],
    }
    manifest_path = tmp_path / "manifest.json.gz"
    write_gzip(manifest_path, manifest)
    ablation = {
        "method": "ravel_transport_ablation_v1",
        "input_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "budget": 512,
        "selections": {
            "topology": {"nodes": official},
            "rank": {"nodes": official[1:] + ["MALICIOUS"]},
        },
    }
    ablation_path = tmp_path / "ablation.json.gz"
    write_gzip(ablation_path, ablation)
    events_path = tmp_path / "events.json.gz"
    with gzip.open(events_path, "wt", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "actorID": "MALICIOUS",
                    "hostname": "SysClient0501.systemia.com",
                    "pid": 7,
                    "timestamp": "2019-09-24T10:30:00-04:00",
                }
            )
            + "\n"
        )
    segments_path = tmp_path / "segments.csv"
    with segments_path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(
            [
                "SysClient0501.systemia.com",
                7,
                "2019-09-24T10:29:00-04:00",
                "2019-09-24T10:31:00-04:00",
            ]
        )
    result = evaluate_ablation(
        manifest_path,
        ablation_path,
        events_path,
        segments_path,
        "0501",
    )
    assert result["selections"]["topology"]["recovered"] == 0
    assert result["selections"]["rank"]["recovered"] == 1
    assert result["selections"]["rank"]["segments"][0]["recovered"] == 1
