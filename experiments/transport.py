from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from bear import SPLITS, calibration_node_maxima, deserialize_chain
from flow import serialize_chain
from wisa_agent.tc.transport import ExactTransport


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--routes", type=Path, required=True)
    parser.add_argument(
        "--validation-losses",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--dataset",
        choices=tuple(SPLITS),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    started = time.perf_counter()
    manifest_bytes = args.manifest.read_bytes()
    with gzip.open(args.manifest, "rt", encoding="utf-8") as handle:
        manifest = json.load(handle)
    route_bytes = args.routes.read_bytes()
    with gzip.open(args.routes, "rt", encoding="utf-8") as handle:
        route_payload = json.load(handle)
    if route_payload["dataset"] != args.dataset:
        raise ValueError("route dataset mismatch")
    input_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if route_payload["input_manifest_sha256"] != input_sha256:
        raise ValueError("route input manifest mismatch")
    official_scores = {
        str(node): float(score)
        for node, score in manifest["official_scores"]
    }
    seeds = set(manifest["seeds"])
    calibration, calibration_sha256, calibration_files = (
        calibration_node_maxima(args.validation_losses)
    )
    if max(calibration) != float(manifest["thresholds"]["velox"]):
        raise ValueError("validation maximum does not match manifest")
    chains = tuple(
        deserialize_chain(item)
        for item in route_payload["chains"]
    )
    transport = ExactTransport(
        official_scores,
        calibration,
        seeds,
        chains,
    )
    selection, certificate = transport.select()
    dataset = SPLITS[args.dataset]
    payload = {
        "method": "ravel_v6",
        "dataset": args.dataset,
        "input_manifest_sha256": input_sha256,
        "route_manifest_sha256": hashlib.sha256(
            route_bytes
        ).hexdigest(),
        "official_score_sha256": manifest["official_score_sha256"],
        "calibration_sha256": calibration_sha256,
        "calibration_files": calibration_files,
        "calibration_nodes": len(calibration),
        "calibration_maximum": max(calibration),
        "kappa": 0.5,
        "conditioned": True,
        "transport": True,
        "conditional_transport": True,
        "exact_transport": True,
        "split": {
            "train": dataset.train,
            "validation": dataset.validation,
            "test": dataset.test,
        },
        "profile_threshold": route_payload["profile_threshold"],
        "budget": len(seeds),
        "chain_count": len(transport.ledger.chains),
        "account_count": len(transport.ledger.accounts),
        "chains": [
            serialize_chain(chain)
            for chain in transport.ledger.chains
        ],
        "certificate": asdict(certificate),
        "selections": {
            "full": {
                "nodes": selection.nodes,
                "ledger": selection.ledger,
                "candidates": selection.candidates,
                "budget": selection.budget,
                "mass": selection.mass,
                "expanded": selection.expanded,
                "values": [
                    asdict(value)
                    for value in selection.values
                ],
            },
        },
        "runtime_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    print(
        json.dumps(
            {
                "dataset": args.dataset,
                "budget": len(seeds),
                "candidates": selection.candidates,
                "chains": len(transport.ledger.chains),
                "accounts": len(transport.ledger.accounts),
                "ledger": selection.ledger,
                "expanded": selection.expanded,
                "runtime_seconds": payload["runtime_seconds"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
