from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


LABELS = {
    6: ("node_Nginx_Backdoor_06.csv",),
    11: (),
    12: ("node_Nginx_Backdoor_12.csv",),
    13: ("node_Nginx_Backdoor_13.csv",),
}


def score_map(rows: list[list[str | float]]) -> dict[str, float]:
    return {
        str(node): float(score)
        for node, score in rows
    }


def load_labels(
    directory: Path,
) -> tuple[dict[int, set[str]], dict[tuple[int, str], set[str]]]:
    by_day = {}
    by_attack = {}
    for day, filenames in LABELS.items():
        values = set()
        for filename in filenames:
            with (directory / filename).open(
                newline="",
                encoding="utf-8",
            ) as handle:
                labels = {
                    row[0].upper()
                    for row in csv.reader(handle)
                    if row
                }
            values.update(labels)
            by_attack[(day, filename)] = labels
        by_day[day] = values
    return by_day, by_attack


def selected_metrics(
    universe: set[str],
    labels: set[str],
    selected: set[str],
) -> dict[str, int | float]:
    selected = selected & universe
    truth = labels & universe
    tp = len(selected & truth)
    fp = len(selected - truth)
    fn = len(truth - selected)
    tn = len(universe - selected - truth)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    denominator = math.sqrt(
        max(
            (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn),
            0,
        )
    )
    return {
        "reported": len(selected),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mcc": (tp * tn - fp * fn) / denominator
        if denominator
        else 0.0,
    }


def ranking_metrics(
    labels: set[str],
    scores: dict[str, float],
) -> dict[str, float | None]:
    nodes = sorted(scores)
    truth = np.asarray(
        [node in labels for node in nodes],
        dtype=np.int8,
    )
    values = np.asarray(
        [scores[node] for node in nodes],
        dtype=float,
    )
    result = {
        "auroc": (
            float(roc_auc_score(truth, values))
            if 0 < int(truth.sum()) < len(truth)
            else None
        ),
        "ap": (
            float(average_precision_score(truth, values))
            if int(truth.sum()) > 0
            else None
        ),
    }
    ranked = np.argsort(values, kind="stable")[::-1]
    positives = max(int(truth.sum()), 1)
    for budget in (100, 500, 1000):
        chosen = ranked[: min(budget, len(ranked))]
        tp = int(truth[chosen].sum())
        result[f"precision_at_{budget}"] = tp / max(len(chosen), 1)
        result[f"recall_at_{budget}"] = tp / positives
    return result


def top_nodes(
    scores: dict[str, float],
    count: int,
) -> set[str]:
    return {
        node
        for node, _ in sorted(
            scores.items(),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )[:count]
    }


def merge_scores(
    base: dict[str, float],
    extra: dict[str, float],
) -> dict[str, float]:
    return {
        node: max(score, extra.get(node, 0.0))
        for node, score in base.items()
    }


def conformal_scores(
    pairwise: dict[str, float],
    profile: dict[str, float],
    pairwise_reference: np.ndarray,
    profile_reference: np.ndarray,
) -> dict[str, float]:
    nodes = set(pairwise) | set(profile)
    result = {}
    pairwise_count = len(pairwise_reference)
    profile_count = len(profile_reference)
    for node in nodes:
        pairwise_index = np.searchsorted(
            pairwise_reference,
            pairwise.get(node, 0.0),
            side="left",
        )
        profile_index = np.searchsorted(
            profile_reference,
            profile.get(node, 0.0),
            side="left",
        )
        pairwise_p = (
            pairwise_count - pairwise_index + 1
        ) / (pairwise_count + 1)
        profile_p = (
            profile_count - profile_index + 1
        ) / (profile_count + 1)
        statistic = 0.5 * (
            math.tan(math.pi * (0.5 - pairwise_p))
            + math.tan(math.pi * (0.5 - profile_p))
        )
        combined_p = 0.5 - math.atan(statistic) / math.pi
        result[node] = -math.log10(max(combined_p, 1e-12))
    return result


def bootstrap_interval(
    values: list[float],
    iterations: int = 10000,
) -> list[float]:
    if not values:
        return [0.0, 0.0]
    array = np.asarray(values, dtype=float)
    random = np.random.default_rng(3407)
    samples = random.choice(
        array,
        size=(iterations, len(array)),
        replace=True,
    ).mean(axis=1)
    return [
        float(np.quantile(samples, 0.025)),
        float(np.quantile(samples, 0.975)),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(
        args.manifest,
        "rt",
        encoding="utf-8",
    ) as handle:
        manifest = json.load(handle)
    labels_by_day, labels_by_attack = load_labels(args.ground_truth)
    pairwise_threshold = float(
        manifest["detector"]["calibration"]["threshold"]
    )
    profile_threshold = float(manifest["profile_threshold"])
    pairwise_validation = score_map(
        manifest["validation"]["pairwise_scores"]
    )
    profile_validation = score_map(
        manifest["validation"]["profile_scores"]
    )
    pairwise_reference = np.sort(
        np.asarray(list(pairwise_validation.values()), dtype=float)
    )
    profile_reference = np.sort(
        np.asarray(list(profile_validation.values()), dtype=float)
    )
    fused_validation = conformal_scores(
        pairwise_validation,
        profile_validation,
        pairwise_reference,
        profile_reference,
    )
    fused_threshold = max(fused_validation.values(), default=12.0)
    day_results = {}
    aggregate_universe = set()
    aggregate_labels = set()
    aggregate_scores = {
        "pairwise": {},
        "hybrid": {},
        "broad": {},
        "profile_alert": {},
        "profile_chain": {},
        "grounded": {},
        "profile": {},
        "fused": {},
        "consensus": {},
    }
    aggregate_selected = {
        "pairwise": set(),
        "hybrid": set(),
        "broad": set(),
        "profile_alert": set(),
        "profile_chain": set(),
        "grounded": set(),
        "profile": set(),
        "fused": set(),
        "consensus": set(),
    }
    paired_deltas = {}
    for day_text, payload in manifest["days"].items():
        day = int(day_text)
        pairwise = score_map(payload["pairwise_scores"])
        seeded = score_map(payload["pairwise_seeded"])
        broad_chain = score_map(payload["pairwise_broad"])
        profile = score_map(payload["profile_scores"])
        profile_chain = score_map(payload["profile_chains"])
        grounded = (
            score_map(payload["profile_grounded"])
            if "profile_grounded" in payload
            else {
                node: score * profile.get(node, 0.0)
                for node, score in profile_chain.items()
            }
        )
        fused = conformal_scores(
            pairwise,
            profile,
            pairwise_reference,
            profile_reference,
        )
        universe = set(pairwise)
        labels = labels_by_day[day]
        selected = {
            "pairwise": {
                node
                for node, score in pairwise.items()
                if score > pairwise_threshold
            },
            "hybrid": set(seeded),
            "broad": set(broad_chain),
            "profile_alert": {
                node
                for node, score in profile.items()
                if score >= profile_threshold
            },
            "profile_chain": set(profile_chain),
            "grounded": set(grounded),
            "profile": set(profile_chain),
            "fused": {
                node
                for node, score in fused.items()
                if score > fused_threshold
            },
            "consensus": set(),
        }
        selected["hybrid"].update(selected["pairwise"])
        selected["broad"].update(selected["pairwise"])
        selected["profile"].update(
            selected["profile_alert"]
        )
        selected["consensus"].update(selected["fused"])
        selected["consensus"].update(
            set(profile_chain) & set(broad_chain)
        )
        grounded_scores = {
            node: grounded.get(node, 0.0)
            for node in universe
        }
        scores = {
            "pairwise": pairwise,
            "hybrid": merge_scores(pairwise, seeded),
            "broad": merge_scores(pairwise, broad_chain),
            "profile_alert": profile,
            "profile_chain": merge_scores(profile, profile_chain),
            "grounded": grounded_scores,
            "profile": merge_scores(profile, profile_chain),
            "fused": fused,
            "consensus": fused,
        }
        detection = {
            name: selected_metrics(
                universe,
                labels,
                values,
            )
            for name, values in selected.items()
        }
        ranking = {
            name: ranking_metrics(labels, values)
            for name, values in scores.items()
        }
        matched = {}
        anchors = {
            "hybrid": pairwise,
            "broad": pairwise,
            "profile_alert": profile,
            "profile_chain": profile,
            "grounded": profile,
            "profile": profile,
            "fused": fused,
            "consensus": fused,
        }
        for name, anchor in anchors.items():
            baseline = top_nodes(anchor, len(selected[name]))
            result = selected_metrics(universe, labels, baseline)
            matched[name] = result
            key = f"{name}_vs_matched"
            paired_deltas.setdefault(key, []).append(
                detection[name]["tp"] - result["tp"]
            )
        day_results[day_text] = {
            "nodes": len(universe),
            "positives": len(labels & universe),
            "detection": detection,
            "matched_pairwise": matched,
            "ranking": ranking,
        }
        for node in universe:
            key = f"{day}:{node}"
            aggregate_universe.add(key)
            if node in labels:
                aggregate_labels.add(key)
            for name in aggregate_scores:
                aggregate_scores[name][key] = scores[name][node]
                if node in selected[name]:
                    aggregate_selected[name].add(key)

    attack_detection = {}
    for name in aggregate_selected:
        detected = 0
        details = {}
        for (day, filename), labels in labels_by_attack.items():
            selected_nodes = {
                key.split(":", 1)[1]
                for key in aggregate_selected[name]
                if key.startswith(f"{day}:")
            }
            hit = bool(selected_nodes & labels)
            detected += int(hit)
            details[f"{day}:{filename}"] = hit
        attack_detection[name] = {
            "detected": detected,
            "total": len(labels_by_attack),
            "rate": detected / max(len(labels_by_attack), 1),
            "attacks": details,
        }
    aggregate = {
        "nodes": len(aggregate_universe),
        "positives": len(aggregate_labels),
        "detection": {
            name: selected_metrics(
                aggregate_universe,
                aggregate_labels,
                values,
            )
            for name, values in aggregate_selected.items()
        },
        "ranking": {
            name: ranking_metrics(
                aggregate_labels,
                values,
            )
            for name, values in aggregate_scores.items()
        },
        "attack_detection": attack_detection,
        "paired_tp_delta": {
            name: {
                "day_values": values,
                "mean": float(np.mean(values)),
                "bootstrap_95": bootstrap_interval(values),
            }
            for name, values in paired_deltas.items()
        },
    }
    result = {
        "method": manifest["method"],
        "official_velox_reproduction": False,
        "manifest": args.manifest.name,
        "split": manifest["split"],
        "thresholds": {
            "pairwise": pairwise_threshold,
            "profile": profile_threshold,
            "fused": fused_threshold,
        },
        "aggregate": aggregate,
        "days": day_results,
        "runtime_seconds": manifest["runtime_seconds"],
        "peak_memory_mb": manifest["peak_memory_mb"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(result["aggregate"], ensure_ascii=False),
        flush=True,
    )


if __name__ == "__main__":
    main()
