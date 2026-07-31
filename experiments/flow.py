from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path

from cdm import DATASETS, Dataset, events as sqlite_events
from pg_events import events as postgres_events
from pg_events import node_catalog
from wisa_agent.tc.cdm_agent import (
    CDMAttackAgent,
    NormalProfile,
    validation_threshold,
)
from wisa_agent.tc.flow import FlowSelector


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


def serialize_chain(chain):
    return {
        "id": chain.chain_id,
        "score": chain.score,
        "edges": [
            {
                "source": edge.source_id,
                "target": edge.target_id,
                "score": edge.score,
                "factors": edge.factors,
            }
            for edge in chain.edges
        ],
        "predicates": [
            {
                "id": predicate.predicate_id,
                "stage": predicate.stage.value,
                "target": predicate.target,
                "confidence": predicate.confidence,
                "severity": predicate.severity,
                "endpoints": predicate.details["endpoints"],
                "endpoint_scores": predicate.details.get(
                    "endpoint_scores",
                    (),
                ),
            }
            for predicate in chain.predicates
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--database", type=Path)
    source.add_argument("--pg-dsn")
    parser.add_argument("--manifest", type=Path, required=True)
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
    official_scores = {
        str(node): float(score)
        for node, score in manifest["official_scores"]
    }
    seeds = set(manifest["seeds"])
    dataset = SPLITS[args.dataset]
    sqlite_connection = None
    postgres_connection = None
    if args.database is not None:
        sqlite_connection = sqlite3.connect(
            f"file:{args.database}?mode=ro",
            uri=True,
        )
        event_stream = lambda days: sqlite_events(
            sqlite_connection,
            days,
        )
        event_source = "sqlite_projection"
    else:
        import psycopg2

        postgres_connection = psycopg2.connect(args.pg_dsn)
        catalog = node_catalog(postgres_connection)
        event_stream = lambda days: postgres_events(
            postgres_connection,
            catalog,
            days,
        )
        event_source = "postgres_projection"
    profile = NormalProfile()
    profile.fit(event_stream(dataset.train))
    threshold = validation_threshold(
        profile,
        event_stream(dataset.validation),
    )
    seeded_chains = []
    chain_count = 0
    for day in dataset.test:
        result = CDMAttackAgent(
            profile,
            threshold,
            predicate_mode="trace",
            attribution_mode="grounded",
        ).run(event_stream((day,)))
        chain_count += len(result.chains)
        for chain in result.chains:
            endpoints = {
                node
                for predicate in chain.predicates
                for node in predicate.details["endpoints"]
            }
            if endpoints & seeds:
                seeded_chains.append(chain)
    if sqlite_connection is not None:
        sqlite_connection.close()
    if postgres_connection is not None:
        postgres_connection.close()
    selector = FlowSelector(
        official_scores,
        seeds,
        seeded_chains,
    )
    selections = {
        mode: selector.select(mode=mode)
        for mode in (
            "anomaly",
            "responsibility",
            "flow",
            "full",
        )
    }
    payload = {
        "method": "flowsub_v1",
        "dataset": args.dataset,
        "input_manifest_sha256": hashlib.sha256(
            manifest_bytes
        ).hexdigest(),
        "official_score_sha256": manifest["official_score_sha256"],
        "event_source": event_source,
        "split": {
            "train": dataset.train,
            "validation": dataset.validation,
            "test": dataset.test,
        },
        "profile_threshold": threshold,
        "budget": len(seeds),
        "chain_count": chain_count,
        "seeded_chain_count": len(seeded_chains),
        "chains": [
            serialize_chain(chain)
            for chain in seeded_chains
        ],
        "selections": {
            mode: {
                "nodes": selection.nodes,
                "gains": selection.gains,
                "objective": selection.objective,
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
                "chains": chain_count,
                "seeded_chains": len(seeded_chains),
                "objective": selections["full"].objective,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
