from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from experiments.optc import timestamp_nanos


MARGIN = 90 * 1_000_000_000


@dataclass(frozen=True)
class Segment:
    identifier: str
    hostname: str
    pid: int
    start: int
    stop: int | None


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def load_manifest(path: Path) -> tuple[dict, str]:
    payload_bytes = path.read_bytes()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload, hashlib.sha256(payload_bytes).hexdigest()


def load_segments(path: Path, target: str) -> list[Segment]:
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for number, row in enumerate(csv.reader(handle), 1):
            if not row or row[0].startswith("#"):
                continue
            if len(row) != 4 or re.match(row[0], target, re.I) is None:
                continue
            rows.append(
                Segment(
                    f"{number}:{row[1]}:{row[2]}",
                    row[0],
                    int(row[1]),
                    timestamp_nanos(row[2]),
                    (
                        None
                        if row[3] == "Infinity"
                        else timestamp_nanos(row[3])
                    ),
                )
            )
    if not rows:
        raise ValueError("host has no registered segments")
    return rows


def labels(
    path: Path,
    segments: list[Segment],
) -> tuple[set[str], dict[str, set[str]], int]:
    aggregate = set()
    by_segment = {segment.identifier: set() for segment in segments}
    events = 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            actor = str(payload["actorID"]).upper()
            aggregate.add(actor)
            events += 1
            stamp = timestamp_nanos(str(payload["timestamp"]))
            pid = int(payload["pid"])
            hostname = str(payload["hostname"])
            for segment in segments:
                if (
                    pid == segment.pid
                    and re.match(segment.hostname, hostname, re.I) is not None
                    and stamp >= segment.start - MARGIN
                    and (
                        segment.stop is None
                        or stamp <= segment.stop + MARGIN
                    )
                ):
                    by_segment[segment.identifier].add(actor)
    return aggregate, by_segment, events


def selection_metrics(
    selected: set[str],
    malicious: set[str],
    universe: set[str],
) -> dict:
    if not selected <= universe:
        raise ValueError("selection is outside the score universe")
    recovered = selected & malicious
    covered = malicious & universe
    tp = len(recovered)
    fp = len(selected) - tp
    fn = len(covered) - tp
    tn = len(universe) - tp - fp - fn
    denominator = math.sqrt(
        (tp + fp)
        * (tp + fn)
        * (tn + fp)
        * (tn + fn)
    )
    return {
        "budget": len(selected),
        "malicious": len(malicious),
        "covered_malicious": len(covered),
        "recovered": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": tp / len(selected) if selected else 0.0,
        "covered_recall": (
            tp / len(covered)
            if covered
            else None
        ),
        "mcc": (
            (tp * tn - fp * fn) / denominator
            if denominator
            else 0.0
        ),
        "random_budget": {
            "expected_recovered": (
                len(selected) * len(covered) / len(universe)
                if universe
                else 0.0
            ),
            "p_at_least_observed": hypergeometric_tail(
                len(universe),
                len(covered),
                len(selected),
                tp,
            ),
        },
        "recovered_nodes": sorted(recovered),
    }


def hypergeometric_tail(
    population: int,
    positives: int,
    draws: int,
    observed: int,
) -> float:
    if not (
        0 <= positives <= population
        and 0 <= draws <= population
    ):
        raise ValueError("invalid hypergeometric parameters")
    lower = max(observed, 0, draws - (population - positives))
    upper = min(draws, positives)
    if lower > upper:
        return 0.0
    denominator = (
        math.lgamma(population + 1)
        - math.lgamma(draws + 1)
        - math.lgamma(population - draws + 1)
    )
    values = [
        (
            math.lgamma(positives + 1)
            - math.lgamma(value + 1)
            - math.lgamma(positives - value + 1)
            + math.lgamma(population - positives + 1)
            - math.lgamma(draws - value + 1)
            - math.lgamma(
                population - positives - draws + value + 1
            )
            - denominator
        )
        for value in range(lower, upper + 1)
    ]
    maximum = max(values)
    return min(
        math.exp(maximum)
        * sum(math.exp(value - maximum) for value in values),
        1.0,
    )


def hypergeometric_two_sided(
    population: int,
    positives: int,
    draws: int,
    observed: int,
) -> float:
    if not (
        0 <= positives <= population
        and 0 <= draws <= population
    ):
        raise ValueError("invalid hypergeometric parameters")
    lower = max(0, draws - (population - positives))
    upper = min(draws, positives)
    if observed < lower or observed > upper:
        return 0.0
    denominator = (
        math.lgamma(population + 1)
        - math.lgamma(draws + 1)
        - math.lgamma(population - draws + 1)
    )

    def log_probability(value: int) -> float:
        return (
            math.lgamma(positives + 1)
            - math.lgamma(value + 1)
            - math.lgamma(positives - value + 1)
            + math.lgamma(population - positives + 1)
            - math.lgamma(draws - value + 1)
            - math.lgamma(
                population - positives - draws + value + 1
            )
            - denominator
        )

    observed_probability = log_probability(observed)
    values = [
        probability
        for value in range(lower, upper + 1)
        if (
            probability := log_probability(value)
        ) <= observed_probability + 1e-12
    ]
    maximum = max(values)
    return min(
        math.exp(maximum)
        * sum(math.exp(value - maximum) for value in values),
        1.0,
    )


def matched_disagreement(
    baseline: set[str],
    candidate: set[str],
    malicious: set[str],
) -> dict:
    baseline_only = baseline - candidate
    candidate_only = candidate - baseline
    if len(baseline_only) != len(candidate_only):
        raise ValueError("matched comparison requires equal budgets")
    discordant = baseline_only | candidate_only
    positives = len(discordant & malicious)
    candidate_positives = len(candidate_only & malicious)
    baseline_positives = len(baseline_only & malicious)
    pairs = len(candidate_only)
    return {
        "changed_slots": pairs,
        "baseline_only_malicious": baseline_positives,
        "candidate_only_malicious": candidate_positives,
        "recovered_delta": candidate_positives - baseline_positives,
        "conditional_null": {
            "p_candidate_at_least_observed": (
                hypergeometric_tail(
                    2 * pairs,
                    positives,
                    pairs,
                    candidate_positives,
                )
                if pairs
                else 1.0
            ),
            "p_two_sided": (
                hypergeometric_two_sided(
                    2 * pairs,
                    positives,
                    pairs,
                    candidate_positives,
                )
                if pairs
                else 1.0
            ),
            "descriptive_not_generalization_test": True,
        },
    }


def evaluate(
    manifest_path: Path,
    ravel_path: Path,
    events_path: Path,
    segments_path: Path,
    host: str,
) -> dict:
    manifest, manifest_sha256 = load_manifest(manifest_path)
    ravel, ravel_sha256 = load_manifest(ravel_path)
    if ravel["method"] != "ravel_v6":
        raise ValueError("exact transport result is required")
    if ravel["input_manifest_sha256"] != manifest_sha256:
        raise ValueError("RAVEL input manifest mismatch")
    if int(manifest["root_budget"]) != 512 or int(ravel["budget"]) != 512:
        raise ValueError("registered budget mismatch")
    official = {str(node).upper() for node in manifest["seeds"]}
    selected = {
        str(node).upper()
        for node in ravel["selections"]["full"]["nodes"]
    }
    if len(official) != 512 or len(selected) != 512:
        raise ValueError("selection must contain 512 unique nodes")
    universe = {
        str(node).upper()
        for node, _ in manifest["official_scores"]
    }
    target = f"SysClient{host}.systemia.com"
    segment_rows = load_segments(segments_path, target)
    malicious, segment_labels, event_count = labels(
        events_path,
        segment_rows,
    )
    official_metrics = selection_metrics(official, malicious, universe)
    ravel_metrics = selection_metrics(selected, malicious, universe)
    segment_metrics = []
    no_decline = True
    for segment in segment_rows:
        current = segment_labels[segment.identifier]
        baseline = len(official & current)
        exact = len(selected & current)
        covered = len(current & universe)
        if covered and exact < baseline:
            no_decline = False
        segment_metrics.append(
            {
                "id": segment.identifier,
                "hostname": segment.hostname,
                "pid": segment.pid,
                "start": segment.start,
                "stop": segment.stop,
                "malicious": len(current),
                "covered_malicious": covered,
                "official": baseline,
                "ravel_v6": exact,
            }
        )
    improvement = (
        ravel_metrics["recovered"] > official_metrics["recovered"]
    )
    return {
        "method": "corrected_optc_actor_eval_v2",
        "host": host,
        "label_source": "Majorczyk et al. corrected host ground truth",
        "manifest_sha256": manifest_sha256,
        "ravel_sha256": ravel_sha256,
        "events_sha256": digest(events_path),
        "segments_sha256": digest(segments_path),
        "label_events": event_count,
        "score_universe": len(universe),
        "official": official_metrics,
        "ravel_v6": ravel_metrics,
        "matched_disagreement": matched_disagreement(
            official,
            selected,
            malicious,
        ),
        "segments": segment_metrics,
        "aggregate_improvement": improvement,
        "segment_no_decline": no_decline,
        "host_success": improvement and no_decline,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ravel", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--host", choices=("0201", "0501"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        args.manifest,
        args.ravel,
        args.events,
        args.segments,
        args.host,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "host": result["host"],
                "official": result["official"]["recovered"],
                "ravel_v6": result["ravel_v6"]["recovered"],
                "host_success": result["host_success"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
