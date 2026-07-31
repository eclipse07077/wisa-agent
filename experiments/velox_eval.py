from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def selected_metrics(
    universe: set[str],
    labels: set[str],
    selected: set[str],
) -> dict[str, int | float]:
    selected = selected & universe
    labels = labels & universe
    tp = len(selected & labels)
    fp = len(selected - labels)
    fn = len(labels - selected)
    tn = len(universe - selected - labels)
    denominator = math.sqrt(
        (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    )
    return {
        "reported": len(selected),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / max(tp + fp, 1),
        "recall": tp / max(tp + fn, 1),
        "mcc": (
            (tp * tn - fp * fn) / denominator
            if denominator
            else 0.0
        ),
    }


def ranking_metrics(
    labels: set[str],
    scores: dict[str, float],
) -> dict[str, float]:
    nodes = sorted(scores)
    truth = np.asarray(
        [node in labels for node in nodes],
        dtype=np.int8,
    )
    values = np.asarray(
        [scores[node] for node in nodes],
        dtype=float,
    )
    ranked = np.argsort(values, kind="stable")[::-1]
    result = {
        "auroc": float(roc_auc_score(truth, values)),
        "ap": float(average_precision_score(truth, values)),
    }
    for budget in (100, 500, 1000):
        chosen = ranked[:budget]
        tp = int(truth[chosen].sum())
        result[f"precision_at_{budget}"] = tp / len(chosen)
        result[f"recall_at_{budget}"] = tp / int(truth.sum())
    return result


def matched_budget(
    scores: dict[str, float],
    budget: int,
) -> tuple[set[str], dict[str, int | float]]:
    ranked = [
        node
        for node, _ in sorted(
            scores.items(),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )
    ]
    matched = set(ranked[:budget])
    cutoff = scores[ranked[budget - 1]]
    strictly_above = {
        node
        for node, score in scores.items()
        if score > cutoff
    }
    tied = {
        node
        for node, score in scores.items()
        if score == cutoff
    }
    return matched, {
        "cutoff": cutoff,
        "strictly_above": len(strictly_above),
        "tied_at_cutoff": len(tied),
        "selected_from_tie": len(matched & tied),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--ground-truth",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(args.manifest, "rt", encoding="utf-8") as handle:
        manifest = json.load(handle)
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
    expanded = {
        str(node): float(score)
        for node, score in manifest["expanded"]
    }
    hybrid = seeds | set(expanded)
    matched, tie_audit = matched_budget(scores, len(hybrid))
    cutoff = float(tie_audit["cutoff"])
    tied = {
        node
        for node, score in scores.items()
        if score == cutoff
    }
    strictly_above = {
        node
        for node, score in scores.items()
        if score > cutoff
    }
    tied_positives = len(tied & labels)
    selected_from_tie = int(tie_audit["selected_from_tie"])
    tie_audit.update(
        {
            "positives_at_cutoff": tied_positives,
            "selected_tp_at_cutoff": len(tied & matched & labels),
            "minimum_total_tp": len(strictly_above & labels)
            + max(
                0,
                selected_from_tie - (len(tied) - tied_positives),
            ),
            "maximum_total_tp": len(strictly_above & labels)
            + min(selected_from_tie, tied_positives),
        }
    )
    result = {
        "method": manifest["method"],
        "dataset": manifest.get("dataset", "clearscope"),
        "official_velox_reproduction": True,
        "official_score_sha256": manifest["official_score_sha256"],
        "split": manifest["split"],
        "thresholds": manifest["thresholds"],
        "nodes": len(universe),
        "positives": len(labels & universe),
        "ranking": ranking_metrics(labels, scores),
        "seeds": selected_metrics(
            universe,
            labels,
            seeds,
        ),
        "seeded_chain": selected_metrics(
            universe,
            labels,
            hybrid,
        ),
        "matched_velox": selected_metrics(
            universe,
            labels,
            matched,
        ),
        "matched_velox_tie_audit": tie_audit,
        "attacks": {
            name: {
                "positives": len(values & universe),
                "seeds_tp": len(values & seeds & universe),
                "seeded_chain_tp": len(values & hybrid & universe),
                "matched_velox_tp": len(values & matched & universe),
            }
            for name, values in labels_by_attack.items()
        },
        "tp_delta_vs_matched": len(labels & hybrid & universe)
        - len(labels & matched & universe),
        "chain_count": manifest["chain_count"],
        "seeded_chain_count": manifest["seeded_chain_count"],
        "runtime_seconds": manifest["runtime_seconds"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
