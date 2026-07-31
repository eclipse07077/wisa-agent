from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path

from cdm import DATASETS, Dataset, events
from flow import serialize_chain
from wisa_agent.method import Chain, ChainEdge, Predicate, Stage
from wisa_agent.tc.bear import BearLedger
from wisa_agent.tc.cdm_agent import (
    CDMAttackAgent,
    NormalProfile,
    validation_threshold,
)


SPLITS = {
    "cadets": Dataset(
        train=(2, 3, 4, 5, 7, 8, 9),
        validation=(10,),
        test=(6, 11, 12, 13),
        labels=DATASETS["cadets"].labels,
    ),
    "theia": Dataset(
        train=(2, 3, 4, 5, 6, 7, 8),
        validation=(9,),
        test=(10, 12, 13),
        labels=DATASETS["theia"].labels,
    ),
    "optc_h051": DATASETS["optc_h051"],
    "optc_h201": DATASETS["optc_h201"],
    "optc_h501": DATASETS["optc_h501"],
}


def deserialize_chain(payload: dict) -> Chain:
    return Chain(
        chain_id=payload["id"],
        predicates=tuple(
            Predicate(
                predicate_id=item["id"],
                stage=Stage(item["stage"]),
                target=item["target"],
                layer="replay",
                relation="replay",
                timestamp=None,
                context=frozenset(),
                confidence=float(item["confidence"]),
                severity=float(item["severity"]),
                mission_relevant=(
                    Stage(item["stage"]) == Stage.MISSION_EFFECT
                ),
                evidence_ids=(item["id"],),
                details={
                    "endpoints": tuple(item["endpoints"]),
                    "endpoint_scores": tuple(
                        tuple(value)
                        for value in item["endpoint_scores"]
                    ),
                },
            )
            for item in payload["predicates"]
        ),
        edges=tuple(
            ChainEdge(
                source_id=item["source"],
                target_id=item["target"],
                score=float(item["score"]),
                factors=tuple(
                    tuple(value)
                    for value in item["factors"]
                ),
            )
            for item in payload["edges"]
        ),
        score=float(payload["score"]),
    )


def calibration_node_maxima(
    directory: Path,
) -> tuple[list[float], str, int]:
    maxima: dict[str, float] = {}
    digest = hashlib.sha256()
    files = sorted(directory.rglob("*.csv"))
    for path in files:
        relative = path.relative_to(directory).as_posix()
        digest.update(relative.encode("utf-8"))
        payload = path.read_bytes()
        digest.update(payload)
        with path.open(newline="", encoding="utf-8") as handle:
            rows = csv.DictReader(handle)
            for row in rows:
                loss = float(row["loss"])
                for node in (row["srcnode"], row["dstnode"]):
                    maxima[node] = max(
                        maxima.get(node, float("-inf")),
                        loss,
                    )
    if not maxima:
        raise ValueError("validation losses are empty")
    return list(maxima.values()), digest.hexdigest(), len(files)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    parser.add_argument("--routes", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
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
        choices=("bear_v1", "bear_v2"),
        default="bear_v1",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    started = time.perf_counter()
    manifest_bytes = args.manifest.read_bytes()
    with gzip.open(args.manifest, "rt", encoding="utf-8") as handle:
        manifest = json.load(handle)
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
    dataset = SPLITS[args.dataset]
    route_manifest_sha256 = None
    if args.routes is not None:
        route_bytes = args.routes.read_bytes()
        with gzip.open(args.routes, "rt", encoding="utf-8") as handle:
            route_payload = json.load(handle)
        if route_payload["dataset"] != args.dataset:
            raise ValueError("route dataset mismatch")
        if route_payload["input_manifest_sha256"] != hashlib.sha256(
            manifest_bytes
        ).hexdigest():
            raise ValueError("route input manifest mismatch")
        chains = [
            deserialize_chain(item)
            for item in route_payload["chains"]
        ]
        threshold = float(route_payload["profile_threshold"])
        route_manifest_sha256 = hashlib.sha256(
            route_bytes
        ).hexdigest()
    else:
        if args.database is None:
            raise ValueError("database or routes is required")
        connection = sqlite3.connect(
            f"file:{args.database}?mode=ro",
            uri=True,
        )
        profile = NormalProfile()
        profile.fit(events(connection, dataset.train))
        threshold = validation_threshold(
            profile,
            events(connection, dataset.validation),
        )
        chains = []
        for day in dataset.test:
            result = CDMAttackAgent(
                profile,
                threshold,
                predicate_mode="trace",
                attribution_mode="grounded",
            ).run(events(connection, (day,)))
            chains.extend(result.chains)
        connection.close()
    ledger = BearLedger(
        official_scores,
        calibration,
        seeds,
        chains,
        unit_growth=args.method == "bear_v2",
    )
    selections = {
        mode: ledger.select(mode=mode)
        for mode in ("local", "chain", "full")
    }
    payload = {
        "method": args.method,
        "dataset": args.dataset,
        "input_manifest_sha256": hashlib.sha256(
            manifest_bytes
        ).hexdigest(),
        "route_manifest_sha256": route_manifest_sha256,
        "official_score_sha256": manifest["official_score_sha256"],
        "calibration_sha256": calibration_sha256,
        "calibration_files": calibration_files,
        "calibration_nodes": len(calibration),
        "calibration_maximum": max(calibration),
        "kappa": 0.5,
        "unit_growth": ledger.unit_growth,
        "split": {
            "train": dataset.train,
            "validation": dataset.validation,
            "test": dataset.test,
        },
        "profile_threshold": threshold,
        "budget": len(seeds),
        "chain_count": len(chains),
        "chains": [
            serialize_chain(chain)
            for chain in chains
        ],
        "length_mass": ledger.length_mass,
        "ledgers": {
            "local": ledger.local_ledger,
            "chain": ledger.chain_ledger,
            "full": ledger.ledger,
        },
        "selections": {
            mode: {
                "nodes": selection.nodes,
                "ledger": selection.ledger,
                "candidates": selection.candidates,
                "budget": selection.budget,
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
                "chains": len(chains),
                "calibration_nodes": len(calibration),
                "ledger": selections["full"].ledger,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
