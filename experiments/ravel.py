from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from bear import (
    SPLITS,
    calibration_node_maxima,
    deserialize_chain,
)
from flow import serialize_chain
from wisa_agent.tc.ravel import RavelLedger, RavelTransport


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
    parser.add_argument(
        "--method",
        choices=(
            "ravel_v1",
            "ravel_v2",
            "ravel_v3",
            "ravel_v4",
            "ravel_v5",
        ),
        default="ravel_v1",
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
    chains = [
        deserialize_chain(item)
        for item in route_payload["chains"]
    ]
    if args.method in {"ravel_v4", "ravel_v5"}:
        transport = RavelTransport(
            official_scores,
            calibration,
            seeds,
            chains,
            conditional_hold=args.method == "ravel_v5",
        )
        ledger = transport.ledger
        selections = {"full": transport.select()}
    else:
        ledger = RavelLedger(
            official_scores,
            calibration,
            seeds,
            chains,
            conditioned=args.method in {"ravel_v2", "ravel_v3"},
            conserved=args.method == "ravel_v3",
        )
        selections = {
            mode: ledger.select(mode=mode)
            for mode in ("local", "chain", "full")
        }
    dataset = SPLITS[args.dataset]
    payload = {
        "method": args.method,
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
        "conditioned": ledger.conditioned,
        "conserved": ledger.conserved,
        "transport": args.method in {"ravel_v4", "ravel_v5"},
        "conditional_transport": args.method == "ravel_v5",
        "split": {
            "train": dataset.train,
            "validation": dataset.validation,
            "test": dataset.test,
        },
        "profile_threshold": route_payload["profile_threshold"],
        "budget": len(seeds),
        "chain_count": len(ledger.chains),
        "account_count": len(ledger.accounts),
        "chains": [
            serialize_chain(chain)
            for chain in ledger.chains
        ],
        "ledgers": ledger.ledgers,
        "selections": {
            mode: {
                "nodes": selection.nodes,
                "ledger": selection.ledger,
                "candidates": selection.candidates,
                "budget": selection.budget,
                **(
                    {
                        "mass": selection.mass,
                        "expanded": selection.expanded,
                    }
                    if args.method in {"ravel_v4", "ravel_v5"}
                    else {}
                ),
                "values": [
                    asdict(value)
                    for value in selection.values
                ],
            }
            for mode, selection in selections.items()
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
                "candidates": selections["full"].candidates,
                "chains": len(ledger.chains),
                "accounts": len(ledger.accounts),
                "ledger": selections["full"].ledger,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
