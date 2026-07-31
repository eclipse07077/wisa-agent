from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

try:
    import resource
except ImportError:
    resource = None

from wisa_agent.tc.cdm_agent import (
    CDMAttackAgent,
    NormalProfile,
    ProvenanceEvent,
    validation_threshold,
)
from wisa_agent.tc.pairwise import PairwiseSeedDetector, RELATIONS


@dataclass(frozen=True)
class Split:
    train: tuple[int, ...]
    validation: tuple[int, ...]
    test: tuple[int, ...]


CADETS = Split(
    train=(2, 3, 4, 5, 7, 8, 9),
    validation=(10,),
    test=(6, 11, 12, 13),
)


def events(
    connection: sqlite3.Connection,
    days: tuple[int, ...],
) -> Iterator[ProvenanceEvent]:
    query = (
        "select e.timestamp, e.source, e.target, e.relation, e.path, "
        "coalesce(s.kind, 'unknown'), coalesce(t.kind, 'unknown') "
        "from events e "
        "left join nodes s on s.uuid = e.source "
        "left join nodes t on t.uuid = e.target "
        "where e.day = ? order by e.timestamp"
    )
    for day in days:
        cursor = connection.execute(query, (day,))
        while True:
            rows = cursor.fetchmany(50000)
            if not rows:
                break
            for row in rows:
                yield ProvenanceEvent(*row)


def pairs(values: dict[str, float]) -> list[list[str | float]]:
    return [
        [node, score]
        for node, score in sorted(values.items())
    ]


def node_scores(scored) -> dict[str, float]:
    values = {}
    for item in scored:
        for node in (item.event.source, item.event.target):
            values[node] = max(values.get(node, 0.0), item.score)
    return values


def chain_summary(output) -> list[dict]:
    return [
        {
            "id": chain.chain_id,
            "score": chain.score,
            "stages": [
                predicate.stage.value
                for predicate in chain.predicates
            ],
            "relations": [
                predicate.relation
                for predicate in chain.predicates
            ],
            "nodes": sorted(
                {
                    node
                    for predicate in chain.predicates
                    for node in predicate.details["endpoints"]
                }
            ),
        }
        for chain in sorted(
            output.chains,
            key=lambda item: item.score,
            reverse=True,
        )[:48]
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=65536)
    parser.add_argument("--seed", type=int, default=3407)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    connection = sqlite3.connect(
        f"file:{args.database}?mode=ro",
        uri=True,
    )

    last_progress = {"train": 0, "validation": 0}

    def progress(stage: str):
        def emit(count: int, value: float) -> None:
            if count - last_progress[stage] >= 1_000_000:
                print(stage, count, value, flush=True)
                last_progress[stage] = count

        return emit

    if args.resume and args.checkpoint.exists():
        detector = PairwiseSeedDetector.load(
            args.checkpoint,
            device=args.device,
        )
        training = {"resumed": True}
    else:
        detector = PairwiseSeedDetector(
            device=args.device,
            seed=args.seed,
        )
        training = detector.fit(
            events(connection, CADETS.train),
            batch_size=args.batch_size,
            progress=progress("train"),
        )
        detector.save(args.checkpoint)
    if detector.calibration is None:
        calibration = detector.calibrate(
            events(connection, CADETS.validation),
            batch_size=args.batch_size,
            progress=progress("validation"),
        )
        detector.save(args.checkpoint)
    else:
        calibration = detector.calibration

    profile = NormalProfile()
    profile.fit(events(connection, CADETS.train))
    profile_threshold = validation_threshold(
        profile,
        events(connection, CADETS.validation),
    )
    pairwise_validation = node_scores(
        detector.iter_scores(
            events(connection, CADETS.validation),
            batch_size=args.batch_size,
        )
    )
    profile_agent = CDMAttackAgent(profile, profile_threshold)
    profile_validation = node_scores(
        profile_agent._score_stream(
            events(connection, CADETS.validation)
        )
    )
    pairwise_profile = NormalProfile()
    pairwise_profile.relations.update(RELATIONS)
    outputs = {}
    counts = Counter()
    for day in CADETS.test:
        pairwise = CDMAttackAgent(
            pairwise_profile,
            calibration.threshold,
            predicate_mode="trace",
            attribution_mode="seeded",
        ).run_scored(
            detector.iter_scores(
                events(connection, (day,)),
                batch_size=args.batch_size,
            )
        )
        broad = CDMAttackAgent._endpoint_scores(
            list(pairwise.chains)
        )
        legacy = CDMAttackAgent(
            profile,
            profile_threshold,
            predicate_mode="trace",
            attribution_mode="endpoints",
        ).run(events(connection, (day,)))
        grounded = CDMAttackAgent._grounded_scores(
            list(legacy.chains),
            legacy.node_scores,
        )
        counts.update(
            {
                "pairwise_predicates": len(pairwise.predicates),
                "pairwise_chains": len(pairwise.chains),
                "pairwise_seeded_nodes": len(pairwise.chain_scores),
                "pairwise_broad_nodes": len(broad),
                "profile_predicates": len(legacy.predicates),
                "profile_chains": len(legacy.chains),
                "profile_chain_nodes": len(legacy.chain_scores),
            }
        )
        outputs[str(day)] = {
            "pairwise_scores": pairs(pairwise.node_scores),
            "pairwise_seeded": pairs(pairwise.chain_scores),
            "pairwise_broad": pairs(broad),
            "profile_scores": pairs(legacy.node_scores),
            "profile_chains": pairs(legacy.chain_scores),
            "profile_grounded": pairs(grounded),
            "top_chains": chain_summary(pairwise),
        }
        print(
            day,
            len(pairwise.node_scores),
            len(pairwise.chains),
            len(pairwise.chain_scores),
            len(broad),
            flush=True,
        )

    result = {
        "method": "velox_style_pairwise_plus_layer_chain",
        "official_velox_reproduction": False,
        "split": {
            "train": CADETS.train,
            "validation": CADETS.validation,
            "test": CADETS.test,
        },
        "detector": {
            "relations": RELATIONS,
            "training": training,
            "calibration": calibration.__dict__,
            "threshold_method": "maximum_validation_edge_loss",
            "checkpoint": args.checkpoint.name,
            "seed": args.seed,
        },
        "profile_threshold": profile_threshold,
        "validation": {
            "pairwise_scores": pairs(pairwise_validation),
            "profile_scores": pairs(profile_validation),
        },
        "counts": dict(sorted(counts.items())),
        "days": outputs,
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            if resource is not None
            else None
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False)
    print(
        json.dumps(
            {
                "counts": result["counts"],
                "runtime_seconds": result["runtime_seconds"],
                "peak_memory_mb": result["peak_memory_mb"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
