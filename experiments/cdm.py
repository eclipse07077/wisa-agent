from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

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


@dataclass(frozen=True)
class Dataset:
    train: tuple[int, ...]
    validation: tuple[int, ...]
    test: tuple[int, ...]
    labels: dict[int, tuple[str, ...]]


DATASETS = {
    "cadets": Dataset(
        train=(3, 4, 5, 7, 8, 9, 10),
        validation=(2,),
        test=(6, 11, 12, 13),
        labels={
            6: ("node_Nginx_Backdoor_06.csv",),
            11: (),
            12: ("node_Nginx_Backdoor_12.csv",),
            13: ("node_Nginx_Backdoor_13.csv",),
        },
    ),
    "theia": Dataset(
        train=(2, 3, 4, 5),
        validation=(9,),
        test=(10, 12, 13),
        labels={
            10: ("node_Firefox_Backdoor_Drakon_In_Memory.csv",),
            12: ("node_Browser_Extension_Drakon_Dropper.csv",),
            13: (),
        },
    ),
    "clearscope": Dataset(
        train=(3, 4, 5, 7, 8, 9, 10),
        validation=(2,),
        test=(11, 12),
        labels={
            11: ("node_clearscope_e3_firefox_0411.csv",),
            12: (),
        },
    ),
    "clearscope_e5": Dataset(
        train=(8, 9),
        validation=(11,),
        test=(14, 15, 17),
        labels={
            14: (),
            15: ("node_clearscope_e5_appstarter_0515.csv",),
            17: (
                "node_clearscope_e5_lockwatch_0517.csv",
                "node_clearscope_e5_tester_0517.csv",
            ),
        },
    ),
    "optc_h051": Dataset(
        train=(19, 20, 21),
        validation=(22,),
        test=(23, 24, 25),
        labels={
            23: (),
            24: (),
            25: ("node_h051_0925.csv",),
        },
    ),
    "optc_h201": Dataset(
        train=(19, 20, 21),
        validation=(22,),
        test=(23, 24, 25),
        labels={
            23: ("node_h201_0923.csv",),
            24: (),
            25: (),
        },
    ),
    "optc_h501": Dataset(
        train=(19, 20, 21),
        validation=(22,),
        test=(23, 24, 25),
        labels={
            23: (),
            24: ("node_h501_0924.csv",),
            25: (),
        },
    ),
}


def events(
    connection: sqlite3.Connection,
    days: tuple[int, ...],
    drop_path: bool = False,
) -> Iterator[ProvenanceEvent]:
    path = "''" if drop_path else "e.path"
    query = (
        f"select e.timestamp, e.source, e.target, e.relation, {path}, "
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


def ground_truth(
    directory: Path,
    dataset: Dataset,
) -> tuple[set[str], dict[int, set[str]]]:
    by_day: dict[int, set[str]] = {}
    for day in dataset.test:
        labels: set[str] = set()
        for filename in dataset.labels[day]:
            path = directory / filename
            with path.open(newline="", encoding="utf-8") as handle:
                labels.update(
                    row[0].upper()
                    for row in csv.reader(handle)
                    if row
                )
        by_day[day] = labels
    return set().union(*by_day.values()), by_day


def metrics(
    labels: set[str],
    node_scores: dict[str, float],
    chain_scores: dict[str, float],
) -> dict:
    from sklearn.metrics import average_precision_score, roc_auc_score

    nodes = np.asarray(sorted(node_scores))
    y = np.asarray([node in labels for node in nodes], dtype=np.int8)
    base = np.asarray([node_scores[node] for node in nodes], dtype=float)
    full = np.asarray(
        [
            max(node_scores[node], chain_scores.get(node, 0.0))
            for node in nodes
        ],
        dtype=float,
    )

    def ranking(score: np.ndarray) -> dict:
        result = {
            "auroc": (
                float(roc_auc_score(y, score))
                if 0 < int(y.sum()) < len(y)
                else None
            ),
            "ap": (
                float(average_precision_score(y, score))
                if int(y.sum()) > 0
                else None
            ),
        }
        ranked = np.argsort(score, kind="stable")[::-1]
        positives = max(int(y.sum()), 1)
        for budget in (100, 500, 1000):
            selected = ranked[: min(budget, len(ranked))]
            true_positive = int(y[selected].sum())
            result[f"precision_at_{budget}"] = true_positive / max(
                len(selected),
                1,
            )
            result[f"recall_at_{budget}"] = true_positive / positives
        return result

    chain_nodes = np.asarray(
        [index for index, node in enumerate(nodes) if node in chain_scores],
        dtype=np.int64,
    )
    chain_true = int(y[chain_nodes].sum()) if len(chain_nodes) else 0
    matched = np.argsort(base, kind="stable")[::-1][: len(chain_nodes)]
    matched_true = int(y[matched].sum()) if len(matched) else 0
    positives = max(int(y.sum()), 1)
    return {
        "nodes": len(nodes),
        "positives": int(y.sum()),
        "label_coverage": len(set(nodes.tolist()) & labels) / max(
            len(labels),
            1,
        ),
        "base": ranking(base),
        "full": ranking(full),
        "chains": {
            "reported_nodes": len(chain_nodes),
            "precision": chain_true / max(len(chain_nodes), 1),
            "recall": chain_true / positives,
            "matched_baseline_precision": matched_true
            / max(len(matched), 1),
            "matched_baseline_recall": matched_true / positives,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--dataset",
        choices=tuple(DATASETS),
        default="cadets",
    )
    parser.add_argument(
        "--predicate-mode",
        choices=("event", "semantic", "trace"),
        default="event",
    )
    parser.add_argument(
        "--method",
        choices=("v4", "v5", "v6", "v7", "v8"),
        default="v4",
    )
    parser.add_argument("--drop-path", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    dataset = DATASETS[args.dataset]
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    profile = NormalProfile(
        marginalize_missing=args.method in {"v5", "v6"},
        missingness_aware=args.method == "v7",
    )
    profile.fit(events(connection, dataset.train, args.drop_path))
    threshold = validation_threshold(
        profile,
        events(connection, dataset.validation, args.drop_path),
    )
    node_scores: dict[str, float] = {}
    chain_scores: dict[str, float] = {}
    chains = []
    plans = Counter()
    predicates = 0
    outputs = {}
    for day in dataset.test:
        output = CDMAttackAgent(
            profile,
            threshold,
            predicate_mode=args.predicate_mode,
            attribution_mode=(
                "connectors"
                if args.method == "v5"
                else "cutset"
                if args.method == "v6"
                else "core"
                if args.method == "v7"
                else "grounded"
                if args.method == "v8"
                else "endpoints"
            ),
        ).run(
            events(connection, (day,), args.drop_path)
        )
        predicates += len(output.predicates)
        chains.extend(output.chains)
        plans.update(plan.group for plan in output.plans)
        for node, score in output.node_scores.items():
            node_scores[node] = max(node_scores.get(node, 0.0), score)
        for node, score in output.chain_scores.items():
            chain_scores[node] = max(chain_scores.get(node, 0.0), score)
        outputs[day] = output
        print(
            day,
            len(output.node_scores),
            len(output.chains),
            len(output.chain_scores),
            flush=True,
        )
    all_labels, labels_by_day = ground_truth(
        args.ground_truth,
        dataset,
    )
    day_results = {
        str(day): metrics(
            labels_by_day[day],
            outputs[day].node_scores,
            outputs[day].chain_scores,
        )
        for day in dataset.test
    }
    result = {
        "dataset": args.dataset,
        "split": {
            "train": dataset.train,
            "validation": dataset.validation,
            "test": dataset.test,
        },
        "ground_truth": {
            str(day): dataset.labels[day]
            for day in dataset.test
        },
        "predicate_mode": args.predicate_mode,
        "method": args.method,
        "drop_path": args.drop_path,
        "chain_node_score": (
            "connector_local_and_persistence"
            if args.method == "v5"
            else "causal_cutset_local_and_persistence"
            if args.method == "v6"
            else "minimal_causal_core"
            if args.method == "v7"
            else "chain_support_times_local_anomaly"
            if args.method == "v8"
            else "chain_score_times_predicate_confidence"
        ),
        "threshold": threshold,
        "profile": {
            "structural_states": len(profile.structural),
            "trace_transitions": len(profile.transitions),
            "path_states": len(profile.paths),
            "marginalize_missing": profile.marginalize_missing,
            "missingness_aware": profile.missingness_aware,
        },
        "aggregate": metrics(all_labels, node_scores, chain_scores),
        "days": day_results,
        "chain_count": len(chains),
        "predicate_count": predicates,
        "plans": dict(sorted(plans.items())),
        "top_chains": [
            {
                "id": chain.chain_id,
                "score": chain.score,
                "stages": [item.stage.value for item in chain.predicates],
                "relations": [item.relation for item in chain.predicates],
                "nodes": sorted(
                    {
                        node
                        for item in chain.predicates
                        for node in item.details["endpoints"]
                    }
                ),
            }
            for chain in sorted(
                chains,
                key=lambda item: item.score,
                reverse=True,
            )[:48]
        ],
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            if resource is not None
            else None
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result["aggregate"]), flush=True)


if __name__ == "__main__":
    main()
