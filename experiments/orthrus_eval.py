from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from optc_eval import matched_disagreement, selection_metrics


def load(path: Path) -> tuple[dict, str]:
    content = path.read_bytes()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle), hashlib.sha256(content).hexdigest()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def malicious_uuids(path: Path) -> tuple[set[str], int]:
    values = set()
    rows = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if not row:
                continue
            if len(row) < 3:
                raise ValueError("ground-truth row has fewer than three fields")
            values.add(str(row[0]).upper())
            rows += 1
    if not values:
        raise ValueError("ground truth is empty")
    return values, rows


def evaluate(
    manifest_path: Path,
    routes_path: Path,
    source_path: Path,
    candidate_path: Path,
    labels_path: Path,
) -> dict:
    manifest, manifest_sha256 = load(manifest_path)
    routes, routes_sha256 = load(routes_path)
    source, source_sha256 = load(source_path)
    candidate, candidate_sha256 = load(candidate_path)
    if manifest["dataset"] != "optc_h051":
        raise ValueError("H051 manifest is required")
    if candidate["method"] != "ravel_cert_v4":
        raise ValueError("certified transport result is required")
    if candidate["input_manifest_sha256"] != manifest_sha256:
        raise ValueError("candidate input manifest mismatch")
    if routes["method"] != "flowsub_v1":
        raise ValueError("FlowSub result is required")
    if routes["input_manifest_sha256"] != manifest_sha256:
        raise ValueError("route input manifest mismatch")
    if source["method"] != "ravel_v6":
        raise ValueError("ravel_v6 source is required")
    if source["input_manifest_sha256"] != manifest_sha256:
        raise ValueError("source input manifest mismatch")
    if source["route_manifest_sha256"] != routes_sha256:
        raise ValueError("source route manifest mismatch")
    if candidate["source_sha256"] != source_sha256:
        raise ValueError("candidate source mismatch")
    official = {
        str(node).upper()
        for node in manifest["seeds"]
    }
    selected = {
        str(node).upper()
        for node in candidate["selections"]["full"]["nodes"]
    }
    methods = {
        "official": official,
        "flowsub": {
            str(node).upper()
            for node in routes["selections"]["full"]["nodes"]
        },
        "ravel_v6": {
            str(node).upper()
            for node in source["selections"]["full"]["nodes"]
        },
        "certified": selected,
    }
    if (
        not official
        or any(len(nodes) != len(official) for nodes in methods.values())
    ):
        raise ValueError("matched unique budgets are required")
    universe = {
        str(node).upper()
        for node, _ in manifest["official_scores"]
    }
    malicious, label_rows = malicious_uuids(labels_path)
    metrics = {
        name: selection_metrics(nodes, malicious, universe)
        for name, nodes in methods.items()
    }
    official_metrics = metrics["official"]
    candidate_metrics = metrics["certified"]
    activated = int(candidate["certified_transports"]) > 0
    safety = (
        candidate_metrics["recovered"]
        >= official_metrics["recovered"]
    )
    efficacy = (
        candidate_metrics["recovered"]
        > official_metrics["recovered"]
    )
    return {
        "method": "ravel_cert_orthrus_eval_v1",
        "dataset": "optc_h051",
        "manifest_sha256": manifest_sha256,
        "routes_sha256": routes_sha256,
        "source_sha256": source_sha256,
        "candidate_sha256": candidate_sha256,
        "labels_sha256": digest(labels_path),
        "label_rows": label_rows,
        "score_universe": len(universe),
        "metrics": metrics,
        "comparisons": {
            name: matched_disagreement(
                methods[name],
                selected,
                malicious,
            )
            for name in ("official", "flowsub", "ravel_v6")
        },
        "certified_transports": int(
            candidate["certified_transports"]
        ),
        "activated": activated,
        "primary_safety": safety and activated,
        "secondary_efficacy": efficacy and activated,
        "competitive_noninferiority": (
            activated
            and candidate_metrics["recovered"]
            >= metrics["flowsub"]["recovered"]
        ),
        "strict_all_comparators": (
            activated
            and candidate_metrics["recovered"]
            > max(
                metrics[name]["recovered"]
                for name in ("official", "flowsub", "ravel_v6")
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--routes", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        args.manifest,
        args.routes,
        args.source,
        args.candidate,
        args.labels,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "official": result["metrics"]["official"]["recovered"],
                "flowsub": result["metrics"]["flowsub"]["recovered"],
                "ravel_v6": result["metrics"]["ravel_v6"]["recovered"],
                "certified": result["metrics"]["certified"]["recovered"],
                "activated": result["activated"],
                "primary_safety": result["primary_safety"],
                "secondary_efficacy": result[
                    "secondary_efficacy"
                ],
                "competitive_noninferiority": result[
                    "competitive_noninferiority"
                ],
                "strict_all_comparators": result[
                    "strict_all_comparators"
                ],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
