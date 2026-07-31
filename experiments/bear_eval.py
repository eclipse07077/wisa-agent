from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from velox_eval import selected_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--bear", type=Path, required=True)
    parser.add_argument(
        "--ground-truth",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest_bytes = args.manifest.read_bytes()
    with gzip.open(args.manifest, "rt", encoding="utf-8") as handle:
        manifest = json.load(handle)
    with gzip.open(args.bear, "rt", encoding="utf-8") as handle:
        bear = json.load(handle)
    if hashlib.sha256(manifest_bytes).hexdigest() != bear[
        "input_manifest_sha256"
    ]:
        raise ValueError("input manifest hash mismatch")
    labels_by_attack = {}
    for path in args.ground_truth:
        with path.open(newline="", encoding="utf-8") as handle:
            labels_by_attack[path.name] = {
                row[0].upper()
                for row in csv.reader(handle)
                if row
            }
    labels = set().union(*labels_by_attack.values())
    scores = {
        str(node): float(score)
        for node, score in manifest["official_scores"]
    }
    universe = set(scores)
    seeds = set(manifest["seeds"])
    selections = {
        mode: set(payload["nodes"])
        for mode, payload in bear["selections"].items()
    }
    result = {
        "method": bear["method"],
        "dataset": bear["dataset"],
        "split": bear["split"],
        "budget": bear["budget"],
        "nodes": len(universe),
        "positives": len(labels & universe),
        "official_seeds": selected_metrics(
            universe,
            labels,
            seeds,
        ),
        "selections": {
            mode: {
                **selected_metrics(
                    universe,
                    labels,
                    selected,
                ),
                "ledger": bear["selections"][mode]["ledger"],
            }
            for mode, selected in selections.items()
        },
        "attacks": {
            name: {
                "positives": len(values & universe),
                "official_seeds_tp": len(values & seeds & universe),
                **{
                    f"{mode}_tp": len(
                        values & selected & universe
                    )
                    for mode, selected in selections.items()
                },
            }
            for name, values in labels_by_attack.items()
        },
        "candidate_count": bear["selections"]["full"]["candidates"],
        "chain_count": bear["chain_count"],
        "calibration_nodes": bear["calibration_nodes"],
        "calibration_sha256": bear["calibration_sha256"],
        "runtime_seconds": bear["runtime_seconds"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
