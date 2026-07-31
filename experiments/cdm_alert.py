from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

import numpy as np

try:
    import resource
except ImportError:
    resource = None

from experiments.cdm import DATASETS, events, ground_truth, metrics
from wisa_agent.tc.cdm_agent import (
    CDMAttackAgent,
    NormalProfile,
    validation_threshold,
)


def chain_threshold(chains, quantile: float = 0.995) -> float:
    scores = np.asarray([chain.score for chain in chains], dtype=float)
    if len(scores) == 0:
        return 1.0
    return float(np.quantile(scores, quantile, method="higher"))


def alert_scores(chains, threshold: float) -> tuple[dict[str, float], tuple]:
    scores: dict[str, float] = {}
    selected = tuple(chain for chain in chains if chain.score >= threshold)
    for chain in selected:
        for predicate in chain.predicates:
            support = chain.score * predicate.confidence
            for node in predicate.details["endpoints"]:
                scores[node] = max(scores.get(node, 0.0), support)
    return scores, selected


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
    args = parser.parse_args()
    started = time.perf_counter()
    dataset = DATASETS[args.dataset]
    connection = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    profile = NormalProfile()
    profile.fit(events(connection, dataset.train))
    anomaly_threshold = validation_threshold(
        profile,
        events(connection, dataset.validation),
    )
    validation = CDMAttackAgent(
        profile,
        anomaly_threshold,
        predicate_mode="trace",
    ).run(events(connection, dataset.validation))
    alert_threshold = chain_threshold(validation.chains)
    outputs = {}
    for day in dataset.test:
        output = CDMAttackAgent(
            profile,
            anomaly_threshold,
            predicate_mode="trace",
        ).run(events(connection, (day,)))
        selected_scores, selected_chains = alert_scores(
            output.chains,
            alert_threshold,
        )
        outputs[day] = (output, selected_scores, selected_chains)
        print(
            day,
            len(output.chains),
            len(selected_chains),
            len(selected_scores),
            flush=True,
        )
    all_labels, labels_by_day = ground_truth(args.ground_truth, dataset)
    node_scores: dict[str, float] = {}
    selected_scores: dict[str, float] = {}
    day_results = {}
    alert_count = 0
    selected_chain_count = 0
    for day in dataset.test:
        output, day_scores, selected_chains = outputs[day]
        for node, score in output.node_scores.items():
            node_scores[node] = max(node_scores.get(node, 0.0), score)
        for node, score in day_scores.items():
            selected_scores[node] = max(selected_scores.get(node, 0.0), score)
        alert_count += len(day_scores)
        selected_chain_count += len(selected_chains)
        day_results[str(day)] = {
            "unfiltered_chains": len(output.chains),
            "alert_chains": len(selected_chains),
            "alert_nodes": len(day_scores),
            "metrics": metrics(
                labels_by_day[day],
                output.node_scores,
                day_scores,
            ),
        }
    result = {
        "dataset": args.dataset,
        "status": "exploratory_after_external_output_observed",
        "split": {
            "train": dataset.train,
            "validation": dataset.validation,
            "test": dataset.test,
        },
        "anomaly_threshold": anomaly_threshold,
        "alert_rule": {
            "quantile": 0.995,
            "method": "higher",
            "validation_chain_count": len(validation.chains),
            "threshold": alert_threshold,
        },
        "aggregate": metrics(
            all_labels,
            node_scores,
            selected_scores,
        ),
        "unfiltered_chain_count": sum(
            len(output.chains) for output, _, _ in outputs.values()
        ),
        "alert_chain_count": selected_chain_count,
        "alert_node_count_sum": alert_count,
        "days": day_results,
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
