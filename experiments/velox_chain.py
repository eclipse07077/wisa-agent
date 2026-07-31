from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sqlite3
import time
from pathlib import Path

try:
    from experiments.cdm import DATASETS, Dataset, events as sqlite_events
    from experiments.pg_events import events as postgres_events
    from experiments.pg_events import node_catalog
except ModuleNotFoundError:
    from cdm import DATASETS, Dataset, events as sqlite_events
    from pg_events import events as postgres_events
    from pg_events import node_catalog
from wisa_agent.tc.cdm_agent import (
    CDMAttackAgent,
    NormalProfile,
    validation_threshold,
)

OFFICIAL_SPLITS = {
    "cadets": Dataset(
        train=(2, 3, 4, 5, 7, 8, 9),
        validation=(10,),
        test=(6, 11, 12, 13),
        labels=DATASETS["cadets"].labels,
    ),
    "clearscope": DATASETS["clearscope"],
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


def select_seeds(
    scores: dict[str, float],
    threshold: float,
    budget: int | None,
) -> set[str]:
    if budget is None:
        return {
            node
            for node, score in scores.items()
            if score > threshold
        }
    if budget < 1 or budget > len(scores):
        raise ValueError("budget must be within the scored node universe")
    ordered = sorted(
        scores.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return {
        node
        for node, _ in ordered[:budget]
    }


def load_scores(
    path: Path,
    connection: sqlite3.Connection | None,
    postgres: tuple[str, str, str, str] | None,
    mapping_override: dict[str, str] | None = None,
) -> dict[str, float]:
    import torch

    payload = torch.load(path, map_location="cpu")
    nodes = payload["nodes"]
    scores = payload["pred_scores"]
    if len(nodes) != len(scores):
        raise ValueError("node and score lengths differ")
    has_mapping = (
        connection is not None
        and connection.execute(
            "select count(*) from sqlite_master "
            "where type = 'table' and name = 'node_index'"
        ).fetchone()[0]
    )
    if mapping_override is not None:
        mapping = mapping_override
    elif has_mapping and connection is not None:
        mapping = dict(
            connection.execute("select index_id, uuid from node_index")
        )
    else:
        if postgres is None:
            raise ValueError("PostgreSQL mapping is required")
        import psycopg2

        host, port, user, database = postgres
        needed = {int(node) for node in nodes}
        mapping = {}
        with psycopg2.connect(
            host=host,
            port=port,
            user=user,
            database=database,
        ) as pg_connection:
            with pg_connection.cursor() as cursor:
                for table in (
                    "file_node_table",
                    "netflow_node_table",
                    "subject_node_table",
                ):
                    cursor.execute(
                        f"select index_id, node_uuid from {table}"
                    )
                    while True:
                        rows = cursor.fetchmany(50000)
                        if not rows:
                            break
                        mapping.update(
                            {
                                str(index): uuid.upper()
                                for index, uuid in rows
                                if index in needed
                            }
                        )
    result = {}
    for node, score in zip(nodes, scores):
        uuid = mapping.get(str(node))
        if uuid is not None:
            result[uuid] = float(score)
    return result


def load_loss_scores(
    directory: Path,
    connection: sqlite3.Connection,
) -> tuple[dict[str, float], str, int]:
    mapping = dict(
        connection.execute("select index_id, uuid from node_index")
    )
    return load_loss_scores_with_mapping(directory, mapping)


def load_loss_scores_with_mapping(
    directory: Path,
    mapping: dict[str, str],
) -> tuple[dict[str, float], str, int]:
    scores: dict[str, float] = {}
    files = sorted(directory.rglob("*.csv"))
    for path in files:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                loss = float(row["loss"])
                for column in ("srcnode", "dstnode"):
                    node = mapping.get(str(row[column]))
                    if node is not None:
                        scores[node] = max(scores.get(node, float("-inf")), loss)
    if not scores:
        raise ValueError("test losses are empty")
    digest = hashlib.sha256(
        json.dumps(
            sorted(scores.items()),
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return scores, digest, len(files)


def maximum_loss(directory: Path) -> float:
    maximum = float("-inf")
    for path in directory.rglob("*.csv"):
        with path.open(newline="", encoding="utf-8") as handle:
            rows = csv.reader(handle)
            next(rows)
            for row in rows:
                maximum = max(maximum, float(row[0]))
    if maximum == float("-inf"):
        raise ValueError("validation losses are empty")
    return maximum


def main() -> None:
    parser = argparse.ArgumentParser()
    events_source = parser.add_mutually_exclusive_group(required=True)
    events_source.add_argument("--database", type=Path)
    events_source.add_argument("--pg-dsn")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--scores", type=Path)
    source.add_argument("--test-losses", type=Path)
    threshold = parser.add_mutually_exclusive_group(required=True)
    threshold.add_argument("--threshold", type=float)
    threshold.add_argument("--validation-losses", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pg-host")
    parser.add_argument("--pg-port", default="5432")
    parser.add_argument("--pg-user")
    parser.add_argument("--pg-database")
    parser.add_argument("--budget", type=int)
    parser.add_argument(
        "--dataset",
        choices=tuple(OFFICIAL_SPLITS),
        default="clearscope",
    )
    parser.add_argument(
        "--detector",
        choices=("velox", "ravel_tgn"),
        default="velox",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    dataset = OFFICIAL_SPLITS[args.dataset]
    velox_threshold = (
        maximum_loss(args.validation_losses)
        if args.validation_losses is not None
        else args.threshold
    )
    sqlite_connection = None
    postgres_connection = None
    if args.database is not None:
        sqlite_connection = sqlite3.connect(
            f"file:{args.database}?mode=ro",
            uri=True,
        )
        mapping_override = None
        event_stream = lambda days: sqlite_events(
            sqlite_connection,
            days,
        )
        event_source = "sqlite_projection"
    else:
        import psycopg2

        postgres_connection = psycopg2.connect(args.pg_dsn)
        catalog = node_catalog(postgres_connection)
        mapping_override = {
            index: value[0]
            for index, value in catalog.items()
        }
        event_stream = lambda days: postgres_events(
            postgres_connection,
            catalog,
            days,
        )
        event_source = "postgres_projection"
    pg_values = (
        args.pg_host,
        args.pg_port,
        args.pg_user,
        args.pg_database,
    )
    postgres = (
        pg_values
        if all(pg_values)
        else None
    )
    if args.test_losses is not None:
        if mapping_override is not None:
            official, digest, score_files = load_loss_scores_with_mapping(
                args.test_losses,
                mapping_override,
            )
        elif sqlite_connection is not None:
            official, digest, score_files = load_loss_scores(
                args.test_losses,
                sqlite_connection,
            )
        else:
            raise ValueError("node mapping is unavailable")
        score_source = "edge_loss_maxima"
    else:
        official = load_scores(
            args.scores,
            sqlite_connection,
            postgres,
            mapping_override,
        )
        digest = hashlib.sha256(args.scores.read_bytes()).hexdigest()
        score_files = 1
        score_source = "evaluation_pickle"
    profile = NormalProfile()
    profile.fit(event_stream(dataset.train))
    profile_threshold = validation_threshold(
        profile,
        event_stream(dataset.validation),
    )
    seeds = select_seeds(
        official,
        velox_threshold,
        args.budget,
    )
    expanded: dict[str, float] = {}
    chain_count = 0
    seeded_chain_count = 0
    for day in dataset.test:
        result = CDMAttackAgent(
            profile,
            profile_threshold,
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
            if not endpoints & seeds:
                continue
            seeded_chain_count += 1
            for predicate in chain.predicates:
                support = chain.score * predicate.confidence
                for node in predicate.details["endpoints"]:
                    if node not in official:
                        continue
                    value = support * official[node]
                    expanded[node] = max(
                        expanded.get(node, 0.0),
                        value,
                    )
    if sqlite_connection is not None:
        sqlite_connection.close()
    if postgres_connection is not None:
        postgres_connection.close()
    manifest = {
        "method": (
            "official_velox_seeded_chain_v1"
            if args.detector == "velox"
            else "matched_tgn_seeded_chain_v1"
        ),
        "detector": args.detector,
        "dataset": args.dataset,
        "official_score_sha256": digest,
        "official_score_source": score_source,
        "official_score_files": score_files,
        "event_source": event_source,
        "split": {
            "train": dataset.train,
            "validation": dataset.validation,
            "test": dataset.test,
        },
        "thresholds": {
            "velox": velox_threshold,
            "profile": profile_threshold,
        },
        "root_policy": (
            "strict_threshold"
            if args.budget is None
            else "top_k_capacity"
        ),
        "root_budget": len(seeds),
        "official_scores": sorted(official.items()),
        "seeds": sorted(seeds),
        "expanded": sorted(expanded.items()),
        "chain_count": chain_count,
        "seeded_chain_count": seeded_chain_count,
        "runtime_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False)
    print(
        json.dumps(
            {
                "nodes": len(official),
                "seeds": len(seeds),
                "expanded": len(expanded),
                "chains": chain_count,
                "seeded_chains": seeded_chain_count,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
